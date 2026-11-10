
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend_estudiantil.adapters.db.sqlalchemy_calificacion_repository import (
    SQLAlchemyCalificacionRepository,
)
from backend_estudiantil.adapters.db.sqlalchemy_trueque_repository import (
    SQLAlchemyTruequeRepository,
)
from backend_estudiantil.domain.services.calificacion_service import CalificacionService
from backend_estudiantil.infrastructure.security import get_current_user
from backend_estudiantil.schemas.trueque import (
    CalificacionCreate,
    CalificacionRead,
    ReputacionRead,
)

router = APIRouter(prefix="/calificaciones", tags=["calificaciones"])


def get_calificacion_service() -> CalificacionService:
    return CalificacionService(
        calificacion_repo=SQLAlchemyCalificacionRepository(),
        trueque_repo=SQLAlchemyTruequeRepository(),
    )


def _calificacion_to_read(c) -> CalificacionRead:
    return CalificacionRead(
        id=c.id,
        trueque_id=c.trueque_id,
        usuario_califica_id=c.usuario_califica_id,
        usuario_calificado_id=c.usuario_calificado_id,
        estrellas=c.estrellas,
        resena=c.resena,
        fecha_calificacion=c.fecha_calificacion,
    )


@router.post(
    "/trueques/{trueque_id}",
    response_model=CalificacionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Calificar un trueque",
)
async def calificar_trueque(
    trueque_id: int,
    payload: CalificacionCreate,
    current_user: dict = Depends(get_current_user),
    service: CalificacionService = Depends(get_calificacion_service),
):
    """
    Califica al otro participante de un trueque completado.
    Solo se puede calificar una vez por trueque y solo si ya está completado.
    """
    try:
        calificacion = await service.calificar_trueque(
            trueque_id=trueque_id,
            usuario_califica_id=current_user["id"],
            usuario_calificado_id=payload.usuario_calificado_id,
            estrellas=payload.estrellas,
            resena=payload.resena,
        )
        return _calificacion_to_read(calificacion)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/reputacion/{usuario_id}",
    response_model=ReputacionRead,
    summary="Reputación de un usuario",
)
async def obtener_reputacion(
    usuario_id: int,
    service: CalificacionService = Depends(get_calificacion_service),
):
    """Retorna la reputación (promedio de estrellas) de un usuario basada en sus calificaciones recibidas."""
    reputacion = await service.obtener_reputacion_usuario(usuario_id)
    return reputacion


@router.get(
    "/mis-calificaciones",
    response_model=list[CalificacionRead],
    summary="Mis calificaciones recibidas",
)
async def mis_calificaciones(
    current_user: dict = Depends(get_current_user),
    service: CalificacionService = Depends(get_calificacion_service),
):
    """Retorna todas las calificaciones recibidas por el usuario autenticado."""
    calificaciones = await service.listar_calificaciones_usuario(current_user["id"])
    return [_calificacion_to_read(c) for c in calificaciones]


class ReportarCalificacionRequest(BaseModel):
    motivo: str


@router.post(
    "/{calificacion_id}/reportar",
    status_code=status.HTTP_201_CREATED,
    summary="Reportar una reseña o calificación para revisión de moderación",
)
async def reportar_calificacion(
    calificacion_id: int,
    payload: ReportarCalificacionRequest,
    current_user: dict = Depends(get_current_user),
    service: CalificacionService = Depends(get_calificacion_service),
):
    """Permite a un usuario autenticado reportar una reseña indebida o falsa."""
    if not payload.motivo or not payload.motivo.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El motivo del reporte es obligatorio")

    calificacion = await service.calificacion_repo.get_by_id(calificacion_id)
    if not calificacion:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calificación no encontrada")

    from backend_estudiantil.adapters.db import ReporteORM, get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        reporte = ReporteORM(
            reportante_id=int(current_user["id"]),
            objetivo_id=calificacion_id,
            tipo_objetivo="calificacion",
            motivo=payload.motivo.strip(),
            estado="pendiente",
        )
        session.add(reporte)
        await session.commit()
        await session.refresh(reporte)

    return {
        "mensaje": "Reseña reportada exitosamente. Será revisada por nuestro equipo de moderación.",
        "reporte_id": reporte.id,
        "calificacion_id": calificacion_id,
        "estado": "pendiente",
    }

