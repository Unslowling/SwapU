import pytest

pytestmark = pytest.mark.integration


def test_registro_publico_no_concede_rol_administrador(client):
    """Regresión: enviar role='admin' al registro NO debe otorgar privilegios."""
    email = "intruso@usbmed.edu.co"
    r = client.post(
        "/auth/register",
        json={"email": email, "name": "Intruso", "password": "Clave12345", "role": "admin"},
    )
    assert r.status_code == 201
    assert r.json()["role"] != "administrador"

    login = client.post("/auth/login", json={"email": email, "password": "Clave12345"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    auditoria = client.get("/admin/auditoria", headers=headers)
    assert auditoria.status_code == 403
