from unittest.mock import patch
import pytest
from backend_estudiantil.config.settings import settings
from backend_estudiantil.infrastructure.verificacion_ia import (
    _clasificar_imagen, verificar_imagen, precalentar
)

pytestmark = pytest.mark.unit


def test_clasificar_imagen_falla_cerrado_si_modelo_no_disponible():
    """Verifica que si MobileNet no está disponible o falla, retorne False (falla cerrado)."""
    with patch("backend_estudiantil.infrastructure.verificacion_ia._cargar_modelo", return_value=(None, None, None, None)):
        es_libro, confianza, clase = _clasificar_imagen(b"dummy_bytes")
        assert es_libro is False
        assert confianza == 0.0
        assert clase == "modelo_no_disponible"


def test_clasificar_imagen_falla_cerrado_en_excepcion():
    """Verifica que una excepción durante inferencia falle cerrado retornando False."""
    with patch("backend_estudiantil.infrastructure.verificacion_ia._cargar_modelo", side_effect=RuntimeError("GPU OOM")):
        es_libro, confianza, clase = _clasificar_imagen(b"dummy_bytes")
        assert es_libro is False
        assert confianza == 0.0
        assert "error" in clase or "disponible" in clase


def test_umbral_libro_configurable_desde_settings():
    """Verifica que el umbral_libro sea configurable desde settings."""
    assert hasattr(settings, "IA_UMBRAL_LIBRO")
    assert settings.IA_UMBRAL_LIBRO >= 0.0

    # Probamos verificar_imagen sin umbral explicito -> toma de settings
    with patch("backend_estudiantil.infrastructure.verificacion_ia._clasificar_imagen", return_value=(False, 0.05, "notebook")):
        with patch("backend_estudiantil.infrastructure.verificacion_ia._extraer_texto_ocr", return_value=["A1B2C3D4"]):
            res = verificar_imagen(b"bytes", "A1B2C3D4")
            # 0.05 es menor al umbral (0.10) por tanto no aprueba
            assert res["aprobado"] is False


def test_precalentar_ejecuta_correctamente():
    """Verifica que la función precalentar() se invoque sin errores de importación."""
    precalentar()
