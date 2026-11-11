import pytest

from backend_estudiantil.tests._admin_helpers import convertir_en_administrador

pytestmark = pytest.mark.integration


def test_resumen_admin_con_datos_reales_y_restringido(client):
    for correo in ("adm@example.com", "est@example.com"):
        assert client.post("/auth/register", json={"email": correo, "name": "X", "password": "Clave12345"}).status_code == 201
    convertir_en_administrador("adm@example.com")

    def token(correo):
        return {"Authorization": "Bearer " + client.post(
            "/auth/login", json={"email": correo, "password": "Clave12345"}).json()["access_token"]}

    assert client.get("/admin/resumen", headers=token("est@example.com")).status_code == 403
    r = client.get("/admin/resumen", headers=token("adm@example.com"))
    assert r.status_code == 200
    datos = r.json()
    assert datos["usuarios_registrados"] == 2
    assert datos["libros_en_oferta"] == 0
    assert datos["trueques_completados"] == 0
    assert datos["reputacion_global"] is None
