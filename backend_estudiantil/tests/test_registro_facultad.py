import pytest
import pytest_asyncio

from httpx import ASGITransport, AsyncClient

from backend_estudiantil.infrastructure.main import app

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture(scope="function", autouse=True)
async def prepare_test_db(isolated_db):
    """Utiliza la base de datos SQLite temporal aislada provista por conftest."""
    yield


@pytest.mark.asyncio
async def test_facultad_viaja_en_registro_y_se_guarda():
    """Confirma que el campo facultad viaja en el registro (/auth/register),

    se almacena en la base de datos y se recupera correctamente en /usuarios/me.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Payload de registro con facultad explícita
        registro_payload = {
            "name": "Estudiante Prueba Facultad",
            "email": "estudiante.facultad@test.com",
            "password": "Password123*",
            "telefono": "+573001234567",
            "facultad": "Facultad de Ingenierías",
            "carrera": "Ingeniería de Sistemas Cibernéticos",
            "semestre": 5,
            "universidad": "Universidad de San Buenaventura Medellín",
        }

        # 2. Registrar usuario
        reg_resp = await client.post("/auth/register", json=registro_payload)
        assert reg_resp.status_code == 201, f"Fallo al registrar: {reg_resp.text}"
        data_reg = reg_resp.json()

        # Verificar que la respuesta del endpoint incluye facultad
        assert "facultad" in data_reg
        assert data_reg["facultad"] == "Facultad de Ingenierías"
        user_id = data_reg["id"]

        # 3. Iniciar sesión para obtener token
        login_resp = await client.post(
            "/auth/login",
            json={"email": "estudiante.facultad@test.com", "password": "Password123*"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 4. Consultar perfil en /usuarios/me para confirmar persistencia en base de datos
        me_resp = await client.get("/usuarios/me", headers=headers)
        assert me_resp.status_code == 200
        data_me = me_resp.json()
        assert data_me["id"] == user_id
        assert data_me["facultad"] == "Facultad de Ingenierías"
        assert data_me["carrera"] == "Ingeniería de Sistemas Cibernéticos"

        # 5. Modificar facultad en /usuarios/me y verificar que se actualiza y persiste
        update_resp = await client.put(
            "/usuarios/me",
            json={"facultad": "Facultad de Ciencias Empresariales", "carrera": "Negocios Internacionales"},
            headers=headers,
        )
        assert update_resp.status_code == 200
        data_upd = update_resp.json()
        assert data_upd["facultad"] == "Facultad de Ciencias Empresariales"
        assert data_upd["carrera"] == "Negocios Internacionales"

        # 6. Reconsultar /usuarios/me para ratificar persistencia tras modificación
        me_resp_2 = await client.get("/usuarios/me", headers=headers)
        assert me_resp_2.status_code == 200
        assert me_resp_2.json()["facultad"] == "Facultad de Ciencias Empresariales"
