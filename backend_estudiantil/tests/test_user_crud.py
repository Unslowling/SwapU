import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from backend_estudiantil.infrastructure.main import app
from backend_estudiantil.config.settings import settings
from backend_estudiantil.adapters.db import Base, get_engine

pytestmark = pytest.mark.integration

@pytest_asyncio.fixture(scope="function", autouse=True)
async def prepare_test_db(isolated_db):
    """Utiliza la base de datos SQLite temporal aislada provista por conftest."""
    yield

@pytest.mark.asyncio
async def test_user_crud_and_promotion():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Registrar usuario normal
        user_payload = {
            "email": "user@example.com",
            "password": "secretpassword123",
            "name": "Normal User",
            "role": "usuario",
            "carrera": "Ingeniería de Sistemas",
            "universidad": "Universidad Nacional",
        }
        resp = await client.post("/auth/register", json=user_payload)
        assert resp.status_code == 201, f"Register falló: {resp.text}"
        data = resp.json()
        assert data["email"] == "user@example.com"
        # El rol puede ser 'usuario' (interno) o 'user' (legacy)
        assert data["role"] in ("user", "usuario")
        user_id = data["id"]

        # 2. Iniciar sesión con usuario normal
        login_user_resp = await client.post(
            "/auth/login",
            json={"email": "user@example.com", "password": "secretpassword123"},
        )
        assert login_user_resp.status_code == 200
        user_token = login_user_resp.json()["access_token"]
        assert "refresh_token" in login_user_resp.cookies
        user_headers = {"Authorization": f"Bearer {user_token}"}

        # 3. Consultar perfil propio en /usuarios/me
        me_resp = await client.get("/usuarios/me", headers=user_headers)
        assert me_resp.status_code == 200
        assert str(me_resp.json()["id"]) == str(user_id)

        # 4. Actualizar perfil propio en /usuarios/me
        update_resp = await client.put(
            "/usuarios/me",
            json={"name": "Normal User Updated"},
            headers=user_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Normal User Updated"

        # 5. Registrar un usuario administrador
        admin_payload = {
            "email": "admin@example.com",
            "password": "adminpass123",
            "name": "Admin User",
            "role": "admin",
        }
        resp_admin = await client.post("/auth/register", json=admin_payload)
        assert resp_admin.status_code == 201

        # 6. Login como admin para obtener token con rol admin
        login_resp = await client.post(
            "/auth/login",
            json={"email": admin_payload["email"], "password": admin_payload["password"]},
        )
        assert login_resp.status_code == 200
        admin_token = login_resp.json()["access_token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # 7. Listar usuarios como admin
        list_resp = await client.get("/usuarios/", headers=admin_headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 2

        # 8. Promover al usuario normal a moderador
        promote_resp = await client.post(f"/admin/users/{user_id}/promote", headers=admin_headers)
        assert promote_resp.status_code == 200
        assert "moderador" in promote_resp.json()["msg"]

        # 9. Logout
        logout_resp = await client.post("/auth/logout")
        assert logout_resp.status_code == 200
