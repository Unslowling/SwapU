import asyncio
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend_estudiantil.adapters.db.sqlalchemy_publicacion_repository import (
    SQLAlchemyPublicacionRepository,
)
from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.services.moderacion_sanciones_service import (
    usuario_puede_operar,
)
from backend_estudiantil.domain.services.publicacion_service import PublicacionService
from backend_estudiantil.infrastructure.security import get_current_user
from backend_estudiantil.schemas.publicacion import (
    PublicacionCreate,
    PublicacionRead,
    PublicacionUpdate,
)

router = APIRouter(prefix="/publicaciones", tags=["publicaciones"])
_pub_user_locks = defaultdict(asyncio.Lock)


def get_publicacion_service() -> PublicacionService:
    return PublicacionService(SQLAlchemyPublicacionRepository())


def _pub_to_read(pub) -> PublicacionRead:
    return PublicacionRead(
        id=pub.id,
        usuario_id=pub.usuario_id,
        titulo=pub.titulo,
        autor=pub.autor,
        isbn=pub.isbn,
        edicion=pub.edicion,
        categoria_id=pub.categoria_id,
        estado_libro=pub.estado_libro,
        descripcion=pub.descripcion,
        libro_buscado=pub.libro_buscado,
        estado_publicacion=pub.estado_publicacion,
        fecha_publicacion=pub.fecha_publicacion,
        tipo_transaccion=getattr(pub, "tipo_transaccion", "trueque") or "trueque",
        fecha_devolucion=getattr(pub, "fecha_devolucion", None),
        organizacion_id=getattr(pub, "organizacion_id", None),
        usuario_nombre=getattr(pub, "usuario_nombre", None),
        usuario_carrera=getattr(pub, "usuario_carrera", None),
        usuario_universidad=getattr(pub, "usuario_universidad", None),
        usuario_avatar=getattr(pub, "usuario_avatar", None),
        categoria_nombre=getattr(pub, "categoria_nombre", None),
    )


@router.get("/", response_model=list[PublicacionRead], summary="Listar publicaciones activas")
async def listar_publicaciones(
    skip: int = Query(0, ge=0, description="Número de registros a omitir"),
    limit: int = Query(20, ge=1, le=100, description="Máximo de registros a retornar"),
    categoria_id: int | None = Query(None, description="Filtrar por categoría"),
    busqueda: str | None = Query(None, description="Buscar por título, autor o libro buscado"),
    organizacion_id: int | None = Query(None, description="Filtrar por organización"),
    service: PublicacionService = Depends(get_publicacion_service),
):
    """Retorna el listado de publicaciones activas. Permite filtrar por categoría, búsqueda y organización."""
    pubs = await service.listar_publicaciones(
        skip=skip,
        limit=limit,
        categoria_id=categoria_id,
        busqueda=busqueda,
        organizacion_id=organizacion_id,
    )
    return [_pub_to_read(p) for p in pubs]


@router.get("/mis-publicaciones", response_model=list[PublicacionRead], summary="Mis publicaciones")
async def mis_publicaciones(
    current_user: dict = Depends(get_current_user),
    service: PublicacionService = Depends(get_publicacion_service),
):
    """Retorna todas las publicaciones del usuario autenticado."""
    pubs = await service.listar_por_usuario(current_user["id"])
    return [_pub_to_read(p) for p in pubs]


@router.get("/{publicacion_id}", response_model=PublicacionRead, summary="Detalle de publicación")
async def obtener_publicacion(
    publicacion_id: int,
    service: PublicacionService = Depends(get_publicacion_service),
):
    """Retorna el detalle de una publicación por su ID."""
    try:
        pub = await service.obtener_publicacion(publicacion_id)
        return _pub_to_read(pub)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("", response_model=PublicacionRead, status_code=status.HTTP_201_CREATED, summary="Crear publicación")
@router.post("/", response_model=PublicacionRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def crear_publicacion(
    payload: PublicacionCreate,
    current_user: dict = Depends(get_current_user),
    service: PublicacionService = Depends(get_publicacion_service),
):
    """Crea una nueva publicación de libro o material académico para intercambio."""
    user = await SQLAlchemyUserRepository().get_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    res_op = usuario_puede_operar(user)
    if not res_op.puede_operar:
        fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
        )

    # Límite de publicaciones activas por nivel (3 sin verificar y 10 verificados) con lock de concurrencia
    async with _pub_user_locks[user.id]:
        limite = (
            settings.LIMITE_PUBLICACIONES_VERIFICADOS
            if user.verificado_comunidad
            else settings.LIMITE_PUBLICACIONES_SIN_VERIFICAR
        )
        pubs_activas = await service.repo.count_activas_by_usuario(user.id)
        if pubs_activas >= limite:
            mensaje = f"Has alcanzado el límite máximo de {limite} publicaciones activas permitidas para tu nivel de verificación (tienes {pubs_activas} activas)."
            if not user.verificado_comunidad:
                mensaje += f" Verificando tu condición de estudiante tu límite sube a {settings.LIMITE_PUBLICACIONES_VERIFICADOS}."
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=mensaje,
            )

        try:
            pub = await service.crear_publicacion(
                usuario_id=current_user["id"],
                titulo=payload.titulo,
                autor=payload.autor,
                isbn=payload.isbn,
                edicion=payload.edicion,
                categoria_id=payload.categoria_id,
                estado_libro=payload.estado_libro,
                descripcion=payload.descripcion,
                libro_buscado=payload.libro_buscado,
                tipo_transaccion=payload.tipo_transaccion,
                fecha_devolucion=payload.fecha_devolucion,
                organizacion_id=payload.organizacion_id or getattr(user, "organizacion_id", None),
            )
            return _pub_to_read(pub)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{publicacion_id}", response_model=PublicacionRead, summary="Actualizar publicación")
async def actualizar_publicacion(
    publicacion_id: int,
    payload: PublicacionUpdate,
    current_user: dict = Depends(get_current_user),
    service: PublicacionService = Depends(get_publicacion_service),
):
    """Actualiza los datos de una publicación. Solo el autor puede modificarla."""
    user = await SQLAlchemyUserRepository().get_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    res_op = usuario_puede_operar(user)
    if not res_op.puede_operar:
        fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
        )

    try:
        datos = payload.model_dump(exclude_none=True)
        pub = await service.actualizar_publicacion(publicacion_id, current_user["id"], datos)
        return _pub_to_read(pub)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{publicacion_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar publicación")
async def eliminar_publicacion(
    publicacion_id: int,
    current_user: dict = Depends(get_current_user),
    service: PublicacionService = Depends(get_publicacion_service),
):
    """Elimina una publicación. Solo el autor puede eliminarla."""
    user = await SQLAlchemyUserRepository().get_by_id(current_user["id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

    res_op = usuario_puede_operar(user)
    if not res_op.puede_operar:
        fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
        )

    try:
        await service.eliminar_publicacion(publicacion_id, current_user["id"])
        return
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
