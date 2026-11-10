import asyncio
import hashlib
import hmac
import io
import json
import logging
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import sqlalchemy as sa
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from backend_estudiantil.adapters.db import (
    PublicacionORM,
    UserORM,
    VerificacionPublicacionORM,
    get_session_factory,
)
from backend_estudiantil.config.settings import settings
from backend_estudiantil.infrastructure.file_upload_security import (
    validar_imagen_segura,
    validar_ruta_segura,
)
from backend_estudiantil.infrastructure.security import get_current_user

# Módulo de IA — importación diferida para evitar error si PyTorch no está instalado
try:
    from backend_estudiantil.infrastructure.verificacion_ia import (
        verificar_imagen as _verificar_imagen_ia,
    )
    _IA_DISPONIBLE = True
except Exception as _ia_err:
    _IA_DISPONIBLE = False
    logger_init = logging.getLogger(__name__)
    logger_init.warning("Módulo de IA no disponible: %s", _ia_err)

from collections import defaultdict

router = APIRouter(prefix="/publicaciones", tags=["verificacion de libros"])
logger = logging.getLogger(__name__)
_verif_activation_locks = defaultdict(asyncio.Lock)

MAX_FOTO_BYTES = 8 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_INTENTOS_CODIGO = 5
TIEMPO_DESAFIO = timedelta(minutes=15)
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


class DesafioRead(BaseModel):
    verificacion_id: int
    codigo: str
    vence_en: datetime
    instrucciones: str


class EvidenciaRead(BaseModel):
    verificacion_id: int
    estado: str
    enviado_en: datetime
    mensaje: str
    ia_aprobado: bool | None = None
    ia_detalle: str | None = None
    ia_disponible: bool = False


class VerificacionEstadoRead(BaseModel):
    publicacion_id: int
    estado_publicacion: str
    estado_verificacion: str | None = None
    enviado_en: datetime | None = None
    nota_revision: str | None = None


class RevisionCreate(BaseModel):
    decision: Literal["aprobada", "rechazada"]
    nota: str = Field(..., min_length=3, max_length=1000)

    @field_validator("nota")
    @classmethod
    def validar_nota(cls, nota: str) -> str:
        nota = nota.strip()
        if len(nota) < 3:
            raise ValueError("La nota de revisión debe tener al menos 3 caracteres")
        return nota


class VerificacionPendienteRead(BaseModel):
    verificacion_id: int
    publicacion_id: int
    usuario_id: int
    titulo: str
    autor: str | None
    isbn: str | None
    enviado_en: datetime


def _es_revisor(usuario: dict) -> bool:
    return usuario.get("role") in ("admin", "administrador", "moderador")


def _hash_codigo(verificacion_id: int, codigo: str) -> str:
    mensaje = f"{verificacion_id}:{codigo}".encode()
    return hmac.new(settings.JWT_SECRET_KEY.encode(), mensaje, hashlib.sha256).hexdigest()


def _directorio_evidencia(verificacion_id: int) -> Path:
    base_dir = Path(settings.BOOK_VERIFICATION_STORAGE_PATH).resolve()
    target_dir = base_dir / str(int(verificacion_id))
    return validar_ruta_segura(base_dir, target_dir)


def _normalizar_imagen(datos: bytes, destino: Path) -> str:
    try:
        with Image.open(io.BytesIO(datos)) as imagen:
            if imagen.width * imagen.height > MAX_PIXELS:
                raise ValueError("La foto supera el límite de resolución permitido")
            imagen = ImageOps.exif_transpose(imagen).convert("RGB")
            imagen = ImageOps.contain(imagen, (2560, 2560), Image.Resampling.LANCZOS)
            destino.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                suffix=".jpg", dir=destino.parent, delete=False
            ) as temporal:
                ruta_temporal = Path(temporal.name)
            try:
                imagen.save(ruta_temporal, format="JPEG", quality=88, optimize=True)
                ruta_temporal.replace(destino)
            finally:
                ruta_temporal.unlink(missing_ok=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("El archivo debe ser una foto JPEG, PNG o WebP válida") from exc

    return hashlib.sha256(destino.read_bytes()).hexdigest()


async def _leer_foto(foto: UploadFile) -> bytes:
    datos = await foto.read(MAX_FOTO_BYTES + 1)
    if not datos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Debes adjuntar ambas fotos"
        )
    if len(datos) > MAX_FOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Cada foto debe pesar como máximo 8 MB",
        )
    # Validar que sea un archivo de imagen real
    validar_imagen_segura(datos, max_bytes=MAX_FOTO_BYTES)
    return datos


async def _obtener_verificacion_propietario(session, publicacion_id: int, usuario_id: int):
    result = await session.execute(
        select(PublicacionORM).where(PublicacionORM.id == publicacion_id)
    )
    publicacion = result.scalar_one_or_none()
    if publicacion is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if publicacion.usuario_id != usuario_id:
        raise HTTPException(status_code=403, detail="La publicación no te pertenece")
    return publicacion


@router.post(
    "/{publicacion_id}/verificacion/desafios",
    response_model=DesafioRead,
    status_code=status.HTTP_201_CREATED,
)
async def crear_desafio(
    publicacion_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Genera un código de un solo uso para fotografiar junto al libro."""
    usuario_id = int(current_user["id"])
    vence_en = datetime.now(timezone.utc) + TIEMPO_DESAFIO

    async with get_session_factory()() as session:
        from backend_estudiantil.domain.services.moderacion_sanciones_service import (
            usuario_puede_operar,
        )
        user_res = await session.execute(select(UserORM).where(UserORM.id == usuario_id))
        user_orm = user_res.scalar_one_or_none()
        res_op = usuario_puede_operar(user_orm)
        if not res_op.puede_operar:
            fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
            )

        publicacion = await _obtener_verificacion_propietario(
            session, publicacion_id, usuario_id
        )
        if publicacion.estado_publicacion == "activa":
            raise HTTPException(status_code=409, detail="El libro ya está verificado")

        result = await session.execute(
            select(VerificacionPublicacionORM)
            .where(
                VerificacionPublicacionORM.publicacion_id == publicacion_id,
                VerificacionPublicacionORM.estado == "pendiente_revision",
            )
            .limit(1)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail="La evidencia ya está pendiente de revisión"
            )

        result = await session.execute(
            select(VerificacionPublicacionORM).where(
                VerificacionPublicacionORM.publicacion_id == publicacion_id,
                VerificacionPublicacionORM.estado == "desafio",
            )
        )
        for desafio_anterior in result.scalars():
            desafio_anterior.estado = "expirado"

        codigo = secrets.token_hex(4).upper()
        verificacion = VerificacionPublicacionORM(
            publicacion_id=publicacion_id,
            usuario_id=usuario_id,
            codigo_hash="",
            estado="desafio",
            vence_en=vence_en,
        )
        session.add(verificacion)
        await session.flush()
        verificacion.codigo_hash = _hash_codigo(verificacion.id, codigo)
        await session.commit()

    return DesafioRead(
        verificacion_id=verificacion.id,
        codigo=codigo,
        vence_en=vence_en,
        instrucciones=(
            "Escribe este código en una hoja y toma dos fotos nuevas: una de la portada "
            "y otra de la página legal donde aparece el ISBN. El código debe leerse "
            "claramente en ambas fotos. El código vence en 15 minutos."
        ),
    )


@router.post(
    "/{publicacion_id}/verificacion/evidencias",
    response_model=EvidenciaRead,
    status_code=status.HTTP_201_CREATED,
)
async def enviar_evidencia(
    publicacion_id: int,
    verificacion_id: int = Form(..., gt=0),
    codigo: str = Form(..., min_length=8, max_length=8),
    foto_portada: UploadFile = File(...),
    foto_pagina_isbn: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Recibe dos fotos privadas y las deja en cola de revisión humana."""
    portada_bytes, isbn_bytes = await asyncio.gather(
        _leer_foto(foto_portada), _leer_foto(foto_pagina_isbn)
    )
    usuario_id = int(current_user["id"])
    ahora = datetime.now(timezone.utc)

    async with get_session_factory()() as session:
        from backend_estudiantil.domain.services.moderacion_sanciones_service import (
            usuario_puede_operar,
        )
        user_res = await session.execute(select(UserORM).where(UserORM.id == usuario_id))
        user_orm = user_res.scalar_one_or_none()
        res_op = usuario_puede_operar(user_orm)
        if not res_op.puede_operar:
            fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
            )

        await _obtener_verificacion_propietario(
            session, publicacion_id, usuario_id
        )
        result = await session.execute(
            select(VerificacionPublicacionORM)
            .where(
                VerificacionPublicacionORM.id == verificacion_id,
                VerificacionPublicacionORM.publicacion_id == publicacion_id,
                VerificacionPublicacionORM.usuario_id == usuario_id,
            )
            .with_for_update()
        )
        verificacion = result.scalar_one_or_none()
        if verificacion is None or verificacion.estado != "desafio":
            raise HTTPException(status_code=404, detail="Desafío no encontrado o ya utilizado")

        vence_en = verificacion.vence_en
        if vence_en.tzinfo is None:
            vence_en = vence_en.replace(tzinfo=timezone.utc)
        if ahora >= vence_en:
            verificacion.estado = "expirado"
            await session.commit()
            raise HTTPException(status_code=400, detail="El desafío venció; genera uno nuevo")

        if not hmac.compare_digest(
            verificacion.codigo_hash, _hash_codigo(verificacion.id, codigo.upper())
        ):
            verificacion.intentos_codigo += 1
            if verificacion.intentos_codigo >= MAX_INTENTOS_CODIGO:
                verificacion.estado = "bloqueado"
            await session.commit()
            raise HTTPException(status_code=400, detail="El código de verificación no coincide")

        base = _directorio_evidencia(verificacion.id)
        portada_destino = base / "portada.jpg"
        isbn_destino = base / "pagina-isbn.jpg"
        try:
            portada_hash, isbn_hash = await asyncio.gather(
                asyncio.to_thread(_normalizar_imagen, portada_bytes, portada_destino),
                asyncio.to_thread(_normalizar_imagen, isbn_bytes, isbn_destino),
            )
        except ValueError as exc:
            portada_destino.unlink(missing_ok=True)
            isbn_destino.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        verificacion.portada_path = str(portada_destino)
        verificacion.pagina_isbn_path = str(isbn_destino)
        verificacion.portada_sha256 = portada_hash
        verificacion.pagina_isbn_sha256 = isbn_hash
        verificacion.estado = "pendiente_revision"
        verificacion.enviado_en = ahora

        # ── Análisis con Red Neuronal ──────────────────────────────────────────
        resultado_ia = None
        ia_aprobado = None
        ia_detalle = None

        if _IA_DISPONIBLE:
            try:
                resultado_ia = await asyncio.to_thread(
                    _verificar_imagen_ia,
                    portada_bytes,      # Analizar foto de portada
                    codigo,
                )
                ia_aprobado = resultado_ia["aprobado"]
                ia_detalle = resultado_ia["detalle"]

                # Guardar resultado como JSON en nota_revision
                verificacion.nota_revision = json.dumps({
                    "ia": resultado_ia,
                    "auto": True,
                }, ensure_ascii=False)

                if ia_aprobado:
                    # La IA aprueba automáticamente — activar publicación
                    logger.info(
                        "IA aprobó automáticamente la verificacion_id=%s", verificacion.id
                    )
                    verificacion.estado = "aprobada"
                    verificacion.revisado_en = ahora
                    verificacion.nota_revision = json.dumps({
                        "ia": resultado_ia,
                        "auto": True,
                        "aprobado_automaticamente": True,
                    }, ensure_ascii=False)

                    # Activar la publicación si no supera el límite de activas
                    result_pub = await session.execute(
                        sa.select(PublicacionORM).where(
                            PublicacionORM.id == publicacion_id
                        )
                    )
                    pub = result_pub.scalar_one_or_none()
                    if pub:
                        user_res = await session.execute(
                            sa.select(UserORM).where(UserORM.id == pub.usuario_id)
                        )
                        owner = user_res.scalar_one_or_none()
                        limite = (
                            settings.LIMITE_PUBLICACIONES_VERIFICADOS
                            if (owner and owner.verificado_comunidad)
                            else settings.LIMITE_PUBLICACIONES_SIN_VERIFICAR
                        )
                        count_res = await session.execute(
                            sa.select(sa.func.count(PublicacionORM.id)).where(
                                PublicacionORM.usuario_id == pub.usuario_id,
                                sa.cast(PublicacionORM.estado_publicacion, sa.String) == "activa",
                            )
                        )
                        activas_actuales = count_res.scalar_one() or 0
                        if activas_actuales < limite:
                            pub.estado_publicacion = "activa"
                        else:
                            logger.warning(
                                "IA verificó publicación %s pero el usuario %s tiene %s activas (límite: %s)",
                                pub.id, pub.usuario_id, activas_actuales, limite
                            )
                else:
                    logger.info(
                        "IA rechazó — queda pendiente revision humana. Detalle: %s", ia_detalle
                    )
            except Exception as exc:
                logger.error("Error ejecutando IA: %s", exc)
                # Fallo de IA no bloquea el flujo: queda en pendiente_revision
        # ──────────────────────────────────────────────────────────────────────

        try:
            await session.commit()
        except Exception:
            portada_destino.unlink(missing_ok=True)
            isbn_destino.unlink(missing_ok=True)
            raise

    estado_final = verificacion.estado
    if estado_final == "aprobada":
        mensaje = (
            "La IA verificó tu libro exitosamente. "
            "Tu publicación ya está activa en el catálogo."
        )
    else:
        mensaje = "Fotos recibidas. El libro no aparecerá en el catálogo hasta su aprobación."
        if ia_detalle and ia_aprobado is False:
            mensaje += f" Motivo IA: {ia_detalle}"

    return EvidenciaRead(
        verificacion_id=verificacion.id,
        estado=estado_final,
        enviado_en=ahora,
        mensaje=mensaje,
        ia_aprobado=ia_aprobado,
        ia_detalle=ia_detalle,
        ia_disponible=_IA_DISPONIBLE,
    )


@router.get(
    "/{publicacion_id}/verificacion",
    response_model=VerificacionEstadoRead,
)
async def estado_verificacion(
    publicacion_id: int,
    current_user: dict = Depends(get_current_user),
):
    async with get_session_factory()() as session:
        publicacion = await _obtener_verificacion_propietario(
            session, publicacion_id, int(current_user["id"])
        )
        result = await session.execute(
            select(VerificacionPublicacionORM)
            .where(VerificacionPublicacionORM.publicacion_id == publicacion_id)
            .order_by(VerificacionPublicacionORM.id.desc())
            .limit(1)
        )
        verificacion = result.scalar_one_or_none()

    return VerificacionEstadoRead(
        publicacion_id=publicacion.id,
        estado_publicacion=publicacion.estado_publicacion,
        estado_verificacion=verificacion.estado if verificacion else None,
        enviado_en=verificacion.enviado_en if verificacion else None,
        nota_revision=verificacion.nota_revision if verificacion else None,
    )


@router.get("/verificaciones/pendientes", response_model=list[VerificacionPendienteRead])
async def listar_verificaciones_pendientes(
    current_user: dict = Depends(get_current_user),
):
    if not _es_revisor(current_user):
        raise HTTPException(status_code=403, detail="Solo moderación puede revisar libros")

    async with get_session_factory()() as session:
        result = await session.execute(
            select(
                VerificacionPublicacionORM,
                PublicacionORM.titulo,
                PublicacionORM.autor,
                PublicacionORM.isbn,
            )
            .join(
                PublicacionORM,
                PublicacionORM.id == VerificacionPublicacionORM.publicacion_id,
            )
            .where(VerificacionPublicacionORM.estado == "pendiente_revision")
            .order_by(VerificacionPublicacionORM.enviado_en.asc())
            .limit(100)
        )
        return [
            VerificacionPendienteRead(
                verificacion_id=verification.id,
                publicacion_id=verification.publicacion_id,
                usuario_id=verification.usuario_id,
                titulo=titulo,
                autor=autor,
                isbn=isbn,
                enviado_en=verification.enviado_en,
            )
            for verification, titulo, autor, isbn in result.all()
        ]


@router.get("/verificaciones/{verificacion_id}/evidencia/{tipo}")
async def obtener_foto_evidencia(
    verificacion_id: int,
    tipo: Literal["portada", "pagina-isbn"],
    current_user: dict = Depends(get_current_user),
):
    async with get_session_factory()() as session:
        result = await session.execute(
            select(VerificacionPublicacionORM).where(
                VerificacionPublicacionORM.id == verificacion_id
            )
        )
        verificacion = result.scalar_one_or_none()
        if verificacion is None:
            raise HTTPException(status_code=404, detail="Evidencia no encontrada")
        if not _es_revisor(current_user) and int(current_user["id"]) != verificacion.usuario_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a estas fotos")
        ruta = verificacion.portada_path if tipo == "portada" else verificacion.pagina_isbn_path

    if not ruta:
        raise HTTPException(status_code=404, detail="Foto todavía no enviada")
    archivo = Path(ruta).resolve()
    if not archivo.is_relative_to(Path(settings.BOOK_VERIFICATION_STORAGE_PATH).resolve()):
        logger.error("Ruta de evidencia fuera del almacenamiento privado: %s", archivo)
        raise HTTPException(status_code=500, detail="No se pudo localizar la foto")
    return FileResponse(archivo, media_type="image/jpeg")


@router.post("/verificaciones/{verificacion_id}/revision")
async def revisar_verificacion(
    verificacion_id: int,
    payload: RevisionCreate,
    current_user: dict = Depends(get_current_user),
):
    if not _es_revisor(current_user):
        raise HTTPException(status_code=403, detail="Solo moderación puede revisar libros")

    async with get_session_factory()() as session:
        result = await session.execute(
            select(VerificacionPublicacionORM)
            .where(VerificacionPublicacionORM.id == verificacion_id)
            .with_for_update()
        )
        verificacion = result.scalar_one_or_none()
        if verificacion is None:
            raise HTTPException(status_code=404, detail="Verificación no encontrada")
        if verificacion.estado != "pendiente_revision":
            raise HTTPException(status_code=409, detail="La evidencia ya fue revisada")

        result = await session.execute(
            select(PublicacionORM).where(
                PublicacionORM.id == verificacion.publicacion_id
            )
        )
        publicacion = result.scalar_one_or_none()
        if publicacion is None:
            raise HTTPException(status_code=404, detail="Publicación no encontrada")

        async with _verif_activation_locks[publicacion.usuario_id]:
            if payload.decision == "aprobada" and publicacion.estado_publicacion != "activa":
                user_res = await session.execute(
                    sa.select(UserORM).where(UserORM.id == publicacion.usuario_id)
                )
                owner = user_res.scalar_one_or_none()
                limite = (
                    settings.LIMITE_PUBLICACIONES_VERIFICADOS
                    if (owner and owner.verificado_comunidad)
                    else settings.LIMITE_PUBLICACIONES_SIN_VERIFICAR
                )
                count_res = await session.execute(
                    sa.select(sa.func.count(PublicacionORM.id)).where(
                        PublicacionORM.usuario_id == publicacion.usuario_id,
                        sa.cast(PublicacionORM.estado_publicacion, sa.String) == "activa",
                    )
                )
                activas_actuales = count_res.scalar_one() or 0
                if activas_actuales >= limite:
                    raise HTTPException(
                        status_code=400,
                        detail=f"El autor ha alcanzado el límite máximo de {limite} publicaciones activas permitidas para su nivel de verificación.",
                    )

            verificacion.estado = payload.decision
            verificacion.revisado_por_id = int(current_user["id"])
            verificacion.revisado_en = datetime.now(timezone.utc)
            verificacion.nota_revision = payload.nota.strip()
            publicacion.estado_publicacion = (
                "activa" if payload.decision == "aprobada" else "inactiva"
            )
            await session.commit()

    return {
        "verificacion_id": verificacion_id,
        "estado": verificacion.estado,
        "estado_publicacion": publicacion.estado_publicacion,
    }
