import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from starlette.websockets import WebSocketDisconnect

from backend_estudiantil.infrastructure.main import app
from backend_estudiantil.tests._admin_helpers import convertir_en_administrador

pytestmark = pytest.mark.integration


@pytest.fixture
def api_client(isolated_db):
    with TestClient(app) as client:
        yield client


def _register_and_login(client: TestClient, name: str, email: str, role: str = "user"):
    response = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "password123", "role": role},
    )
    assert response.status_code == 201
    if role == "admin":
        # El registro público no concede roles: se asigna en la SQLite temporal de la prueba
        convertir_en_administrador(email)
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _photo(code: str, title: str) -> bytes:
    image = Image.new("RGB", (700, 900), "white")
    draw = ImageDraw.Draw(image)
    draw.text((40, 40), code, fill="black")
    draw.text((40, 150), title, fill="black")
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def _verify_publication(client, owner_headers, reviewer_headers, publication):
    publication_id = publication["id"]
    challenge = client.post(
        f"/publicaciones/{publication_id}/verificacion/desafios",
        headers=owner_headers,
    )
    assert challenge.status_code == 201, challenge.text
    verification = challenge.json()
    code = verification["codigo"]
    evidence = client.post(
        f"/publicaciones/{publication_id}/verificacion/evidencias",
        headers=owner_headers,
        data={"verificacion_id": verification["verificacion_id"], "codigo": code},
        files={
            "foto_portada": (
                "portada.jpg",
                _photo(code, publication["titulo"]),
                "image/jpeg",
            ),
            "foto_pagina_isbn": (
                "isbn.jpg",
                _photo(code, publication["isbn"] or "Página legal"),
                "image/jpeg",
            ),
        },
    )
    assert evidence.status_code == 201, evidence.text
    evidence_data = evidence.json()
    if evidence_data.get("estado") != "aprobada":
        pending = client.get(
            "/publicaciones/verificaciones/pendientes", headers=reviewer_headers
        )
        assert pending.status_code == 200
        assert verification["verificacion_id"] in {
            item["verificacion_id"] for item in pending.json()
        }
        image = client.get(
            f"/publicaciones/verificaciones/{verification['verificacion_id']}/evidencia/portada",
            headers=reviewer_headers,
        )
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/jpeg"
        approved = client.post(
            f"/publicaciones/verificaciones/{verification['verificacion_id']}/revision",
            headers=reviewer_headers,
            json={"decision": "aprobada", "nota": "Portada e ISBN revisados"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["estado_publicacion"] == "activa"


def test_publish_book_and_complete_authenticated_trade_conversation(api_client):
    suffix = uuid4().hex
    headers_a = _register_and_login(api_client, "Estudiante A", f"a-{suffix}@example.com")
    headers_b = _register_and_login(api_client, "Estudiante B", f"b-{suffix}@example.com")
    headers_other = _register_and_login(api_client, "Estudiante C", f"c-{suffix}@example.com")
    headers_admin = _register_and_login(
        api_client, "Administrador", f"admin-{suffix}@example.com", role="admin"
    )
    headers_reviewer = _register_and_login(
        api_client, "Moderación", f"moderator-{suffix}@example.com"
    )
    reviewer = api_client.get("/usuarios/me", headers=headers_reviewer)
    assert reviewer.status_code == 200
    promotion = api_client.post(
        f"/admin/users/{reviewer.json()['id']}/promote", headers=headers_admin
    )
    assert promotion.status_code == 200, promotion.text

    publication_a = api_client.post(
        "/publicaciones/",
        headers=headers_a,
        json={
            "titulo": "Cálculo",
            "categoria_id": 3,
            "estado_libro": "Buen estado",
            "libro_buscado": "Física",
        },
    )
    publication_b = api_client.post(
        "/publicaciones/",
        headers=headers_b,
        json={
            "titulo": "Física",
            "categoria_id": 3,
            "estado_libro": "Como nuevo",
            "libro_buscado": "Cálculo",
        },
    )
    assert publication_a.status_code == 201
    assert publication_b.status_code == 201
    assert publication_a.json()["categoria_id"] == 3
    assert publication_a.json()["estado_publicacion"] == "inactiva"
    _verify_publication(api_client, headers_a, headers_reviewer, publication_a.json())
    _verify_publication(api_client, headers_b, headers_reviewer, publication_b.json())
    catalog = api_client.get("/publicaciones/")
    assert {book["id"] for book in catalog.json()} >= {
        publication_a.json()["id"],
        publication_b.json()["id"],
    }

    proposal = api_client.post(
        "/trueques/proponer",
        headers=headers_a,
        json={
            "publicacion_origen_id": publication_a.json()["id"],
            "publicacion_destino_id": publication_b.json()["id"],
            "usuario_recibe_id": publication_b.json()["usuario_id"],
        },
    )
    assert proposal.status_code == 201, proposal.text
    trade_id = proposal.json()["id"]
    available_matches = api_client.get("/matches/mis-matches", headers=headers_a)
    assert available_matches.status_code == 200
    assert proposal.json()["match_id"] not in {
        match["id"] for match in available_matches.json()
    }

    duplicate_proposal = api_client.post(
        "/trueques/",
        headers=headers_a,
        json={
            "publicacion_origen_id": publication_a.json()["id"],
            "publicacion_destino_id": publication_b.json()["id"],
        },
    )
    assert duplicate_proposal.status_code == 400

    info = api_client.get(f"/trueques/{trade_id}/info", headers=headers_a)
    assert info.status_code == 200
    assert info.json()["libro_propone"] == "Cálculo"
    assert info.json()["libro_recibe"] == "Física"

    message_a = api_client.post(
        f"/trueques/{trade_id}/mensajes",
        headers=headers_a,
        json={"contenido": "¿Nos vemos en la biblioteca?"},
    )
    assert message_a.status_code == 201
    message_b = api_client.post(
        f"/trueques/{trade_id}/mensajes",
        headers=headers_b,
        json={"contenido": "Sí, mañana a las tres."},
    )
    assert message_b.status_code == 201

    with (
        pytest.raises(WebSocketDisconnect) as disconnected,
        api_client.websocket_connect(
            f"/trueques/{trade_id}/ws",
            subprotocols=["bearer", headers_other["Authorization"].split(" ", 1)[1]],
        ),
    ):
        pass
    assert disconnected.value.code == 4403

    with api_client.websocket_connect(
        f"/trueques/{trade_id}/ws",
        subprotocols=["bearer", headers_b["Authorization"].split(" ", 1)[1]],
    ) as conversation:
        realtime_message = api_client.post(
            f"/trueques/{trade_id}/mensajes",
            headers=headers_a,
            json={"contenido": "Mensaje recibido en tiempo real."},
        )
        assert realtime_message.status_code == 201
        ws_msg = conversation.receive_json()
        if ws_msg.get("type") == "room_state":
            ws_msg = conversation.receive_json()
        assert ws_msg["contenido"] == "Mensaje recibido en tiempo real."

    history = api_client.get(f"/trueques/{trade_id}/mensajes", headers=headers_a)
    assert history.status_code == 200
    assert [message["contenido"] for message in history.json()] == [
        "¿Nos vemos en la biblioteca?",
        "Sí, mañana a las tres.",
        "Mensaje recibido en tiempo real.",
    ]
    latest_messages = api_client.get(
        f"/trueques/{trade_id}/mensajes?limit=2", headers=headers_a
    )
    assert [message["contenido"] for message in latest_messages.json()] == [
        "Sí, mañana a las tres.",
        "Mensaje recibido en tiempo real.",
    ]
    earlier_messages = api_client.get(
        f"/trueques/{trade_id}/mensajes?limit=2&before_id={latest_messages.json()[0]['id']}",
        headers=headers_a,
    )
    assert [message["contenido"] for message in earlier_messages.json()] == [
        "¿Nos vemos en la biblioteca?"
    ]

    confirmed = api_client.post(f"/trueques/{trade_id}/confirmar", headers=headers_b)
    assert confirmed.status_code == 200
    completed = api_client.post(f"/trueques/{trade_id}/completar", headers=headers_a)
    assert completed.status_code == 200

    closed_chat_message = api_client.post(
        f"/trueques/{trade_id}/mensajes",
        headers=headers_a,
        json={"contenido": "Mensaje posterior al cierre"},
    )
    assert closed_chat_message.status_code == 400

    outside_history = api_client.get(
        f"/trueques/{trade_id}/mensajes", headers=headers_other
    )
    assert outside_history.status_code == 403
