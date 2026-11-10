import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator
from backend_estudiantil.adapters.security.password_hasher import hash_password
from backend_estudiantil.infrastructure.main import app


from backend_estudiantil.adapters.db import (
    AuditoriaLogORM,
    CalificacionORM,
    MatchORM,
    OrganizacionORM,
    PublicacionORM,
    ReporteORM,
    SancionORM,
    TruequeORM,
    UserORM,
    get_session_factory,
)
from backend_estudiantil.domain.models.user import User
from backend_estudiantil.domain.services.calificacion_service import CalificacionService
from backend_estudiantil.domain.services.moderacion_contenido_service import (
    ModeracionContenidoService,
)
from backend_estudiantil.domain.services.moderacion_sanciones_service import (
    ModeracionSancionesService,
    usuario_puede_operar,
)
from backend_estudiantil.domain.validators.isbn_validator import validar_isbn


def create_access_token(data: dict) -> str:
    return JWTAuthenticator().create_access_token(data)

# ==============================================================================
# 1. PRUEBAS DE VALIDACIÓN DE ISBN
# ==============================================================================

@pytest.mark.unit
def test_isbn_validator_valid_and_invalid():
    """Verifica el cálculo de dígito de control para ISBN-10 y ISBN-13."""
    # ISBN-10 Válidos (con guiones, sin guiones y con dígito 'X')
    assert validar_isbn("0-306-40615-2") is True
    assert validar_isbn("0471958697") is True
    assert validar_isbn("0-8044-2957-X") is True

    # ISBN-13 Válidos
    assert validar_isbn("978-0-306-40615-7") is True
    assert validar_isbn("9780471958697") is True

    # None o vacío es permitido (el ISBN es opcional)
    assert validar_isbn(None) is True
    assert validar_isbn("") is True
    assert validar_isbn("   ") is True

    # ISBN Inválidos (checksum incorrecto)
    with pytest.raises(ValueError, match="no es un ISBN-10 válido"):
        validar_isbn("0-306-40615-3")

    with pytest.raises(ValueError, match="no es un ISBN-13 válido"):
        validar_isbn("978-0-306-40615-8")

    # Longitudes inválidas o caracteres no numéricos
    with pytest.raises(ValueError, match="debe tener 10 o 13 dígitos"):
        validar_isbn("12345")

    with pytest.raises(ValueError, match="no es un ISBN-10 válido"):
        validar_isbn("030640615A")


# ==============================================================================
# 2. PRUEBAS DE CONTENIDO PROHIBIDO (ENLACES, TELÉFONOS, DINERO/VENTA)
# ==============================================================================

@pytest.mark.unit
def test_moderacion_contenido_prohibido():
    """Valida que ModeracionContenidoService detecte enlaces, teléfonos y ventas en dinero."""
    service = ModeracionContenidoService()

    # Enlaces externos
    res_enlace = service.procesar_contenido_publicacion(
        "Visita mi web https://librosbaratos.com para ver más fotos",
        campo="descripción"
    )
    assert res_enlace.es_valido is False
    assert "enlaces externos" in res_enlace.mensaje_error

    # Teléfonos / Datos personales
    res_tel = service.procesar_contenido_publicacion(
        "Libro de Física 3001234567 escríbeme por whatsapp",
        campo="título"
    )
    assert res_tel.es_valido is False
    assert "teléfonos o datos de contacto" in res_tel.mensaje_error

    # Ofertas de venta con dinero (la plataforma es de trueque)
    res_dinero = service.procesar_contenido_publicacion(
        "Lo vendo por $50.000 pesos o transferencia nequi",
        campo="descripción"
    )
    assert res_dinero.es_valido is False
    assert "ofertas de venta" in res_dinero.mensaje_error or "venta con dinero" in res_dinero.mensaje_error

    # Contenido legítimo pasa sin error
    res_ok = service.procesar_contenido_publicacion(
        "Cálculo Multivariable Stewart",
        campo="título"
    )
    assert res_ok.es_valido is True
    assert "Stewart" in res_ok.texto_final


# ==============================================================================
# 3. PRUEBAS DE PROMEDIO BAYESIANO Y NIVELES DE REPUTACIÓN
# ==============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_promedio_bayesiano_y_niveles():
    """Valida la fórmula bayesiana (C*m + suma)/(C + n) y los niveles nuevo/confiable/destacado."""
    class DummyCalificacionRepo:
        def __init__(self, stats, user_ratings):
            self.stats = stats
            self.user_ratings = user_ratings

        async def get_global_rating_stats(self):
            return self.stats

        async def list_by_usuario_calificado(self, user_id):
            return self.user_ratings

    class DummyRating:
        def __init__(self, estrellas):
            self.id = 1
            self.trueque_id = 1
            self.usuario_califica_id = 1
            self.estrellas = estrellas
            self.resena = "Buena experiencia"
            self.fecha_calificacion = None

    # Caso 1: 2 calificaciones de 5 estrellas -> n < 3 -> "nuevo"
    repo1 = DummyCalificacionRepo(stats=(4.0, 50), user_ratings=[DummyRating(5), DummyRating(5)])
    service1 = CalificacionService(repo1)
    res1 = await service1.obtener_reputacion_usuario(1)
    assert res1["nivel"] == "nuevo"
    assert res1["promedio_simple"] == 5.0
    # Bayesiano: (5*4.0 + 10) / (5 + 2) = 30 / 7 = 4.29
    assert res1["promedio_bayesiano"] == 4.29

    # Caso 2: 5 calificaciones de 4 estrellas -> "confiable"
    repo2 = DummyCalificacionRepo(stats=(4.0, 50), user_ratings=[DummyRating(4) for _ in range(5)])
    service2 = CalificacionService(repo2)
    res2 = await service2.obtener_reputacion_usuario(1)
    assert res2["nivel"] == "confiable"
    # Bayesiano: (5*4.0 + 20) / (5 + 5) = 40 / 10 = 4.0
    assert res2["promedio_bayesiano"] == 4.0

    # Caso 3: 12 calificaciones de 5 estrellas -> bayesiano >= 4.5 con n>=10 -> "destacado"
    repo3 = DummyCalificacionRepo(stats=(4.0, 50), user_ratings=[DummyRating(5) for _ in range(12)])
    service3 = CalificacionService(repo3)
    res3 = await service3.obtener_reputacion_usuario(1)
    assert res3["nivel"] == "destacado"
    # Bayesiano: (5*4.0 + 60) / (5 + 12) = 80 / 17 = 4.71
    assert res3["promedio_bayesiano"] >= 4.5


# ==============================================================================
# 4. PRUEBAS DE DOMINIO: usuario_puede_operar Y EXPIRACIÓN AUTOMÁTICA
# ==============================================================================

@pytest.mark.unit
def test_usuario_puede_operar_regla_centralizada():
    """Valida la regla de dominio única para operar y auto-desbloqueo al pasar la fecha."""
    # Usuario activo
    user_activo = User(
        id=1, email="u1@test.com", password_hash="hash", name="Activo",
        estado_cuenta="activo"
    )
    assert bool(usuario_puede_operar(user_activo)) is True

    # Usuario bloqueado definitivamente
    user_bloqueado = User(
        id=2, email="u2@test.com", password_hash="hash", name="Bloqueado",
        estado_cuenta="bloqueado", motivo_sancion="Falta grave"
    )
    assert bool(usuario_puede_operar(user_bloqueado)) is False

    # Usuario suspendido con fecha futura
    ahora = datetime.now(timezone.utc)
    user_suspendido_vigente = User(
        id=3, email="u3@test.com", password_hash="hash", name="Suspendido",
        estado_cuenta="suspendido",
        fin_suspension=ahora + timedelta(days=5),
        motivo_sancion="Infracciones reiteradas"
    )
    assert bool(usuario_puede_operar(user_suspendido_vigente)) is False

    # Usuario cuya suspensión ya venció -> debe desbloquearse solo (auto-healing)
    user_suspendido_expirado = User(
        id=4, email="u4@test.com", password_hash="hash", name="Expirado",
        estado_cuenta="suspendido",
        fin_suspension=ahora - timedelta(minutes=10),
        motivo_sancion="Ya cumplida"
    )
    assert bool(usuario_puede_operar(user_suspendido_expirado)) is True
    assert user_suspendido_expirado.estado_cuenta == "activo"
    assert user_suspendido_expirado.fin_suspension is None


# ==============================================================================
# 5. PRUEBAS DE ESCALERA DE SANCIONES Y APELACIONES (INTEGRACIÓN)
# ==============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalera_de_sanciones_y_apelacion_unica():
    """Verifica: 3 advertencias -> suspensión 7 días -> apelación única -> levantamiento."""
    factory = get_session_factory()
    uid = uuid.uuid4().hex[:6]

    async with factory() as session:
        # Crear moderador
        mod = UserORM(
            correo_institucional=f"mod_{uid}@usbmed.edu.co",
            password_hash="hash",
            nombre="Moderador",
            apellido="Test",
            rol="moderador",
            tipo_usuario="estudiante",
            estado_cuenta="activo",
        )
        session.add(mod)

        # Crear usuario objetivo
        target = UserORM(
            correo_institucional=f"target_{uid}@usbmed.edu.co",
            password_hash="hash",
            nombre="Usuario",
            apellido="Objetivo",
            rol="usuario",
            tipo_usuario="estudiante",
            estado_cuenta="activo",
        )
        session.add(target)
        await session.commit()
        await session.refresh(mod)
        await session.refresh(target)
        mod_id = mod.id
        target_id = target.id

    service = ModeracionSancionesService()

    # Advertencia 1
    adv1 = await service.aplicar_advertencia(target_id, "Infracción leve 1", moderador_id=mod_id)
    assert adv1["advertencia_id"] is not None

    # Advertencia 2
    adv2 = await service.aplicar_advertencia(target_id, "Infracción leve 2", moderador_id=mod_id)
    assert adv2["advertencia_id"] is not None

    # Verificar que el usuario sigue activo con 2 advertencias
    async with factory() as session:
        u = await session.get(UserORM, target_id)
        assert u.estado_cuenta == "activo"

    # Advertencia 3 -> debe disparar escalamiento a SUSPENSIÓN de 7 días
    adv3 = await service.aplicar_advertencia(target_id, "Infracción leve 3", moderador_id=mod_id)
    assert adv3["advertencia_id"] is not None
    assert adv3["escalado_a_sancion"] is True

    async with factory() as session:
        u = await session.get(UserORM, target_id)
        assert u.estado_cuenta == "suspendido"
        assert u.fin_suspension is not None
        fin_susp = (
            u.fin_suspension
            if u.fin_suspension.tzinfo is not None
            else u.fin_suspension.replace(tzinfo=timezone.utc)
        )
        dias = (fin_susp - datetime.now(timezone.utc)).days
        assert dias >= 6

        # Buscar la sanción registrada
        res_sancion = await session.execute(select(SancionORM).where(SancionORM.usuario_id == target_id))
        sancion = res_sancion.scalars().first()
        assert sancion is not None
        assert sancion.tipo == "suspension_7"
        sancion_id = sancion.id

    # Apelación del usuario
    apelacion = await service.crear_apelacion(sancion_id, target_id, "Pido disculpas, fue un error")
    assert apelacion["apelacion_id"] is not None
    assert apelacion["estado"] == "pendiente"

    # Intentar apelar una segunda vez -> debe ser RECHAZADO (solo 1 apelación por sanción)
    with pytest.raises(ValueError, match="Solo se permite una apelación por sanción"):
        await service.crear_apelacion(sancion_id, target_id, "Segunda apelación")

    # Moderador aprueba la apelación -> sanción levantada y cuenta reactivada
    res_resol = await service.resolver_apelacion(
        apelacion["apelacion_id"],
        moderador_id=mod_id,
        aprobada=True,
        respuesta="Aceptamos las disculpas por ser primera falta",
    )
    assert res_resol["estado"] == "aprobada"

    async with factory() as session:
        u = await session.get(UserORM, target_id)
        assert u.estado_cuenta == "activo"
        assert u.fin_suspension is None

        # Verificar logs de auditoría sin texto ofensivo
        logs = (await session.execute(
            select(AuditoriaLogORM).where(AuditoriaLogORM.usuario_id.in_([target_id, mod_id]))
        )).scalars().all()
        acciones = [log_entry.accion for log_entry in logs]
        assert "ADVERTENCIA_APLICADA" in acciones
        assert "SANCION_APLICADA" in acciones
        assert "APELACION_RESUELTA" in acciones
        assert "SANCION_LEVANTADA" in acciones


# ==============================================================================
# 6. PRUEBAS DE ENFORCEMENT DE SANCIONES EN LOGIN, PUBLICACIONES Y CHAT
# ==============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_enforcement_sanciones_en_login_y_publicaciones():
    """Verifica que un usuario suspendido reciba 403 con motivo y fecha de fin al intentar login y publicar."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    factory = get_session_factory()
    email = f"sancionado_{uid}@usbmed.edu.co"
    password = "Password123*"

    fin_susp = datetime.now(timezone.utc) + timedelta(days=7)

    async with factory() as session:
        target = UserORM(
            correo_institucional=email,
            password_hash=hash_password(password),
            nombre="Usuario",
            apellido="Sancionado",
            rol="usuario",
            tipo_usuario="estudiante",
            estado_cuenta="suspendido",
            fin_suspension=fin_susp,
            motivo_sancion="Vocabulario ofensivo reiterado",
        )
        session.add(target)
        await session.commit()
        await session.refresh(target)
        user_id = target.id

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Intento de login de usuario suspendido -> 403 Forbidden
        login_res = await ac.post("/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 403
        detail = login_res.json()["detail"]
        assert "suspendido" in detail.lower()
        assert "Vocabulario ofensivo" in detail

        token = create_access_token({"sub": str(user_id), "email": email, "rol": "usuario"})
        headers = {"Authorization": f"Bearer {token}"}

        # Intento de crear publicación -> 403 Forbidden
        pub_res = await ac.post("/publicaciones/", headers=headers, json={
            "titulo": "Libro de Álgebra",
            "autor": "Baldor",
            "categoria_id": 1,
            "estado_libro": "bueno",
            "libro_buscado": "Cálculo Stewart",
            "descripcion": "Intercambio por libro de cálculo",
        })
        assert pub_res.status_code == 403
        assert "suspendido" in pub_res.json()["detail"].lower()


# ==============================================================================
# 7. PRUEBAS DE LÍMITE DE PUBLICACIONES CON MENSAJE CLARO
# ==============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_limite_publicaciones_activas_con_mensaje_claro():
    """Valida que un usuario sin verificar no pueda superar 3 activas y reciba el mensaje con desglose."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    factory = get_session_factory()
    email = f"unverified_{uid}@gmail.com"

    try:
        async with factory() as session:
            u = UserORM(
                correo_institucional=email,
                password_hash="hash",
                nombre="Estudiante",
                apellido="NoVerificado",
                rol="usuario",
                tipo_usuario="estudiante",
                estado_cuenta="activo",
                verificado_comunidad=False,
            )
            session.add(u)
            await session.commit()
            await session.refresh(u)
            user_id = u.id

            # Insertar 3 publicaciones activas
            for i in range(3):
                p = PublicacionORM(
                    usuario_id=user_id,
                    titulo=f"Libro {i}",
                    autor="Autor",
                    categoria_id=1,
                    estado_libro="bueno",
                    libro_buscado="Buscado",
                    estado_publicacion="activa",
                )
                session.add(p)
            await session.commit()

        token = create_access_token({"sub": str(user_id), "email": email, "rol": "usuario"})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/publicaciones/", headers=headers, json={
                "titulo": "Libro Excedente",
                "autor": "Autor",
                "categoria_id": 1,
                "estado_libro": "bueno",
                "libro_buscado": "Cálculo",
                "descripcion": "Descripción válida para intercambio",
            })
            assert res.status_code == 400
            msg = res.json()["detail"]
            assert "tienes 3 activas" in msg
            assert "3 publicaciones activas" in msg
            assert "sube a 10" in msg
    finally:
        async with factory() as session:
            from sqlalchemy import text
            await session.execute(text("DELETE FROM publicaciones WHERE usuario_id = :uid"), {"uid": user_id})
            await session.execute(text("DELETE FROM usuarios WHERE id = :uid"), {"uid": user_id})
            await session.commit()


# ==============================================================================
# 8. PRUEBAS DE REPORTE DE RESEÑAS
# ==============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_reportar_resena_endpoint():
    """Valida el endpoint para que los usuarios reporten una reseña a moderación."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    factory = get_session_factory()

    calif_id = None
    rep_id = None
    trueque_id = None
    match_id = None
    p1_id = None
    p2_id = None
    reporter_id = None
    reviewed_id = None

    try:
        async with factory() as session:
            reporter = UserORM(
                correo_institucional=f"reporter_{uid}@usbmed.edu.co",
                password_hash="hash",
                nombre="Reportante",
                apellido="Prueba",
                rol="usuario",
                tipo_usuario="estudiante",
                estado_cuenta="activo",
            )
            reviewed = UserORM(
                correo_institucional=f"reviewed_{uid}@usbmed.edu.co",
                password_hash="hash",
                nombre="Calificado",
                apellido="Prueba",
                rol="usuario",
                tipo_usuario="estudiante",
                estado_cuenta="activo",
            )
            session.add_all([reporter, reviewed])
            await session.flush()
            reporter_id = reporter.id
            reviewed_id = reviewed.id

            # Publicaciones para el match
            p1 = PublicacionORM(
                usuario_id=reporter.id,
                titulo="Libro P1",
                autor="Autor P1",
                categoria_id=1,
                estado_publicacion="activa",
            )
            p2 = PublicacionORM(
                usuario_id=reviewed.id,
                titulo="Libro P2",
                autor="Autor P2",
                categoria_id=1,
                estado_publicacion="activa",
            )
            session.add_all([p1, p2])
            await session.flush()
            p1_id = p1.id
            p2_id = p2.id

            match = MatchORM(
                publicacion_origen_id=p1.id,
                publicacion_destino_id=p2.id,
                tipo_match="similar",
                puntuacion=10,
            )
            session.add(match)
            await session.flush()
            match_id = match.id

            trueque = TruequeORM(
                match_id=match.id,
                usuario_propone_id=reporter.id,
                usuario_recibe_id=reviewed.id,
                estado="completado",
            )
            session.add(trueque)
            await session.flush()
            trueque_id = trueque.id

            calif = CalificacionORM(
                trueque_id=trueque.id,
                usuario_califica_id=reporter.id,
                usuario_calificado_id=reviewed.id,
                estrellas=1,
                resena="Comentario difamatorio",
            )
            session.add(calif)
            await session.commit()
            await session.refresh(calif)
            calif_id = calif.id

        token = create_access_token({"sub": str(reporter_id), "email": f"reporter_{uid}@usbmed.edu.co", "rol": "usuario"})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(f"/calificaciones/{calif_id}/reportar", headers=headers, json={
                "motivo": "Reseña falsa y difamatoria"
            })
            assert res.status_code == 201
            assert "exitosa" in res.json()["mensaje"]

            # Verificar que quedó en la tabla reportes
            async with factory() as session:
                rep = (await session.execute(
                    select(ReporteORM).where(ReporteORM.objetivo_id == calif_id, ReporteORM.tipo_objetivo == "calificacion")
                )).scalars().first()
                assert rep is not None
                assert rep.motivo == "Reseña falsa y difamatoria"
                assert rep.estado == "pendiente"
                rep_id = rep.id
    finally:
        async with factory() as session:
            from sqlalchemy import text
            if rep_id:
                await session.execute(text("DELETE FROM reportes WHERE id = :rid"), {"rid": rep_id})
            if calif_id:
                await session.execute(text("DELETE FROM calificaciones WHERE id = :cid"), {"cid": calif_id})
            if trueque_id:
                await session.execute(text("DELETE FROM trueques WHERE id = :tid"), {"tid": trueque_id})
            if match_id:
                await session.execute(text("DELETE FROM matches WHERE id = :mid"), {"mid": match_id})
            if p1_id and p2_id:
                await session.execute(text("DELETE FROM publicaciones WHERE id IN (:p1, :p2)"), {"p1": p1_id, "p2": p2_id})
            if reporter_id and reviewed_id:
                await session.execute(text("DELETE FROM usuarios WHERE id IN (:u1, :u2)"), {"u1": reporter_id, "u2": reviewed_id})
            await session.commit()


# ==============================================================================
# 9. PRUEBAS DE ORGANIZACIONES Y ASIGNACIÓN POR DOMINIO
# ==============================================================================

@pytest.mark.integration
@pytest.mark.asyncio
async def test_organizacion_por_defecto_seed():
    """Verifica que la organización USB Medellín exista en la base y tenga el dominio usbmed.edu.co."""
    factory = get_session_factory()
    async with factory() as session:
        res = await session.execute(
            select(OrganizacionORM).where(OrganizacionORM.nombre == "Universidad de San Buenaventura Medellín")
        )
        org = res.scalars().first()
        assert org is not None
        assert "usbmed.edu.co" in org.dominios
        assert org.tipo == "universidad"
