import uuid

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend_estudiantil.adapters.db import (
    AuditoriaLogORM,
    PublicacionORM,
    UserORM,
    get_session_factory,
)
from backend_estudiantil.adapters.db.sqlalchemy_match_repository import (
    SQLAlchemyMatchRepository,
)
from backend_estudiantil.adapters.db.sqlalchemy_publicacion_repository import (
    SQLAlchemyPublicacionRepository,
)
from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.services.match_service import MatchService
from backend_estudiantil.infrastructure.confirmation_rate_limiter import (
    confirmation_rate_limiter,
)
from backend_estudiantil.infrastructure.main import app


@pytest.mark.unit
def test_validacion_dominio_institucional_anti_spoofing():
    """Valida estrictamente la división por '@' y previene ataques de sufijo o subdominio malicioso."""
    # 1. Correo legítimo
    assert settings.es_dominio_institucional("a@usbmed.edu.co") is True
    assert settings.es_dominio_institucional("estudiante@tau.usbmed.edu.co") is True
    assert "San Buenaventura" in settings.obtener_universidad_por_dominio("estudiante@tau.usbmed.edu.co")
    assert settings.es_dominio_institucional("estudiante.sistemas@alumno.unal.edu.co") is True

    # 2. Correo atacante con sufijo extra (attacker.com) -> DEBE SER RECHAZADO
    assert settings.es_dominio_institucional("a@usbmed.edu.co.attacker.com") is False

    # 3. Correo atacante con prefijo concatenado (xusbmed.edu.co) -> DEBE SER RECHAZADO
    assert settings.es_dominio_institucional("a@xusbmed.edu.co") is False

    # 4. Formatos inválidos
    assert settings.es_dominio_institucional("sin_arroba.com") is False
    assert settings.es_dominio_institucional("a@@usbmed.edu.co") is False
    assert settings.es_dominio_institucional("") is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_maximo_5_intentos_por_codigo_e_invalidacion():
    """Valida que tras 5 intentos fallidos el código sea invalidado y exija reenvío."""
    confirmation_rate_limiter.reset()
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    email = f"intento_{uid}@usbmed.edu.co"
    factory = get_session_factory()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Registrar usuario
        reg = await ac.post("/auth/register", json={
            "email": email,
            "password": "Password123*",
            "name": "Estudiante Intentos",
        })
        assert reg.status_code == 201

        # Fallar 4 veces
        for i in range(1, 5):
            res_fail = await ac.post("/auth/confirmar-codigo", json={
                "email": email,
                "codigo": f"99999{i}",
            })
            assert res_fail.status_code == 400
            assert f"intento {i} de 5" in res_fail.json()["detail"].lower()

        # Quinto fallo: debe superar el límite y bloquear el código
        res_fail_5 = await ac.post("/auth/confirmar-codigo", json={
            "email": email,
            "codigo": "999995",
        })
        assert res_fail_5.status_code == 400
        assert "superado el número máximo de intentos" in res_fail_5.json()["detail"].lower()

        # En la BD, el código debe haber sido invalidado a None
        async with factory() as session:
            q = await session.execute(select(UserORM).where(UserORM.correo_institucional == email))
            u = q.scalar_one()
            assert u.codigo_confirmacion is None
            assert u.verificado_comunidad is False

        # Sexto intento: ya no hay código activo (reseteamos rate limit para evaluar la respuesta de negocio)
        confirmation_rate_limiter.reset()
        res_fail_6 = await ac.post("/auth/confirmar-codigo", json={
            "email": email,
            "codigo": "123456",
        })
        assert res_fail_6.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_rate_limit_endpoints_confirmacion():
    """Valida que los endpoints de confirmación apliquen rate limit y retornen HTTP 429."""
    confirmation_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Ejecutar 5 peticiones permitidas
        for _ in range(5):
            res = await ac.post("/auth/reenviar-codigo", json={"email": "nadie@usbmed.edu.co"})
            assert res.status_code == 200

        # La 6ª petición dentro de la ventana de tiempo debe retornar 429 Too Many Requests
        res_429 = await ac.post("/auth/reenviar-codigo", json={"email": "nadie@usbmed.edu.co"})
        assert res_429.status_code == 429
        assert "límite de intentos" in res_429.json()["detail"].lower()

    confirmation_rate_limiter.reset()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_respuestas_genericas_sin_revelar_correos_registrados():
    """Valida respuestas genéricas en reenviar-codigo y confirmar sin filtrar existencia de usuario."""
    confirmation_rate_limiter.reset()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Reenviar a correo inexistente -> HTTP 200 genérico
        res_reenviar = await ac.post("/auth/reenviar-codigo", json={
            "email": "inexistente_total_xyz@usbmed.edu.co",
        })
        assert res_reenviar.status_code == 200
        assert "si el correo corresponde" in res_reenviar.json()["message"].lower()

        # Confirmar en correo inexistente -> HTTP 400 genérico (no 404 ni 'Usuario no encontrado')
        res_conf = await ac.post("/auth/confirmar-codigo", json={
            "email": "inexistente_total_xyz@usbmed.edu.co",
            "codigo": "123456",
        })
        assert res_conf.status_code == 400
        assert "código de confirmación o correo inválido" in res_conf.json()["detail"].lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cambio_correo_reinicia_verificado_comunidad():
    """Valida que si el usuario cambia su correo electrónico, verificado_comunidad vuelve a False."""
    confirmation_rate_limiter.reset()
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    factory = get_session_factory()
    email_inicial = f"inicial_{uid}@usbmed.edu.co"

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Registrar y login
        reg = await ac.post("/auth/register", json={
            "email": email_inicial,
            "password": "Password123*",
            "name": "Estudiante Cambio Correo",
        })
        assert reg.status_code == 201

        login = await ac.post("/auth/login", json={
            "email": email_inicial,
            "password": "Password123*",
        })
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Simular que el usuario ya estaba verificado
        async with factory() as session:
            q = await session.execute(select(UserORM).where(UserORM.correo_institucional == email_inicial))
            u = q.scalar_one()
            u.verificado_comunidad = True
            u.correo_confirmado = True
            await session.commit()

        # Cambiar correo a uno nuevo
        nuevo_email = f"nuevo_{uid}@usbmed.edu.co"
        res_update = await ac.put("/usuarios/me", headers=headers, json={
            "email": nuevo_email,
        })
        assert res_update.status_code == 200
        data_update = res_update.json()

        # REGLA: verificado_comunidad DEBE volver a False
        assert data_update["verificado_comunidad"] is False

        # Verificar en la base de datos
        async with factory() as session:
            q = await session.execute(select(UserORM).where(UserORM.correo_institucional == nuevo_email))
            u = q.scalar_one()
            assert u.verificado_comunidad is False
            assert u.correo_confirmado is False
            assert u.codigo_confirmacion is not None  # Se le envía un nuevo código


@pytest.mark.integration
@pytest.mark.asyncio
async def test_facebook_oauth_nunca_otorga_verificado_comunidad():
    """Valida que el registro o autenticación por Facebook OAuth jamás active verificado_comunidad."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    email_fb = f"fb_user_{uid}@usbmed.edu.co"

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Autenticación federada simulando proveedor facebook
        res_fb = await ac.post("/auth/social-login", json={
            "provider": "facebook",
            "email": email_fb,
            "name": "Usuario Facebook",
            "universidad": "Universidad de San Buenaventura Medellín",
        })
        assert res_fb.status_code == 200

        # Consultar datos del usuario
        factory = get_session_factory()
        async with factory() as session:
            q = await session.execute(select(UserORM).where(UserORM.correo_institucional == email_fb))
            u = q.scalar_one()
            # REGLA: Facebook OAuth NUNCA otorga verificado_comunidad
            assert u.verificado_comunidad is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_audit_middleware_no_registra_query_string_de_confirmacion():
    """Verifica que AuditMiddleware no registre la query string (código, tokens) del enlace de confirmación."""
    transport = ASGITransport(app=app)
    confirmation_rate_limiter.reset()

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.get("/auth/confirmar-correo?email=prueba@usbmed.edu.co&codigo=987654")
        import asyncio
        await asyncio.sleep(0.15)

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(AuditoriaLogORM)
            .where(AuditoriaLogORM.endpoint.like("%/auth/confirmar-correo%"))
            .order_by(AuditoriaLogORM.id.desc())
            .limit(1)
        )
        log = result.scalar_one_or_none()
        assert log is not None
        # REGLA: endpoint no debe contener '?' ni parámetros de query string
        assert "?" not in log.endpoint
        assert "987654" not in log.endpoint


@pytest.mark.integration
@pytest.mark.asyncio
async def test_matching_prioridades_facultad_carrera_y_semestre():
    """Demuestra el orden resultante del algoritmo de matching con pesos de afinidad para estudiantes verificados.
    
    Orden esperado de prioridad:
    1. Misma universidad + Misma facultad/carrera + Semestre cercano (diff <= 2)
    2. Misma universidad + Misma facultad/carrera + Semestre lejano
    3. Misma universidad + Otra facultad/carrera
    4. Otra universidad o no verificado
    """
    uid = uuid.uuid4().hex[:6]
    factory = get_session_factory()

    async with factory() as session:
        # Usuario origen (verificado, USBMED, Ingeniería, Semestre 5)
        u_origen = UserORM(
            nombre="Origen Afinidad",
            apellido="Estudiante",
            correo_institucional=f"origen_afinidad_{uid}@usbmed.edu.co",
            password_hash="hash",
            universidad="Universidad de San Buenaventura Medellín",
            facultad="Facultad de Ingeniería",
            programa_area="Ingeniería de Sistemas",
            semestre=5,
            verificado_comunidad=True,
        )

        # Candidato 1: Misma uni, misma facultad, semestre 6 (diff=1 <= 2) -> PUNTUACIÓN MÁXIMA
        c1 = UserORM(
            nombre="Cand 1 Maxima Afinidad",
            apellido="Estudiante",
            correo_institucional=f"c1_{uid}@usbmed.edu.co",
            password_hash="hash",
            universidad="Universidad de San Buenaventura Medellín",
            facultad="Facultad de Ingeniería",
            programa_area="Ingeniería de Sistemas",
            semestre=6,
            verificado_comunidad=True,
        )

        # Candidato 2: Misma uni, misma facultad, semestre 10 (diff=5 > 2)
        c2 = UserORM(
            nombre="Cand 2 Sin Semestre Cercano",
            apellido="Estudiante",
            correo_institucional=f"c2_{uid}@usbmed.edu.co",
            password_hash="hash",
            universidad="Universidad de San Buenaventura Medellín",
            facultad="Facultad de Ingeniería",
            programa_area="Ingeniería de Sistemas",
            semestre=10,
            verificado_comunidad=True,
        )

        # Candidato 3: Misma uni, OTRA facultad (Derecho), semestre 5
        c3 = UserORM(
            nombre="Cand 3 Otra Facultad",
            apellido="Estudiante",
            correo_institucional=f"c3_{uid}@usbmed.edu.co",
            password_hash="hash",
            universidad="Universidad de San Buenaventura Medellín",
            facultad="Facultad de Derecho",
            programa_area="Derecho",
            semestre=5,
            verificado_comunidad=True,
        )

        # Candidato 4: OTRA universidad (UdeA)
        c4 = UserORM(
            nombre="Cand 4 Otra Uni",
            apellido="Estudiante",
            correo_institucional=f"c4_{uid}@udea.edu.co",
            password_hash="hash",
            universidad="Universidad de Antioquia",
            facultad="Facultad de Ingeniería",
            programa_area="Ingeniería de Sistemas",
            semestre=5,
            verificado_comunidad=True,
        )

        session.add_all([u_origen, c1, c2, c3, c4])
        await session.flush()

        libro_buscado = f"Física Cuántica {uid}"
        libro_ofrecido = f"Ecuaciones Diferenciales {uid}"

        pub_origen = PublicacionORM(
            usuario_id=u_origen.id,
            titulo=libro_ofrecido,
            libro_buscado=libro_buscado,
            estado_publicacion="activa",
        )
        pub_c1 = PublicacionORM(
            usuario_id=c1.id,
            titulo=libro_buscado,
            libro_buscado="Cualquiera",
            estado_publicacion="activa",
        )
        pub_c2 = PublicacionORM(
            usuario_id=c2.id,
            titulo=libro_buscado,
            libro_buscado="Cualquiera",
            estado_publicacion="activa",
        )
        pub_c3 = PublicacionORM(
            usuario_id=c3.id,
            titulo=libro_buscado,
            libro_buscado="Cualquiera",
            estado_publicacion="activa",
        )
        pub_c4 = PublicacionORM(
            usuario_id=c4.id,
            titulo=libro_buscado,
            libro_buscado="Cualquiera",
            estado_publicacion="activa",
        )

        session.add_all([pub_origen, pub_c1, pub_c2, pub_c3, pub_c4])
        await session.commit()
        pub_origen_id = pub_origen.id
        c1_id, c2_id, c3_id, c4_id = pub_c1.id, pub_c2.id, pub_c3.id, pub_c4.id

    match_service = MatchService(
        match_repo=SQLAlchemyMatchRepository(),
        publicacion_repo=SQLAlchemyPublicacionRepository(),
        user_repo=SQLAlchemyUserRepository(),
    )

    matches = await match_service.buscar_matches_para_publicacion(pub_origen_id)

    # Filtrar únicamente los matches de las publicaciones creadas en esta prueba
    ids_en_prueba = {c1_id, c2_id, c3_id, c4_id}
    matches_prueba = [m for m in matches if m.publicacion_destino_id in ids_en_prueba]
    assert len(matches_prueba) == 4

    # DEMOSTRACIÓN DEL ORDEN RESULTANTE:
    # 1º: c1 (Misma uni + Misma carrera/facultad + Semestre cercano)
    # 2º: c2 (Misma uni + Misma carrera/facultad, pero semestre lejano)
    # 3º: c3 (Misma uni, pero distinta carrera/facultad)
    # 4º: c4 (Otra universidad)
    assert matches_prueba[0].publicacion_destino_id == c1_id
    assert matches_prueba[1].publicacion_destino_id == c2_id
    assert matches_prueba[2].publicacion_destino_id == c3_id
    assert matches_prueba[3].publicacion_destino_id == c4_id

    # Limpiar las publicaciones creadas para mantener limpia la base de datos
    async with factory() as session:
        await session.execute(
            sa.text("DELETE FROM matches WHERE publicacion_origen_id = :pid OR publicacion_destino_id IN (:c1, :c2, :c3, :c4)"),
            {"pid": pub_origen_id, "c1": c1_id, "c2": c2_id, "c3": c3_id, "c4": c4_id}
        )
        await session.execute(
            sa.text("DELETE FROM publicaciones WHERE id IN (:pid, :c1, :c2, :c3, :c4)"),
            {"pid": pub_origen_id, "c1": c1_id, "c2": c2_id, "c3": c3_id, "c4": c4_id}
        )
        await session.commit()
