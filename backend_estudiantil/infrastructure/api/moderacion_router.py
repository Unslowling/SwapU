"""
moderacion_router.py
--------------------
Endpoints de la API para moderadores y administradores:
- Listar reportes y actualizar su estado.
- Aplicar advertencias (escalera de sanciones).
- Aplicar sanciones (suspensión temporal o bloqueo definitivo).
- Levantar sanciones.
- Listar y resolver apelaciones.
- Endpoint para que un usuario sancionado pueda apelar su sanción (máximo 1 vez).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.future import select

from backend_estudiantil.adapters.db import (
    ApelacionORM,
    ReporteORM,
    get_session_factory,
)
from backend_estudiantil.domain.services.moderacion_sanciones_service import (
    ModeracionSancionesService,
)
from backend_estudiantil.infrastructure.security import get_current_user

router = APIRouter(tags=["moderacion"])
service = ModeracionSancionesService()


def _exigir_moderador(current_user: dict):
    rol = current_user.get("role") or current_user.get("rol")
    if rol not in ("moderador", "administrador", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de moderador o administrador para realizar esta acción.",
        )


# --- DTO Schemas ---
class AdvertenciaCreate(BaseModel):
    usuario_id: int
    motivo: str = Field(..., min_length=3)


class SancionCreate(BaseModel):
    usuario_id: int
    tipo: str = Field(..., description="advertencia, suspension_7, suspension_30, bloqueo")
    motivo: str = Field(..., min_length=3)
    dias: int | None = None


class LevantarSancionRequest(BaseModel):
    motivo: str = Field(..., min_length=3)


class ApelarSancionRequest(BaseModel):
    motivo: str = Field(..., min_length=5)


class ResolverApelacionRequest(BaseModel):
    aprobada: bool
    respuesta: str = Field(..., min_length=3)


class ReporteRead(BaseModel):
    id: int
    reportante_id: int
    objetivo_id: int
    tipo_objetivo: str
    motivo: str
    estado: str
    creado_en: str


# --- Endpoints de Moderador / Administrador ---

@router.get("/moderacion/reportes", summary="Listar reportes de contenido o usuarios")
async def listar_reportes(
    estado: str | None = Query(None, description="Filtrar por estado: pendiente, revisado, descartado, sancionado"),
    tipo_objetivo: str | None = Query(None, description="Filtrar por tipo: calificacion, publicacion, usuario, mensaje"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    _exigir_moderador(current_user)
    factory = get_session_factory()
    async with factory() as session:
        query = select(ReporteORM).order_by(ReporteORM.id.desc())
        if estado:
            query = query.where(ReporteORM.estado == estado)
        if tipo_objetivo:
            query = query.where(ReporteORM.tipo_objetivo == tipo_objetivo)
        query = query.offset(skip).limit(limit)
        result = await session.execute(query)
        reportes = result.scalars().all()
        return [
            {
                "id": r.id,
                "reportante_id": r.reportante_id,
                "objetivo_id": r.objetivo_id,
                "tipo_objetivo": r.tipo_objetivo,
                "motivo": r.motivo,
                "estado": r.estado,
                "creado_en": r.creado_en.isoformat() if r.creado_en else None,
            }
            for r in reportes
        ]


@router.post("/moderacion/advertencias", status_code=status.HTTP_201_CREATED, summary="Aplicar advertencia a un usuario")
async def aplicar_advertencia(
    payload: AdvertenciaCreate,
    current_user: dict = Depends(get_current_user),
):
    _exigir_moderador(current_user)
    try:
        res = await service.aplicar_advertencia(
            usuario_id=payload.usuario_id,
            motivo=payload.motivo,
            moderador_id=int(current_user["id"]),
            origen="manual",
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/moderacion/sanciones", status_code=status.HTTP_201_CREATED, summary="Aplicar sanción o bloqueo")
async def aplicar_sancion(
    payload: SancionCreate,
    current_user: dict = Depends(get_current_user),
):
    _exigir_moderador(current_user)
    try:
        res = await service.aplicar_sancion(
            usuario_id=payload.usuario_id,
            tipo=payload.tipo,
            motivo=payload.motivo,
            moderador_id=int(current_user["id"]),
            dias=payload.dias,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/moderacion/sanciones/{sancion_id}/levantar", summary="Levantar una sanción")
async def levantar_sancion(
    sancion_id: int,
    payload: LevantarSancionRequest,
    current_user: dict = Depends(get_current_user),
):
    _exigir_moderador(current_user)
    try:
        res = await service.levantar_sancion(
            sancion_id=sancion_id,
            moderador_id=int(current_user["id"]),
            motivo=payload.motivo,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/moderacion/apelaciones", summary="Listar apelaciones de sanciones")
async def listar_apelaciones(
    estado: str | None = Query(None, description="pendiente, aprobada, rechazada"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(50, ge=1, le=100, description="Límite por página"),
    current_user: dict = Depends(get_current_user),
):
    _exigir_moderador(current_user)
    factory = get_session_factory()
    async with factory() as session:
        query = select(ApelacionORM).order_by(ApelacionORM.id.desc()).offset(skip).limit(limit)
        if estado:
            query = query.where(ApelacionORM.estado == estado)
        result = await session.execute(query)
        apelaciones = result.scalars().all()
        return [
            {
                "id": a.id,
                "sancion_id": a.sancion_id,
                "usuario_id": a.usuario_id,
                "motivo": a.motivo,
                "estado": a.estado,
                "moderador_id": a.moderador_id,
                "respuesta": a.respuesta,
                "creado_en": a.creado_en.isoformat() if a.creado_en else None,
                "resuelto_en": a.resuelto_en.isoformat() if a.resuelto_en else None,
            }
            for a in apelaciones
        ]


@router.post("/moderacion/apelaciones/{apelacion_id}/resolver", summary="Resolver apelación de sanción")
async def resolver_apelacion(
    apelacion_id: int,
    payload: ResolverApelacionRequest,
    current_user: dict = Depends(get_current_user),
):
    _exigir_moderador(current_user)
    try:
        res = await service.resolver_apelacion(
            apelacion_id=apelacion_id,
            moderador_id=int(current_user["id"]),
            aprobada=payload.aprobada,
            respuesta=payload.respuesta,
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# --- Endpoint de Usuario: Apelar sanción ---

@router.post("/sanciones/{sancion_id}/apelar", status_code=status.HTTP_201_CREATED, summary="Apelar sanción recibida (máximo 1 vez)")
async def apelar_sancion(
    sancion_id: int,
    payload: ApelarSancionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Permite al estudiante apelar una sanción activa en su contra."""
    try:
        res = await service.crear_apelacion(
            sancion_id=sancion_id,
            usuario_id=int(current_user["id"]),
            motivo=payload.motivo,
        )
        return res
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
