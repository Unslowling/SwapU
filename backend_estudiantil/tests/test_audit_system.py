import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from backend_estudiantil.infrastructure.main import app
from backend_estudiantil.config.settings import settings
from backend_estudiantil.adapters.db import Base, get_engine, get_session_factory, AuditoriaLogORM, UserORM
from backend_estudiantil.adapters.security.password_hasher import hash_password
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator

pytestmark = pytest.mark.integration



@pytest_asyncio.fixture(autouse=True)
async def reset_db(isolated_db):
    """Utiliza la base de datos SQLite temporal aislada provista por conftest."""
    yield


@pytest.mark.asyncio
async def test_audit_middleware_captures_requests_5w():
    """Verifica que el middleware intercepte peticiones y persista registros bajo la regla 5W."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Intento de login fallido (debe registrar Why: 401 Unauthorized)
        res_login = await client.post(
            "/auth/login",
            json={"email": "inexistente@correo.com", "password": "wrongpassword"},
        )
        assert res_login.status_code == 401

        # Dar un breve instante para que la tarea en segundo plano guarde el log
        await asyncio.sleep(0.15)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(AuditoriaLogORM))
        logs = result.scalars().all()

        assert len(logs) >= 1
        login_log = next((log_item for log_item in logs if log_item.accion == "INICIO_SESION"), None)
        assert login_log is not None

        # Verificación de la Regla de las 5W
        # 1. Who (Quién)
        assert login_log.ip_origen in ("127.0.0.1", "testclient", "localhost")
        # 2. What (Qué)
        assert login_log.accion == "INICIO_SESION"
        assert login_log.recurso == "auth"
        # 3. When (Cuándo)
        assert login_log.fecha_hora is not None
        # 4. Where (Dónde)
        assert login_log.metodo_http == "POST"
        assert login_log.endpoint == "/auth/login"
        # 5. Why (Por qué)
        assert login_log.estado_http == 401
        assert login_log.exito is False
        assert "No autorizado" in login_log.detalle
        assert login_log.duracion_ms >= 0


@pytest.mark.asyncio
async def test_admin_audit_endpoints_and_permissions():
    """Valida los endpoints GET /admin/auditoria y GET /admin/auditoria/stats con control RBAC."""
    factory = get_session_factory()
    jwt_auth = JWTAuthenticator()

    async with factory() as session:
        # Crear usuario administrador
        admin_user = UserORM(
            nombre="Admin",
            apellido="Auditor",
            correo_institucional="admin@trueque.edu.co",
            password_hash=hash_password("adminpass123"),
            rol="administrador",
            estado_cuenta="activo",
        )
        # Crear usuario normal
        normal_user = UserORM(
            nombre="Estudiante",
            apellido="Prueba",
            correo_institucional="user@trueque.edu.co",
            password_hash=hash_password("userpass123"),
            rol="usuario",
            estado_cuenta="activo",
        )

        session.add_all([admin_user, normal_user])
        await session.commit()
        await session.refresh(admin_user)
        await session.refresh(normal_user)

    admin_token = jwt_auth.create_access_token({"sub": str(admin_user.id), "role": "administrador"})
    user_token = jwt_auth.create_access_token({"sub": str(normal_user.id), "role": "usuario"})


    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Usuario normal intenta consultar auditoría -> 403 Forbidden
        res_denied = await client.get(
            "/admin/auditoria",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert res_denied.status_code == 403

        # 2. Administrador consulta auditoría -> 200 OK
        res_admin = await client.get(
            "/admin/auditoria",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_admin.status_code == 200
        data = res_admin.json()
        assert "total" in data
        assert "items" in data
        assert isinstance(data["items"], list)

        # 3. Administrador consulta métricas estadísticas
        res_stats = await client.get(
            "/admin/auditoria/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res_stats.status_code == 200
        stats_data = res_stats.json()
        assert "total_eventos" in stats_data
        assert "eventos_exitosos" in stats_data
        assert "eventos_fallidos" in stats_data
        assert "intentos_bloqueados_401_403" in stats_data
