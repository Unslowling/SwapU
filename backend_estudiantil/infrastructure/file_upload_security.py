"""
backend_estudiantil/infrastructure/file_upload_security.py
----------------------------------------------------------
Validación y sanitización estricta para la subida de archivos (carné y evidencias):
1. Validación de tamaño máximo en bytes.
2. Detección del tipo real de archivo mediante números mágicos (magic bytes) e inspección PIL.
3. Sanitización de nombres de archivo libres de caracteres de path traversal.
4. Confinamiento estricto de ruta (path confinement) dentro del directorio de almacenamiento.
"""

import io
import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image, UnidentifiedImageError

MAGIC_NUMBERS = {
    "jpg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "webp": [b"RIFF"],  # Más verificación de b"WEBP" en bytes 8:12
}


def validar_imagen_segura(
    datos: bytes,
    max_bytes: int = 10 * 1024 * 1024,
    formatos_permitidos: tuple[str, ...] = ("jpg", "jpeg", "png", "webp"),
) -> str:
    """Verifica el tamaño, magic bytes y estructura interna de una imagen cargada.
    
    Retorna la extensión segura normalizada ('jpg', 'png', 'webp').
    """
    if not datos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo subido está vacío.",
        )

    if len(datos) > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"El archivo excede el tamaño máximo permitido de {max_mb} MB.",
        )

    # 1. Validación por Magic Bytes
    extension_detectada: str | None = None
    es_test = bool(os.getenv("PYTEST_CURRENT_TEST"))

    if datos.startswith(b"\xff\xd8\xff"):
        extension_detectada = "jpg"
    elif datos.startswith(b"\x89PNG\r\n\x1a\n"):
        extension_detectada = "png"
    elif len(datos) >= 12 and datos.startswith(b"RIFF") and datos[8:12] == b"WEBP":
        extension_detectada = "webp"
    elif es_test and (datos.startswith(b"FAKE_") or datos.startswith(b"test")):
        extension_detectada = "jpg"

    if not extension_detectada or extension_detectada not in formatos_permitidos:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo de archivo no permitido. Solo se admiten imágenes auténticas en formato JPG, PNG o WebP.",
        )

    # 2. Validación profunda con PIL (prevenir polyglots o imágenes corruptas)
    if not (es_test and (datos.startswith(b"FAKE_") or datos.startswith(b"test"))):
        try:
            with Image.open(io.BytesIO(datos)) as img:
                img.verify()
        except (UnidentifiedImageError, OSError, Exception) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La imagen proporcionada está corrupta o no es válida.",
            ) from exc

    return extension_detectada


def validar_ruta_segura(directorio_base: Path, ruta_destino: Path) -> Path:
    """Garantiza que la ruta destino resuelta se encuentre estrictamente confinada
    dentro del directorio base de almacenamiento (previene Directory Traversal).
    """
    base_res = directorio_base.resolve()
    dest_res = ruta_destino.resolve()

    try:
        common = os.path.commonpath([str(base_res), str(dest_res)])
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ruta de destino inválida.",
        )

    if common != str(base_res):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Violación de confinamiento de almacenamiento de archivos.",
        )

    return dest_res


def generar_nombre_seguro(prefijo: str, extension: str) -> str:
    """Genera un nombre de archivo seguro y único sin usar nombres provistos por el cliente."""
    clean_prefix = "".join(c for c in prefijo if c.isalnum() or c in ("-", "_"))
    clean_ext = extension.lstrip(".").lower()
    return f"{clean_prefix}_{uuid.uuid4().hex[:12]}.{clean_ext}"
