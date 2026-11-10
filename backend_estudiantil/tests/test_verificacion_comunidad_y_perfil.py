import io
import uuid
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import select

from backend_estudiantil.adapters.db import UserORM, get_session_factory
from backend_estudiantil.adapters.notifications.email_sender import SMTPEmailSender
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator
from backend_estudiantil.infrastructure.main import app

pytestmark = pytest.mark.integration


@pytest.fixture
def jwt_auth():
    return JWTAuthenticator()

@pytest.mark.asyncio
async def test_registro_password_no_marca_verificado_hasta_confirmar_codigo(jwt_auth):
    """Verifica que el registro con contraseña NO active verificado_comunidad de inmediato y requiera confirmación de código."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    codigos_capturados = []

    async def mock_send_email(self, to_email, code, verification_link=None):
        codigos_capturados.append(code)
        return True

    with patch.object(SMTPEmailSender, "send_verification_code", new=mock_send_email):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            email_inst = f"estudiante_{uid}@usbmed.edu.co"
            # 1. Registro con dominio institucional de USBMED
            res_inst = await ac.post("/auth/register", json={
                "email": email_inst,
                "password": "Password123*",
                "name": "Carlos Rodríguez",
                "carrera": "Ingeniería de Sistemas",
            })
            assert res_inst.status_code == 201
            data_inst = res_inst.json()
            # REGLA: NO debe estar verificado sólo por el dominio
            assert data_inst["verificado_comunidad"] is False

            # Obtener el código de confirmación generado en la BD
            factory = get_session_factory()
            async with factory() as session:
                q = await session.execute(select(UserORM).where(UserORM.correo_institucional == email_inst))
                u = q.scalar_one()
                codigo_guardado = u.codigo_confirmacion
                assert codigo_guardado is not None
                # Debe estar almacenado como hash SHA-256 (64 hex caracteres) por seguridad
                assert len(codigo_guardado) == 64

            assert len(codigos_capturados) == 1
            codigo_plano = codigos_capturados[0]
            assert len(codigo_plano) == 6

            # 2. Intentar confirmar con código erróneo -> 400 Bad Request
            res_fail = await ac.post("/auth/confirmar-codigo", json={
                "email": email_inst,
                "codigo": "000000",
            })
            assert res_fail.status_code == 400
            assert "incorrecto" in res_fail.json()["detail"].lower()

            # 3. Confirmar con código correcto -> 200 OK y verificado_comunidad=True
            res_ok = await ac.post("/auth/confirmar-codigo", json={
                "email": email_inst,
                "codigo": codigo_plano,
            })
            assert res_ok.status_code == 200
            assert res_ok.json()["verificado_comunidad"] is True

            # Verificar en la base de datos que ya no hay código pendiente y la comunidad está verificada
            async with factory() as session:
                q = await session.execute(select(UserORM).where(UserORM.correo_institucional == email_inst))
                u = q.scalar_one()
                assert u.verificado_comunidad is True
                assert u.codigo_confirmacion is None
                assert u.universidad == "Universidad de San Buenaventura Medellín"

            # 4. Usuario con correo externo (@gmail.com) no tiene verificado_comunidad
            res_ext = await ac.post("/auth/register", json={
                "email": f"usuario_ext_{uid}@gmail.com",
                "password": "Password123*",
                "name": "Pedro Gómez",
            })
            assert res_ext.status_code == 201
            data_ext = res_ext.json()
            assert data_ext["verificado_comunidad"] is False



@pytest.mark.asyncio
async def test_cuenta_general_puede_publicar_y_bloqueado_es_rechazado(jwt_auth):
    """Verifica que una cuenta general/Gmail pueda publicar y proponer trueques, y que una cuenta bloqueada sea rechazada."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    factory = get_session_factory()
    email = f"general_{uid}@gmail.com"
    pub_id = None
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Registrar usuario externo general (Gmail)
            await ac.post("/auth/register", json={
                "email": email,
                "password": "Password123*",
                "name": "Usuario General",
            })

            login_res = await ac.post("/auth/login", json={
                "email": email,
                "password": "Password123*",
            })
            token = login_res.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Usuario general puede publicar exitosamente
            pub_res = await ac.post("/publicaciones/", json={
                "titulo": "Libro de Lectura General",
                "autor": "Autor Ejemplo",
                "categoria_id": 1,
            }, headers=headers)
            assert pub_res.status_code == 201
            pub_id = pub_res.json()["id"]

            # Si la cuenta pasa a estado 'bloqueado', no puede publicar
            async with factory() as session:
                q = await session.execute(select(UserORM).where(UserORM.correo_institucional == email))
                u = q.scalar_one()
                u.estado_cuenta = "bloqueado"
                await session.commit()

            pub_bloq = await ac.post("/publicaciones/", json={
                "titulo": "Otro Libro",
                "autor": "Autor",
                "categoria_id": 1,
            }, headers=headers)
            assert pub_bloq.status_code == 403
            assert any(m in pub_bloq.json()["detail"] for m in ["Inactive", "bloqueada"])
    finally:
        async with factory() as session:
            from sqlalchemy import text
            if pub_id:
                await session.execute(text("DELETE FROM publicaciones WHERE id = :pid"), {"pid": pub_id})
            await session.execute(text("DELETE FROM usuarios WHERE correo_institucional = :email"), {"email": email})
            await session.commit()


@pytest.mark.asyncio
async def test_flujo_solicitud_y_aprobacion_carne_estudiantil(jwt_auth):
    """Flujo completo de carga de carné, privacidad y aprobación por moderador."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Registrar usuario externo no verificado
        alumno_email = f"alumno_{uid}@hotmail.com"
        reg_alumno = await ac.post("/auth/register", json={
            "email": alumno_email,
            "password": "Password123*",
            "name": "Juan Alumno",
            "carrera": "Derecho",
            "universidad": "Universidad Libre",
        })
        alumno_id = reg_alumno.json()["id"]

        login_alumno = await ac.post("/auth/login", json={"email": alumno_email, "password": "Password123*"})
        alumno_token = login_alumno.json()["access_token"]
        alumno_headers = {"Authorization": f"Bearer {alumno_token}"}

        # 2. Registrar moderador
        mod_email = f"mod_{uid}@unal.edu.co"
        await ac.post("/auth/register", json={
            "email": mod_email,
            "password": "Password123*",
            "name": "Mod Staff",
        })
        # Promover a moderador
        factory = get_session_factory()
        async with factory() as session:
            q = await session.execute(select(UserORM).where(UserORM.correo_institucional == mod_email))
            mod_user = q.scalar_one()
            mod_user.rol = "moderador"
            await session.commit()

        login_mod = await ac.post("/auth/login", json={"email": mod_email, "password": "Password123*"})
        mod_token = login_mod.json()["access_token"]
        mod_headers = {"Authorization": f"Bearer {mod_token}"}

        # 3. Alumno sube carné
        fake_image = io.BytesIO(b"FAKE_CARNET_IMAGE_BYTES_12345")
        files = {"carnet": ("mi_carnet.jpg", fake_image, "image/jpeg")}
        upload_res = await ac.post("/usuarios/me/solicitar-verificacion", files=files, headers=alumno_headers)
        assert upload_res.status_code == 200
        assert "Carné recibido" in upload_res.json()["msg"]

        # 4. Privacidad: Otro usuario común intenta ver el carné de este alumno -> 403 Forbidden
        otro_email = f"curioso_{uid}@gmail.com"
        await ac.post("/auth/register", json={"email": otro_email, "password": "Password123*", "name": "Curioso"})
        login_otro = await ac.post("/auth/login", json={"email": otro_email, "password": "Password123*"})
        otro_headers = {"Authorization": f"Bearer {login_otro.json()['access_token']}"}

        priv_res = await ac.get(f"/usuarios/{alumno_id}/carnet", headers=otro_headers)
        assert priv_res.status_code == 403

        # 5. El moderador lista pendientes
        pendientes_res = await ac.get("/usuarios/verificaciones/pendientes", headers=mod_headers)
        assert pendientes_res.status_code == 200
        ids_pendientes = [u["id"] for u in pendientes_res.json()]
        assert str(alumno_id) in ids_pendientes

        # 6. El moderador aprueba la verificación
        aprobar_res = await ac.post(f"/usuarios/{alumno_id}/verificar", headers=mod_headers)
        assert aprobar_res.status_code == 200
        assert aprobar_res.json()["verificado_comunidad"] is True


@pytest.mark.asyncio
async def test_google_oauth_exige_email_verified():
    """Verifica que Google OAuth exija email_verified=true y active verificado_comunidad si es institucional."""
    from backend_estudiantil.infrastructure.api.google_oauth_router import get_google_authenticator

    class MockGoogleAuth:
        def __init__(self, email_verified: bool, email: str):
            self.email_verified = email_verified
            self.email = email

        async def exchange_code(self, code: str):
            return {"access_token": "mock_google_token"}

        async def get_userinfo(self, token: str):
            return {
                "id": "123456789",
                "email": self.email,
                "name": "Estudiante Google",
                "email_verified": self.email_verified,
            }

    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]

    # 1. Caso email_verified=False -> 400 Bad Request
    app.dependency_overrides[get_google_authenticator] = lambda: MockGoogleAuth(
        email_verified=False,
        email=f"google_unverified_{uid}@unal.edu.co"
    )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/auth/google/callback?code=mock_code")
        assert res.status_code == 400
        assert "email_verified=true" in res.json()["detail"]

    # 2. Caso email_verified=True con correo institucional -> 200 y verificado_comunidad=True
    email_inst = f"google_verified_{uid}@usbmed.edu.co"
    app.dependency_overrides[get_google_authenticator] = lambda: MockGoogleAuth(
        email_verified=True,
        email=email_inst
    )
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/auth/google/callback?code=mock_code", headers={"Accept": "application/json"})
        assert res.status_code == 200
        data = res.json()
        assert data["user"]["verificado_comunidad"] is True
        assert data["user"]["universidad"] == "Universidad de San Buenaventura Medellín"

    # Limpiar overrides
    app.dependency_overrides.pop(get_google_authenticator, None)

