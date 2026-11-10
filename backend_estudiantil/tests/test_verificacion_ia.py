import io
import pytest
from PIL import Image, ImageDraw
from backend_estudiantil.infrastructure.verificacion_ia import (
    _codigo_presente,
    verificar_imagen,
)

pytestmark = pytest.mark.unit


def test_codigo_presente_exacto():
    assert _codigo_presente("A8D4F1E2", ["LIBRO DE FISICA", "A8D4F1E2"])


def test_codigo_presente_fuzzy_ocr():
    # Simula confusión de OCR típica de manuscrito
    assert _codigo_presente("A8D4F1E2", ["FISICA", "ABDAFIEZ"])


def test_codigo_presente_espacios():
    assert _codigo_presente("F4B2", ["CODIGO: F 4 B 2"])


def test_verificar_imagen_sintetica():
    # Crear imagen simulando portada y nota de papel
    img = Image.new("RGB", (400, 300), color=(245, 245, 240))
    d = ImageDraw.Draw(img)
    # Dibujar lomo/libro
    d.rectangle([40, 40, 240, 260], fill=(30, 60, 140))
    d.text((50, 50), "CALCULO DIFERENCIAL", fill=(255, 255, 255))
    # Dibujar papelito blanco con código
    d.rectangle([250, 100, 380, 180], fill=(255, 255, 255), outline=(0, 0, 0))
    d.text((260, 130), "C1D2E3F4", fill=(0, 0, 0))

    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    res = verificar_imagen(buf.getvalue(), "C1D2E3F4")

    assert "es_libro" in res
    assert "codigo_encontrado" in res
    assert "aprobado" in res
    assert isinstance(res["detalle"], str)
