
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend_estudiantil.adapters.db.sqlalchemy_trueque_repository import (
    SQLAlchemyTruequeRepository,
)
from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from backend_estudiantil.domain.services.trueque_service import TruequeService
from backend_estudiantil.infrastructure.security import get_current_user
from backend_estudiantil.schemas.trueque import TruequeCreate, TruequeRead

router = APIRouter(prefix="/trueques", tags=["trueques"])


def get_trueque_service() -> TruequeService:
    return TruequeService(SQLAlchemyTruequeRepository())


def _trueque_to_read(t) -> TruequeRead:
    return TruequeRead(
        id=t.id,
        match_id=t.match_id,
        usuario_propone_id=t.usuario_propone_id,
        usuario_recibe_id=t.usuario_recibe_id,
        estado=t.estado,
        fecha_propuesta=t.fecha_propuesta,
        fecha_confirmacion=t.fecha_confirmacion,
        fecha_completado=t.fecha_completado,
    )


@router.get("/mis-trueques", response_model=list[TruequeRead], summary="Mis trueques")
async def mis_trueques(
    estado: str | None = Query(None, description="Filtrar por estado: propuesto, confirmado, completado, rechazado"),
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(50, ge=1, le=100, description="Límite de registros a retornar"),
    current_user: dict = Depends(get_current_user),
    service: TruequeService = Depends(get_trueque_service),
):
    """Retorna todos los trueques en los que participa el usuario autenticado con paginación."""
    try:
        trueques = await service.listar_trueques_usuario(current_user["id"], estado=estado, skip=skip, limit=limit)
        return [_trueque_to_read(t) for t in trueques]
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{trueque_id}", response_model=TruequeRead, summary="Detalle de trueque")
async def obtener_trueque(
    trueque_id: int,
    current_user: dict = Depends(get_current_user),
    service: TruequeService = Depends(get_trueque_service),
):
    """Retorna el detalle de un trueque por su ID."""
    try:
        trueque = await service.obtener_trueque(trueque_id)
        # Solo los participantes pueden ver el trueque
        if current_user["id"] not in (trueque.usuario_propone_id, trueque.usuario_recibe_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso no autorizado a este trueque")
        return _trueque_to_read(trueque)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/", response_model=TruequeRead, status_code=status.HTTP_201_CREATED, summary="Proponer trueque")
@router.post(
    "/proponer",
    response_model=TruequeRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def proponer_trueque(
    payload: TruequeCreate,
    current_user: dict = Depends(get_current_user),
    service: TruequeService = Depends(get_trueque_service),
):
    """Propone un nuevo trueque a otro usuario."""
    user = await SQLAlchemyUserRepository().get_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    from backend_estudiantil.domain.services.moderacion_sanciones_service import (
        usuario_puede_operar,
    )
    res_op = usuario_puede_operar(user)
    if not res_op.puede_operar:
        fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
        )

    try:
        trueque = await service.proponer_trueque(
            usuario_propone_id=current_user["id"],
            usuario_recibe_id=payload.usuario_recibe_id,
            match_id=payload.match_id,
            publicacion_origen_id=payload.publicacion_origen_id,
            publicacion_destino_id=payload.publicacion_destino_id,
        )
        return _trueque_to_read(trueque)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{trueque_id}/confirmar", response_model=TruequeRead, summary="Confirmar trueque")
async def confirmar_trueque(
    trueque_id: int,
    current_user: dict = Depends(get_current_user),
    service: TruequeService = Depends(get_trueque_service),
):
    """El usuario receptor confirma la propuesta de trueque."""
    try:
        trueque = await service.confirmar_trueque(trueque_id, current_user["id"])
        return _trueque_to_read(trueque)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{trueque_id}/completar", response_model=TruequeRead, summary="Completar trueque")
async def completar_trueque(
    trueque_id: int,
    current_user: dict = Depends(get_current_user),
    service: TruequeService = Depends(get_trueque_service),
):
    """Marca el trueque como completado (intercambio realizado)."""
    try:
        trueque = await service.completar_trueque(trueque_id, current_user["id"])
        return _trueque_to_read(trueque)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/{trueque_id}/rechazar", response_model=TruequeRead, summary="Rechazar trueque")
async def rechazar_trueque(
    trueque_id: int,
    current_user: dict = Depends(get_current_user),
    service: TruequeService = Depends(get_trueque_service),
):
    """Rechaza una propuesta de trueque."""
    try:
        trueque = await service.rechazar_trueque(trueque_id, current_user["id"])
        return _trueque_to_read(trueque)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
