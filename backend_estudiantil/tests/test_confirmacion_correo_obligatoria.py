import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend_estudiantil.adapters.notifications.email_sender import SMTPEmailSender
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.services.moderacion_sanciones_service import usuario_puede_operar
from backend_estudiantil.infrastructure.main import app  # noqa: F401  (asegura la app cargada)


@pytest.fixture(autouse=True)
def _regla_confirmacion_activa(monkeypatch):
    """En este archivo la regla está ACTIVA (conftest la desactiva para pruebas heredadas)."""
    monkeypatch.setattr(settings, "CONFIRMACION_CORREO_OBLIGATORIA", True)


def _usuario(correo, confirmado, estado="activo"):
    return SimpleNamespace(
        correo_institucional=correo,
        correo_confirmado=confirmado,
        estado_cuenta=estado,
        fin_suspension=None,
        motivo_sancion=None,
        is_active=True,
    )


@pytest.mark.unit
def test_institucional_sin_confirmar_no_puede_operar():
    res = usuario_puede_operar(_usuario("ana@usbmed.edu.co", False))
    assert res.puede_operar is False
    assert res.estado_cuenta == "pendiente"


@pytest.mark.unit
def test_institucional_confirmado_puede_operar():
    assert usuario_puede_operar(_usuario("ana@usbmed.edu.co", True)).puede_operar is True


@pytest.mark.unit
def test_cuenta_general_sin_confirmar_puede_operar():
    assert usuario_puede_operar(_usuario("ana@gmail.com", False)).puede_operar is True


@pytest.mark.unit
def test_interruptor_desactiva_la_regla(monkeypatch):
    monkeypatch.setattr(settings, "CONFIRMACION_CORREO_OBLIGATORIA", False)
    assert usuario_puede_operar(_usuario("ana@usbmed.edu.co", False)).puede_operar is True


@pytest.mark.integration
def test_flujo_login_bloqueado_y_desbloqueo_tras_confirmar(client):
    capturados = []

    async def fake_send(self, to_email, code, verification_link=None):
        capturados.append(code)
        return True

    email = f"est-{uuid.uuid4().hex[:8]}@usbmed.edu.co"
    with patch.object(SMTPEmailSender, "send_verification_code", new=fake_send):
        r = client.post("/auth/register", json={"email": email, "name": "Est", "password": "Clave12345"})
        assert r.status_code == 201

        bloqueado = client.post("/auth/login", json={"email": email, "password": "Clave12345"})
        assert bloqueado.status_code == 403
        assert "confirmar" in bloqueado.json()["detail"].lower()

        conf = client.post("/auth/confirmar-codigo", json={"email": email, "codigo": capturados[-1]})
        assert conf.status_code == 200

        ok = client.post("/auth/login", json={"email": email, "password": "Clave12345"})
        assert ok.status_code == 200


@pytest.mark.integration
def test_cuenta_general_puede_iniciar_sesion_sin_confirmar(client):
    email = f"general-{uuid.uuid4().hex[:8]}@gmail.com"
    assert client.post("/auth/register", json={"email": email, "name": "G", "password": "Clave12345"}).status_code == 201
    assert client.post("/auth/login", json={"email": email, "password": "Clave12345"}).status_code == 200
