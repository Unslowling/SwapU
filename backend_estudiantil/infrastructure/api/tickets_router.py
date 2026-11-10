from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from backend_estudiantil.adapters.db import (
    VerificacionPublicacionORM,
    get_session_factory,
)
from backend_estudiantil.domain.services.ticket_service import TicketService
from backend_estudiantil.infrastructure.security import get_current_user
from backend_estudiantil.schemas.ticket import (
    TicketCreate,
    TicketDetalleRead,
    TicketEstadoUpdate,
    TicketMensajeCreate,
    TicketMensajeRead,
    TicketRead,
)

router = APIRouter(prefix="/tickets", tags=["tickets de revision"])
service = TicketService()


def _es_revisor(usuario: dict) -> bool:
    rol = usuario.get("role") or usuario.get("rol")
    return rol in ("admin", "administrador", "moderador")


@router.post(
    "",
    response_model=TicketDetalleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un ticket de comunicación/revisión",
)
@router.post(
    "/",
    response_model=TicketDetalleRead,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def crear_ticket(
    payload: TicketCreate,
    current_user: dict = Depends(get_current_user),
):
    """Abre un canal de comunicación (ticket) entre el moderador y el estudiante para una publicación."""
    try:
        return await service.crear_ticket(
            publicacion_id=payload.publicacion_id,
            asunto=payload.asunto,
            mensaje_inicial=payload.mensaje_inicial,
            usuario_actual=current_user,
            prioridad=payload.prioridad,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get(
    "",
    response_model=list[TicketRead],
    summary="Listar tickets (panel de moderación o usuario)",
)
@router.get(
    "/",
    response_model=list[TicketRead],
    include_in_schema=False,
)
async def listar_tickets(
    estado: str | None = Query(None, description="Filtrar por estado: abierto, en_revision, esperando_estudiante, resuelto, cerrado"),
    publicacion_id: int | None = Query(None, description="Filtrar por ID de publicación"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Retorna los tickets. Si el usuario es moderador/admin, ve todos; si es estudiante, solo los suyos."""
    return await service.listar_tickets(
        usuario_actual=current_user,
        solo_mis_tickets=not _es_revisor(current_user),
        estado=estado,
        publicacion_id=publicacion_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/mis-tickets",
    response_model=list[TicketRead],
    summary="Listar mis tickets de revisión (estudiante)",
)
async def listar_mis_tickets(
    estado: str | None = Query(None, description="Filtrar por estado"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """Retorna exclusivamente los tickets pertenecientes al estudiante autenticado."""
    return await service.listar_tickets(
        usuario_actual=current_user,
        solo_mis_tickets=True,
        estado=estado,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/publicacion/{publicacion_id}",
    response_model=list[TicketRead],
    summary="Listar tickets de una publicación específica",
)
async def listar_tickets_publicacion(
    publicacion_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Retorna los tickets asociados a una publicación."""
    return await service.listar_tickets(
        usuario_actual=current_user,
        solo_mis_tickets=not _es_revisor(current_user),
        publicacion_id=publicacion_id,
    )


@router.get(
    "/{ticket_id}",
    response_model=TicketDetalleRead,
    summary="Obtener detalle de ticket con su historial de mensajes",
)
async def obtener_ticket(
    ticket_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Retorna el detalle completo del ticket y la conversación."""
    try:
        return await service.obtener_ticket_detalle(ticket_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post(
    "/{ticket_id}/mensajes",
    response_model=TicketMensajeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Responder en el ticket (estudiante o moderador)",
)
async def enviar_mensaje_ticket(
    ticket_id: int,
    payload: TicketMensajeCreate,
    current_user: dict = Depends(get_current_user),
):
    """Agrega una nueva respuesta/mensaje a la conversación del ticket."""
    try:
        return await service.enviar_mensaje(
            ticket_id=ticket_id,
            contenido=payload.contenido,
            usuario_actual=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch(
    "/{ticket_id}/estado",
    response_model=TicketDetalleRead,
    summary="Actualizar estado del ticket (abierto, en_revision, esperando_estudiante, resuelto, cerrado)",
)
async def cambiar_estado_ticket(
    ticket_id: int,
    payload: TicketEstadoUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Modifica el estado de resolución del ticket."""
    try:
        return await service.cambiar_estado(
            ticket_id=ticket_id,
            nuevo_estado=payload.estado,
            usuario_actual=current_user,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post(
    "/desde-verificacion/{verificacion_id}",
    response_model=TicketDetalleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir o continuar ticket desde la cola de verificación de libros",
)
async def ticket_desde_verificacion(
    verificacion_id: int,
    payload: TicketMensajeCreate,
    current_user: dict = Depends(get_current_user),
):
    """Shortcut para moderadores: abre o responde un ticket para el libro en verificación."""
    if not _es_revisor(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo moderadores pueden usar este acceso rápido")

    async with get_session_factory()() as session:
        res = await session.execute(
            select(VerificacionPublicacionORM).where(VerificacionPublicacionORM.id == verificacion_id)
        )
        verif = res.scalar_one_or_none()
        if not verif:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verificación no encontrada")
        pub_id = verif.publicacion_id

    # Buscar si ya existe un ticket abierto para esta publicación
    tickets_existentes = await service.listar_tickets(
        usuario_actual=current_user,
        publicacion_id=pub_id,
        limit=5,
    )
    ticket_abierto = next((t for t in tickets_existentes if t.estado not in ("cerrado", "resuelto")), None)

    if ticket_abierto:
        # Enviar mensaje al ticket existente
        await service.enviar_mensaje(
            ticket_id=ticket_abierto.id,
            contenido=payload.contenido,
            usuario_actual=current_user,
        )
        return await service.obtener_ticket_detalle(ticket_abierto.id, current_user)
    else:
        # Crear nuevo ticket
        return await service.crear_ticket(
            publicacion_id=pub_id,
            asunto="Revisión de verificación de libro",
            mensaje_inicial=payload.contenido,
            usuario_actual=current_user,
            prioridad="alta",
        )

