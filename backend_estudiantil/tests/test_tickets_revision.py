import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from backend_estudiantil.adapters.db import (
    PublicacionORM,
    UserORM,
    VerificacionPublicacionORM,
    get_session_factory,
)
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator
from backend_estudiantil.infrastructure.main import app

pytestmark = pytest.mark.integration


def _crear_token(user_id: int, role: str = "usuario") -> str:
    return JWTAuthenticator().create_access_token({"sub": str(user_id), "role": role})


@pytest.mark.asyncio
async def test_flujo_completo_tickets_revision():
    tag = uuid.uuid4().hex[:6]
    factory = get_session_factory()
    async with factory() as session:
        estudiante = UserORM(
            nombre=f"Carlos {tag}",
            apellido="Estudiante",
            correo_institucional=f"carlos_{tag}@usbmed.edu.co",
            password_hash="dummyhash",
            rol="usuario",
            estado_cuenta="activo",
        )
        moderador = UserORM(
            nombre=f"Laura {tag}",
            apellido="Moderadora",
            correo_institucional=f"laura_{tag}@usbmed.edu.co",
            password_hash="dummyhash",
            rol="moderador",
            estado_cuenta="activo",
        )
        otro = UserORM(
            nombre=f"Pedro {tag}",
            apellido="Ajeno",
            correo_institucional=f"pedro_{tag}@usbmed.edu.co",
            password_hash="dummyhash",
            rol="usuario",
            estado_cuenta="activo",
        )
        session.add_all([estudiante, moderador, otro])
        await session.flush()

        titulo_libro = f"Cálculo Diferencial {tag}"
        pub = PublicacionORM(
            usuario_id=estudiante.id,
            titulo=titulo_libro,
            autor="James Stewart",
            estado_publicacion="inactiva",
        )
        session.add(pub)
        await session.flush()

        verif = VerificacionPublicacionORM(
            publicacion_id=pub.id,
            usuario_id=estudiante.id,
            codigo_hash="dummycodehash",
            estado="pendiente_revision",
            vence_en=pub.fecha_publicacion,
        )
        session.add(verif)
        await session.commit()

        estudiante_id = estudiante.id
        moderador_id = moderador.id
        otro_id = otro.id
        pub_id = pub.id
        verif_id = verif.id

    token_estudiante = _crear_token(estudiante_id, role="usuario")
    token_moderador = _crear_token(moderador_id, role="moderador")
    token_otro = _crear_token(otro_id, role="usuario")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 2. Otro estudiante no puede abrir ticket para libro ajeno (403)
        resp_ajeno = await client.post(
            "/tickets",
            json={
                "publicacion_id": pub_id,
                "asunto": "Intento no autorizado",
                "mensaje_inicial": "No es mi libro",
                "prioridad": "media",
            },
            headers={"Authorization": f"Bearer {token_otro}"},
        )
        assert resp_ajeno.status_code == 403

        # 3. Moderador abre ticket para comunicarse con el estudiante sobre su libro en revisión
        resp_mod = await client.post(
            "/tickets",
            json={
                "publicacion_id": pub_id,
                "asunto": "Fotos borrosas en verificación de libro",
                "mensaje_inicial": "Hola Carlos, la foto de la página legal no se lee bien. ¿Puedes volver a subirla?",
                "prioridad": "alta",
            },
            headers={"Authorization": f"Bearer {token_moderador}"},
        )
        assert resp_mod.status_code == 201
        ticket_data = resp_mod.json()
        ticket_id = ticket_data["id"]
        assert ticket_data["asunto"] == "Fotos borrosas en verificación de libro"
        assert ticket_data["estado"] == "esperando_estudiante"
        assert ticket_data["usuario_id"] == estudiante_id
        assert ticket_data["moderador_id"] == moderador_id
        assert len(ticket_data["mensajes"]) == 1
        assert "Hola Carlos" in ticket_data["mensajes"][0]["contenido"]

        # 4. Estudiante lista sus tickets y ve el ticket abierto por el moderador
        resp_mis = await client.get(
            "/tickets/mis-tickets",
            headers={"Authorization": f"Bearer {token_estudiante}"},
        )
        assert resp_mis.status_code == 200
        mis_tickets = resp_mis.json()
        assert len(mis_tickets) == 1
        assert mis_tickets[0]["id"] == ticket_id
        assert mis_tickets[0]["publicacion_titulo"] == titulo_libro

        # 5. Estudiante responde en el ticket
        resp_resp = await client.post(
            f"/tickets/{ticket_id}/mensajes",
            json={"contenido": "Hola Laura, acabo de subir una foto mucho más clara con buena iluminación."},
            headers={"Authorization": f"Bearer {token_estudiante}"},
        )
        assert resp_resp.status_code == 201
        msg_data = resp_resp.json()
        assert msg_data["remitente_id"] == estudiante_id

        # 6. Al responder el estudiante, el estado del ticket pasa a 'en_revision'
        resp_det = await client.get(
            f"/tickets/{ticket_id}",
            headers={"Authorization": f"Bearer {token_moderador}"},
        )
        assert resp_det.status_code == 200
        det_data = resp_det.json()
        assert det_data["estado"] == "en_revision"
        assert len(det_data["mensajes"]) == 2

        # 7. Moderador resuelve el ticket
        resp_est = await client.patch(
            f"/tickets/{ticket_id}/estado",
            json={"estado": "resuelto"},
            headers={"Authorization": f"Bearer {token_moderador}"},
        )
        assert resp_est.status_code == 200
        assert resp_est.json()["estado"] == "resuelto"

        # 8. Probar shortcut desde verificación: /tickets/desde-verificacion/{verificacion_id}
        resp_shortcut = await client.post(
            f"/tickets/desde-verificacion/{verif_id}",
            json={"contenido": "Revisión final: Libro validado correctamente."},
            headers={"Authorization": f"Bearer {token_moderador}"},
        )
        assert resp_shortcut.status_code == 201
        shortcut_data = resp_shortcut.json()
        assert shortcut_data["publicacion_id"] == pub_id
