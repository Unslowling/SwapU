from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, func, or_, select

from backend_estudiantil.adapters.db import AuditoriaLogORM, get_session_factory
from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from backend_estudiantil.domain.services.user_service import UserService
from backend_estudiantil.infrastructure.security import get_current_user
from backend_estudiantil.ports.repositories.user_repository import UserRepository

router = APIRouter(prefix="/admin", tags=["admin"])

def get_user_repository() -> UserRepository:
    return SQLAlchemyUserRepository()

def get_user_service(repo: UserRepository = Depends(get_user_repository)) -> UserService:
    return UserService(repo)

@router.post("/users/{user_id}/promote", status_code=status.HTTP_200_OK)
async def promote_user(
    user_id: str,
    service: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """Promote a user to the *moderador* role.
    Only an *admin* can perform this action.
    """
    if current_user.get("role") not in ("admin", "administrador"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    # Promote using service method
    promoted_user = await service.promote_to_moderator(user_id)
    return {"msg": f"Usuario {user_id} promovido a {promoted_user.rol}"}


# ─────────────────────────────────────────────────────────────────────────────
# Módulo y Consola de Auditoría (Regla de las 5W)
# ─────────────────────────────────────────────────────────────────────────────


class AuditoriaItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int | None = None
    usuario_email: str | None = None
    usuario_rol: str | None = None
    ip_origen: str
    user_agent: str | None = None
    accion: str
    recurso: str | None = None
    fecha_hora: datetime
    metodo_http: str
    endpoint: str
    estado_http: int
    exito: bool
    detalle: str | None = None
    duracion_ms: float | None = None


class AuditoriaRespuesta(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[AuditoriaItemRead]


class AuditoriaStats(BaseModel):
    total_eventos: int
    eventos_exitosos: int
    eventos_fallidos: int
    intentos_bloqueados_401_403: int
    usuarios_activos_auditados: int


@router.get("/auditoria", response_model=AuditoriaRespuesta, summary="Consultar logs de auditoría 5W")
async def consultar_auditoria(
    skip: int = 0,
    limit: int = 50,
    accion: str | None = None,
    usuario_id: int | None = None,
    solo_errores: bool | None = False,
    recurso: str | None = None,
    busqueda: str | None = None,
    current_user: dict = Depends(get_current_user),
):
    """Consulta la bitácora del sistema auditor aplicando la regla de las 5W.
    Solo accesible para administradores.
    """
    if current_user.get("role") not in ("admin", "administrador"):
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")

    factory = get_session_factory()
    async with factory() as session:
        condiciones = []

        if accion:
            condiciones.append(AuditoriaLogORM.accion == accion)
        if usuario_id is not None:
            condiciones.append(AuditoriaLogORM.usuario_id == usuario_id)
        if solo_errores:
            condiciones.append(AuditoriaLogORM.exito.is_(False))
        if recurso:
            condiciones.append(AuditoriaLogORM.recurso == recurso)
        if busqueda:
            termino = f"%{busqueda}%"
            condiciones.append(
                or_(
                    AuditoriaLogORM.accion.ilike(termino),
                    AuditoriaLogORM.endpoint.ilike(termino),
                    AuditoriaLogORM.usuario_email.ilike(termino),
                    AuditoriaLogORM.ip_origen.ilike(termino),
                    AuditoriaLogORM.detalle.ilike(termino),
                )
            )

        # Conteo total
        stmt_count = select(func.count(AuditoriaLogORM.id))
        if condiciones:
            stmt_count = stmt_count.where(*condiciones)
        total_res = await session.execute(stmt_count)
        total = total_res.scalar_one()

        # Consulta paginada
        stmt = (
            select(AuditoriaLogORM)
            .where(*condiciones)
            .order_by(desc(AuditoriaLogORM.fecha_hora))
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(stmt)
        items = result.scalars().all()

        return AuditoriaRespuesta(
            total=total,
            skip=skip,
            limit=limit,
            items=items,
        )


@router.get("/auditoria/stats", response_model=AuditoriaStats, summary="Estadísticas generales de auditoría")
async def obtener_estadisticas_auditoria(
    current_user: dict = Depends(get_current_user),
):
    """Retorna métricas clave del sistema auditor para el panel de administración."""
    if current_user.get("role") not in ("admin", "administrador"):
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")

    factory = get_session_factory()
    async with factory() as session:
        # Total
        total_stmt = select(func.count(AuditoriaLogORM.id))
        total = (await session.execute(total_stmt)).scalar_one()

        # Exitosos
        exitosos_stmt = select(func.count(AuditoriaLogORM.id)).where(AuditoriaLogORM.exito.is_(True))
        exitosos = (await session.execute(exitosos_stmt)).scalar_one()

        # Fallidos
        fallidos_stmt = select(func.count(AuditoriaLogORM.id)).where(AuditoriaLogORM.exito.is_(False))
        fallidos = (await session.execute(fallidos_stmt)).scalar_one()

        # 401 / 403
        bloqueados_stmt = select(func.count(AuditoriaLogORM.id)).where(
            AuditoriaLogORM.estado_http.in_([401, 403])
        )
        bloqueados = (await session.execute(bloqueados_stmt)).scalar_one()

        # Usuarios únicos auditados
        usuarios_stmt = select(func.count(func.distinct(AuditoriaLogORM.usuario_id))).where(
            AuditoriaLogORM.usuario_id.isnot(None)
        )
        usuarios_activos = (await session.execute(usuarios_stmt)).scalar_one()

        return AuditoriaStats(
            total_eventos=total,
            eventos_exitosos=exitosos,
            eventos_fallidos=fallidos,
            intentos_bloqueados_401_403=bloqueados,
            usuarios_activos_auditados=usuarios_activos,
        )


class ResumenPlataforma(BaseModel):
    usuarios_registrados: int
    libros_en_oferta: int
    trueques_completados: int
    reputacion_global: float | None


@router.get("/resumen", response_model=ResumenPlataforma, summary="Indicadores reales de la plataforma")
async def obtener_resumen_plataforma(current_user: dict = Depends(get_current_user)):
    """Conteos reales para las tarjetas del panel de administración (sin valores de ejemplo)."""
    if current_user.get("role") not in ("admin", "administrador"):
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores")

    from backend_estudiantil.adapters.db import CalificacionORM, PublicacionORM, TruequeORM, UserORM

    factory = get_session_factory()
    async with factory() as session:
        usuarios = (await session.execute(select(func.count(UserORM.id)))).scalar_one()
        libros = (await session.execute(
            select(func.count(PublicacionORM.id)).where(PublicacionORM.estado_publicacion == "activa")
        )).scalar_one()
        trueques = (await session.execute(
            select(func.count(TruequeORM.id)).where(TruequeORM.estado == "completado")
        )).scalar_one()
        promedio = (await session.execute(select(func.avg(CalificacionORM.estrellas)))).scalar_one()

    return ResumenPlataforma(
        usuarios_registrados=usuarios,
        libros_en_oferta=libros,
        trueques_completados=trueques,
        reputacion_global=round(float(promedio), 2) if promedio is not None else None,
    )
