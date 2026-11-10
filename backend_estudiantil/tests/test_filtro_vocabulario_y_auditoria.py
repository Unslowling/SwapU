import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from backend_estudiantil.infrastructure.main import app
from backend_estudiantil.adapters.db import (
    get_session_factory, UserORM, TruequeORM, PublicacionORM, MatchORM, AuditoriaLogORM
)
from backend_estudiantil.domain.services.moderacion_contenido_service import (
    ModeracionContenidoService,
)
from sqlalchemy import select, desc, text

pytestmark = pytest.mark.integration


@pytest.fixture
def mod_service():
    return ModeracionContenidoService()


def test_normalizacion_y_leetspeak(mod_service):
    """Prueba que el normalizador elimine tildes, letras repetidas y leetspeak."""
    # Tildes
    assert mod_service.normalizar("Estúpido") == "estupido"
    # Leetspeak (@->a, 0->o, 3->e)
    assert mod_service.normalizar("g0n0rr3@") == "gonorrea"
    # Letras repetidas
    assert mod_service.normalizar("malparrrriiiiidooooo") == "malparido"


def test_clasificacion_por_severidad(mod_service):
    """Prueba la clasificación exacta por niveles de severidad en modismos colombianos."""
    # 1. Leve -> Enmascara palabra
    res_leve = mod_service.procesar_texto("Hola, qué libro tan estupido")
    assert res_leve.es_valido is True
    assert res_leve.nivel_severidad == "leve"
    assert "e******o" in res_leve.texto_final or "e" in res_leve.texto_final
    assert "estupido" not in res_leve.texto_final.lower()
    assert res_leve.accion_auditoria == "INFRACCION_VOCABULARIO"

    # 2. Media -> Advertir y bloquear
    res_media = mod_service.procesar_texto("Usted es un gonorrea")
    assert res_media.es_valido is False
    assert res_media.nivel_severidad == "media"
    assert res_media.accion == "advertir"
    assert res_media.accion_auditoria == "ADVERTENCIA_APLICADA"

    # 3. Grave -> Bloquear
    res_grave = mod_service.procesar_texto("Te vendo cocaina pura y barata")
    assert res_grave.es_valido is False
    assert res_grave.nivel_severidad == "grave"
    assert res_grave.accion == "bloquear"
    assert res_grave.accion_auditoria == "SANCION_APLICADA"


@pytest.mark.asyncio
async def test_chat_rest_y_auditoria_sin_texto_crudo():
    """Verifica que el chat filtre vocabulario y audite la infracción SIN almacenar el mensaje completo."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    factory = get_session_factory()
    tid = None
    mid = None
    pids = []
    uids = []
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Crear usuarios e intercambio
            email1 = f"u1_chat_{uid}@unal.edu.co"
            email2 = f"u2_chat_{uid}@unal.edu.co"
            await ac.post("/auth/register", json={"email": email1, "password": "Password123*", "name": "Usuario Uno", "carrera": "Sistemas"})
            await ac.post("/auth/register", json={"email": email2, "password": "Password123*", "name": "Usuario Dos", "carrera": "Sistemas"})

            l1 = await ac.post("/auth/login", json={"email": email1, "password": "Password123*"})
            token1 = l1.json()["access_token"]
            headers1 = {"Authorization": f"Bearer {token1}"}

            # Obtener IDs y crear trueque con match asociado
            async with factory() as session:
                q1 = await session.execute(select(UserORM).where(UserORM.correo_institucional == email1))
                user1 = q1.scalar_one()
                q2 = await session.execute(select(UserORM).where(UserORM.correo_institucional == email2))
                user2 = q2.scalar_one()
                uids = [user1.id, user2.id]

                pub1 = PublicacionORM(
                    titulo=f"Libro A {uid}",
                    autor="Autor A",
                    categoria_id=1,
                    usuario_id=user1.id,
                    estado_publicacion="activa",
                )
                pub2 = PublicacionORM(
                    titulo=f"Libro B {uid}",
                    autor="Autor B",
                    categoria_id=1,
                    usuario_id=user2.id,
                    estado_publicacion="activa",
                )
                session.add_all([pub1, pub2])
                await session.flush()
                pids = [pub1.id, pub2.id]

                match = MatchORM(
                    publicacion_origen_id=pub1.id,
                    publicacion_destino_id=pub2.id,
                    tipo_match="similar",
                    puntuacion=10,
                )
                session.add(match)
                await session.flush()
                mid = match.id

                trueque = TruequeORM(
                    match_id=match.id,
                    usuario_propone_id=user1.id,
                    usuario_recibe_id=user2.id,
                    estado="propuesto",
                )
                session.add(trueque)
                await session.commit()
                await session.refresh(trueque)
                tid = trueque.id

            # 1. Enviar mensaje con insulto medio ("pirobo") -> 400 Bad Request
            insulto_medio = "Oiga usted es un tremendo pirobo"
            res_msg = await ac.post(f"/trueques/{tid}/mensajes", json={"contenido": insulto_medio}, headers=headers1)
            assert res_msg.status_code == 400
            assert "vocabulario inadecuado" in res_msg.json()["detail"].lower() or "advertencia" in res_msg.json()["detail"].lower()

            # 2. Verificar que se haya registrado en AuditoriaLogORM y que NO contenga el texto completo
            async with factory() as session:
                stmt = select(AuditoriaLogORM).where(
                    AuditoriaLogORM.usuario_id == user1.id,
                    AuditoriaLogORM.accion == "ADVERTENCIA_APLICADA",
                ).order_by(desc(AuditoriaLogORM.fecha_hora)).limit(1)
                audit_entry = (await session.execute(stmt)).scalar_one_or_none()
                assert audit_entry is not None
                assert audit_entry.accion == "ADVERTENCIA_APLICADA"
                assert audit_entry.exito is False
                # Detalle contiene severidad y conteo, NO el texto del insulto
                assert "severidad=media" in audit_entry.detalle
                assert insulto_medio not in audit_entry.detalle
                assert "pirobo" not in audit_entry.detalle

            # 3. Enviar mensaje con insulto leve ("estupido") -> 201 Created y texto enmascarado
            res_leve = await ac.post(f"/trueques/{tid}/mensajes", json={"contenido": "Eso fue muy estupido de tu parte"}, headers=headers1)
            assert res_leve.status_code == 201
            contenido_guardado = res_leve.json()["contenido"]
            assert "estupido" not in contenido_guardado.lower()
            assert "*" in contenido_guardado
    finally:
        from sqlalchemy import delete as sa_delete
        from backend_estudiantil.adapters.db import MensajeORM
        async with factory() as session:
            if tid:
                await session.execute(sa_delete(MensajeORM).where(MensajeORM.trueque_id == tid))
                await session.execute(sa_delete(TruequeORM).where(TruequeORM.id == tid))
            if mid:
                await session.execute(sa_delete(MatchORM).where(MatchORM.id == mid))
            if pids:
                await session.execute(sa_delete(PublicacionORM).where(PublicacionORM.id.in_(pids)))
            if uids:
                await session.execute(sa_delete(AuditoriaLogORM).where(AuditoriaLogORM.usuario_id.in_(uids)))
                await session.execute(sa_delete(UserORM).where(UserORM.id.in_(uids)))
            await session.commit()


@pytest.mark.asyncio
async def test_moderacion_en_publicaciones_y_resenas():
    """Verifica que el título/descripción de publicación y la reseña sean moderados."""
    transport = ASGITransport(app=app)
    uid = uuid.uuid4().hex[:6]
    created_pub_id = None
    factory = get_session_factory()
    email = f"autor_mod_{uid}@unal.edu.co"
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            await ac.post("/auth/register", json={"email": email, "password": "Password123*", "name": "Autor Mod", "carrera": "Diseño"})
            login_res = await ac.post("/auth/login", json={"email": email, "password": "Password123*"})
            headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

            # Intentar crear publicación con término grave en título -> 400 Bad Request
            res_pub_grave = await ac.post("/publicaciones/", json={
                "titulo": "Manual de sicario profesional",
                "autor": "Anónimo",
                "categoria_id": 1,
            }, headers=headers)
            assert res_pub_grave.status_code == 400
            assert "bloqueada por contenido" in res_pub_grave.json()["detail"].lower() or "grave" in res_pub_grave.json()["detail"].lower()

            # Crear publicación con término leve -> Éxito con título enmascarado
            res_pub_leve = await ac.post("/publicaciones/", json={
                "titulo": "Guía de física para bobo novato",
                "autor": "Profesor",
                "categoria_id": 1,
            }, headers=headers)
            assert res_pub_leve.status_code == 201
            assert "bobo" not in res_pub_leve.json()["titulo"].lower()
            assert "*" in res_pub_leve.json()["titulo"]
            created_pub_id = res_pub_leve.json().get("id")
    finally:
        async with factory() as session:
            if created_pub_id:
                await session.execute(text("DELETE FROM publicaciones WHERE id = :id"), {"id": created_pub_id})
            await session.execute(text("DELETE FROM usuarios WHERE correo_institucional = :email"), {"email": email})
            await session.commit()
