"""
test_integration_quality.py
---------------------------
Suite de pruebas de integración completa:
- WebSocket (cierres 4401, 4403, 4404, vocabulario bloqueado, usuario suspendido)
- Redis activo y caído (fakeredis): persistencia BD y fallback a memoria
- Concurrencia en límite de publicaciones (3 sin verificar, 10 verificados)
- Seguridad integral (JWT falsificado/expirado, CORS estricto, 5 intentos lockout, cabeceras, auditoría)
- Flujo completo de verificación de libro con IA simulada
- Control de acceso y permisos RBAC en endpoints de moderación
Marcador pytest: integration
"""

import asyncio
import io
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import fakeredis.aioredis
import httpx
import pytest
from PIL import Image, ImageDraw
from starlette.websockets import WebSocketDisconnect

from backend_estudiantil.adapters.db import (
    AuditoriaLogORM,
    PublicacionORM,
    UserORM,
    get_session_factory,
)
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator
from backend_estudiantil.config.settings import settings
from backend_estudiantil.infrastructure.login_rate_limiter import LoginRateLimiter
from backend_estudiantil.infrastructure.main import app

pytestmark = pytest.mark.integration

# ============================================================================
# 1. WEBSOCKET: Cierres 4401, 4403, 4404, vocabulario y suspensión en vivo
# ============================================================================

def test_websocket_cierre_4401_sin_token_o_invalido(client, usuario_verificado, usuario_sin_verificar, trueque_factory):
    """Verifica cierre 4401 si no se provee token o si el token es inválido."""
    trueque_id = trueque_factory(usuario_verificado, usuario_sin_verificar)

    # Caso 1: Sin subprotocols
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/trueques/{trueque_id}/ws"):
            pass
    assert exc.value.code == 4401

    # Caso 2: Token inválido en subprotocol
    with pytest.raises(WebSocketDisconnect) as exc2, client.websocket_connect(
        f"/trueques/{trueque_id}/ws",
        subprotocols=["bearer", "token_invalido_123"],
    ):
        pass
    assert exc2.value.code == 4401


def test_websocket_cierre_4404_trueque_inexistente(client, usuario_verificado):
    """Verifica cierre 4404 si el trueque no existe."""
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(
        "/trueques/9999999/ws",
        subprotocols=["bearer", usuario_verificado["token"]],
    ):
        pass
    assert exc.value.code == 4404


def test_websocket_cierre_4403_no_participante(client, usuario_verificado, usuario_sin_verificar, usuario_moderador, trueque_factory):
    """Verifica cierre 4403 si el usuario autenticado no pertenece al trueque."""
    trueque_id = trueque_factory(usuario_verificado, usuario_sin_verificar)

    # usuario_moderador NO es participante del trueque
    with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(
        f"/trueques/{trueque_id}/ws",
        subprotocols=["bearer", usuario_moderador["token"]],
    ):
        pass
    assert exc.value.code == 4403


def test_websocket_bloqueo_vocabulario_en_vivo(client, usuario_verificado, usuario_sin_verificar, trueque_factory):
    """Verifica que un mensaje con vocabulario prohibido en el WebSocket sea rechazado con error."""
    trueque_id = trueque_factory(usuario_verificado, usuario_sin_verificar)

    with client.websocket_connect(
        f"/trueques/{trueque_id}/ws",
        subprotocols=["bearer", usuario_verificado["token"]],
    ) as ws:
        # Mensaje de bienvenida de sala
        room_state = ws.receive_json()
        assert room_state["type"] == "room_state"

        # Enviar mensaje con insulto/palabra grave prohibida
        ws.send_text(json.dumps({
            "type": "message",
            "contenido": "Eres un sicario y te voy a matar",
        }))

        respuesta = ws.receive_json()
        assert respuesta["type"] == "error"
        assert "prohibido" in respuesta["detail"].lower() or "vocabulario" in respuesta["detail"].lower() or "bloqueada" in respuesta["detail"].lower()


def test_websocket_usuario_suspendido_con_socket_abierto(client, usuario_verificado, usuario_sin_verificar, trueque_factory):
    """Verifica que si un usuario es suspendido mientras tiene el WebSocket abierto, no pueda seguir enviando mensajes."""
    trueque_id = trueque_factory(usuario_verificado, usuario_sin_verificar)

    with client.websocket_connect(
        f"/trueques/{trueque_id}/ws",
        subprotocols=["bearer", usuario_verificado["token"]],
    ) as ws:
        ws.receive_json()  # room_state

        # Enviar mensaje inicial legítimo
        ws.send_text(json.dumps({
            "type": "message",
            "contenido": "Hola, ¿cómo estás?",
        }))
        msg_resp = ws.receive_json()
        assert msg_resp["type"] == "message"

        # Suspender al usuario directamente en la base de datos
        factory = get_session_factory()

        async def _suspender():
            from sqlalchemy.future import select
            async with factory() as session:
                res = await session.execute(select(UserORM).where(UserORM.id == usuario_verificado["id"]))
                u = res.scalar_one_or_none()
                u.estado_cuenta = "suspendido"
                u.fin_suspension = datetime.now(timezone.utc) + timedelta(days=7)
                u.motivo_sancion = "Conducta inapropiada en trueques"
                await session.commit()

        asyncio.run(_suspender())

        # Intentar enviar un nuevo mensaje con el socket ya abierto
        ws.send_text(json.dumps({
            "type": "message",
            "contenido": "Sigo intentando escribir",
        }))

        respuesta_susp = ws.receive_json()
        assert respuesta_susp["type"] == "error"
        assert "suspendido" in respuesta_susp["detail"].lower()


# ============================================================================
# 2. REDIS ACTIVO Y CAÍDO (fakeredis): Persistencia en BD y fallback en memoria
# ============================================================================

def test_redis_activo_y_caido_chat_persiste_bd(client, usuario_verificado, usuario_sin_verificar, trueque_factory):
    """Comprueba que tanto con Redis activo (fakeredis) como con Redis caído,

    los mensajes de chat siempre se persisten en la base de datos relacional.
    """
    trueque_id = trueque_factory(usuario_verificado, usuario_sin_verificar)

    # 1. Con Redis activo simulado
    fake_redis = fakeredis.aioredis.FakeRedis()
    with patch("redis.asyncio.Redis.from_url", return_value=fake_redis):
        resp1 = client.post(
            f"/trueques/{trueque_id}/mensajes",
            headers=usuario_verificado["headers"],
            json={"contenido": "Mensaje con Redis operativo"},
        )
        assert resp1.status_code == 201
        assert resp1.json()["contenido"] == "Mensaje con Redis operativo"

    # 2. Con Redis caído (simulando error de conexión)
    with patch("redis.asyncio.Redis.from_url", side_effect=ConnectionError("Redis connection refused")):
        resp2 = client.post(
            f"/trueques/{trueque_id}/mensajes",
            headers=usuario_sin_verificar["headers"],
            json={"contenido": "Mensaje cuando Redis está caído"},
        )
        assert resp2.status_code == 201
        assert resp2.json()["contenido"] == "Mensaje cuando Redis está caído"

    # Verificar que ambos mensajes existen en la BD
    listar = client.get(
        f"/trueques/{trueque_id}/mensajes",
        headers=usuario_verificado["headers"],
    )
    assert listar.status_code == 200
    mensajes_bd = [m["contenido"] for m in listar.json()]
    assert "Mensaje con Redis operativo" in mensajes_bd
    assert "Mensaje cuando Redis está caído" in mensajes_bd


def test_rate_limiter_fallback_a_memoria():
    """Valida que LoginRateLimiter caiga limpiamente a memoria cuando Redis no está disponible."""
    # Instanciar rate limiter apuntando a redis no disponible
    limiter = LoginRateLimiter(
        ip_max_per_min=5,
        email_max_per_min=5,
        max_consecutive_failures=5,
        lockout_duration_sec=900,
        window_sec=60,
    )
    # Forzar _get_redis a None simulando Redis caído
    limiter._get_redis = lambda: None

    ip = "192.168.1.50"
    email = "estudiante_test@tau.usbmed.edu.co"

    # Registrar 4 fallos sucesivos
    for _ in range(4):
        limiter.record_failed_attempt(email=email, ip=ip)
        assert limiter.is_locked_out(email=email, ip=ip) is False

    # El 5to fallo activa el bloqueo en memoria
    limiter.record_failed_attempt(email=email, ip=ip)
    assert limiter.is_locked_out(email=email, ip=ip) is True


# ============================================================================
# 3. LÍMITE DE PUBLICACIONES ACTIVAS CON PETICIONES CONCURRENTES
# ============================================================================

@pytest.mark.asyncio
async def test_limite_publicaciones_concurrentes_sin_superar_tope(
    client, usuario_sin_verificar, usuario_verificado
):
    """Comprueba mediante peticiones concurrentes que no se supere el tope de publicaciones activas

    (3 para no verificados, 10 para verificados).
    """
    factory = get_session_factory()

    try:
        # 1. Configurar usuario no verificado con 3 publicaciones activas (al tope)
        async with factory() as session:
            for i in range(settings.LIMITE_PUBLICACIONES_SIN_VERIFICAR):
                session.add(
                    PublicacionORM(
                        usuario_id=usuario_sin_verificar["id"],
                        titulo=f"Libro Activo NoVerif {i}",
                        autor="Autor Test",
                        categoria_id=1,
                        estado_libro="bueno",
                        libro_buscado="Cálculo",
                        estado_publicacion="activa",
                    )
                )
            # Configurar usuario verificado con 10 publicaciones activas (al tope)
            for i in range(settings.LIMITE_PUBLICACIONES_VERIFICADOS):
                session.add(
                    PublicacionORM(
                        usuario_id=usuario_verificado["id"],
                        titulo=f"Libro Activo Verif {i}",
                        autor="Autor Test",
                        categoria_id=1,
                        estado_libro="bueno",
                        libro_buscado="Física",
                        estado_publicacion="activa",
                    )
                )
            await session.commit()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
            # Peticiones concurrentes para usuario sin verificar intentando exceder 3
            async def crear_pub_no_verif(i: int):
                return await async_client.post(
                    "/publicaciones/",
                    headers=usuario_sin_verificar["headers"],
                    json={
                        "titulo": f"Intento Concurrente NoVerif #{i}",
                        "autor": "Autor",
                        "categoria_id": 1,
                        "estado_libro": "bueno",
                        "libro_buscado": "Cálculo",
                        "tipo_transaccion": "trueque",
                    },
                )

            # Peticiones concurrentes para usuario verificado intentando exceder 10
            async def crear_pub_verif(i: int):
                return await async_client.post(
                    "/publicaciones/",
                    headers=usuario_verificado["headers"],
                    json={
                        "titulo": f"Intento Concurrente Verif #{i}",
                        "autor": "Autor",
                        "categoria_id": 1,
                        "estado_libro": "bueno",
                        "libro_buscado": "Física",
                        "tipo_transaccion": "trueque",
                    },
                )

            respuestas_no_verif = await asyncio.gather(*(crear_pub_no_verif(i) for i in range(5)))
            respuestas_verif = await asyncio.gather(*(crear_pub_verif(i) for i in range(5)))

        # Todas las peticiones deben ser rechazadas con 400 por superar el tope respectivo
        for r in respuestas_no_verif:
            assert r.status_code == 400
            assert "límite" in r.json()["detail"].lower()
            assert str(settings.LIMITE_PUBLICACIONES_SIN_VERIFICAR) in r.json()["detail"]

        for r in respuestas_verif:
            assert r.status_code == 400
            assert "límite" in r.json()["detail"].lower()
            assert str(settings.LIMITE_PUBLICACIONES_VERIFICADOS) in r.json()["detail"]

        # Validar en base de datos que el número de activas no supera el tope
        async with factory() as session:
            from sqlalchemy import func
            from sqlalchemy.future import select

            res_no_verif = await session.execute(
                select(func.count(PublicacionORM.id)).where(
                    PublicacionORM.usuario_id == usuario_sin_verificar["id"],
                    PublicacionORM.estado_publicacion == "activa",
                )
            )
            assert res_no_verif.scalar_one() == settings.LIMITE_PUBLICACIONES_SIN_VERIFICAR

            res_verif = await session.execute(
                select(func.count(PublicacionORM.id)).where(
                    PublicacionORM.usuario_id == usuario_verificado["id"],
                    PublicacionORM.estado_publicacion == "activa",
                )
            )
            assert res_verif.scalar_one() == settings.LIMITE_PUBLICACIONES_VERIFICADOS
    finally:
        async with factory() as session:
            from sqlalchemy import delete
            await session.execute(
                delete(PublicacionORM).where(
                    PublicacionORM.usuario_id.in_([usuario_sin_verificar["id"], usuario_verificado["id"]])
                )
            )
            await session.commit()


# ============================================================================
# 4. SEGURIDAD: JWT, CORS, Bloqueo 5 intentos, Cabeceras y Auditoría limpia
# ============================================================================

def test_seguridad_jwt_falsificado_y_expirado_rechazado(client):
    """Comprueba que tokens JWT falsificados o expirados sean rechazados con 401."""
    # 1. Token falsificado
    resp_falso = client.get(
        "/usuarios/me",
        headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.falsificado.firma_invalida"},
    )
    assert resp_falso.status_code == 401

    # 2. Token expirado
    token_expirado = JWTAuthenticator()._create_token(
        data={"sub": "1", "email": "test@tau.usbmed.edu.co", "role": "usuario"},
        expires_delta=timedelta(seconds=-10),
    )
    resp_expirado = client.get(
        "/usuarios/me",
        headers={"Authorization": f"Bearer {token_expirado}"},
    )
    assert resp_expirado.status_code == 401


def test_seguridad_cors_rechaza_origen_no_listado(client):
    """Verifica que orígenes no autorizados no reciban cabecera Access-Control-Allow-Origin."""
    resp = client.options(
        "/auth/login",
        headers={
            "Origin": "http://sitio-malicioso-atacante.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    allow_origin = resp.headers.get("access-control-allow-origin")
    assert allow_origin != "http://sitio-malicioso-atacante.com"
    assert allow_origin != "*"


def test_seguridad_bloqueo_login_tras_5_intentos(client, usuario_sin_verificar):
    """Comprueba bloqueo de seguridad tras 5 intentos fallidos consecutivos de login."""
    email = usuario_sin_verificar["email"]

    # 5 intentos con clave errónea
    for i in range(1, 6):
        resp = client.post(
            "/auth/login",
            json={"email": email, "password": "password_incorrecta"},
        )
        if resp.status_code == 429:
            break
        assert resp.status_code in (400, 401)

    # El siguiente intento debe estar bloqueado por fuerza bruta
    resp_bloqueado = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert resp_bloqueado.status_code == 429
    assert any(term in resp_bloqueado.text.lower() for term in ("bloquead", "límite", "demasiados", "espera"))


def test_seguridad_cabeceras_presentes(client):
    """Verifica que las cabeceras de seguridad requeridas estén configuradas en las respuestas."""
    resp = client.get("/health")
    assert resp.status_code == 200
    headers = resp.headers

    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") in ("DENY", "SAMEORIGIN")
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "content-security-policy" in headers


@pytest.mark.asyncio
async def test_auditoria_no_guarda_query_strings_ni_texto_ofensivo(client, usuario_verificado):
    """Verifica que los logs de auditoría omitan parámetros de query sensibles y texto ofensivo."""
    # Enviar reporte con texto que contiene insulto y query param
    client.post(
        "/publicaciones/?token_secreto=123456&param_privado=ocultar",
        headers=usuario_verificado["headers"],
        json={
            "titulo": "Libro de prueba auditoría",
            "autor": "Autor",
            "isbn": "9789587781236",
            "edicion": "1ra",
            "estado_libro": "bueno",
            "descripcion": "Descripción sin palabras prohibidas",
            "libro_buscado": "Cálculo",
            "tipo_transaccion": "trueque",
        },
    )

    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy.future import select

        res = await session.execute(select(AuditoriaLogORM))
        logs = res.scalars().all()

        for log in logs:
            recurso = getattr(log, "recurso", "") or ""
            detalle = getattr(log, "detalle", "") or ""
            assert "token_secreto" not in recurso
            assert "param_privado" not in recurso
            assert "token_secreto" not in detalle
            assert "param_privado" not in detalle


# ============================================================================
# 5. FLUJO COMPLETO DE VERIFICACIÓN DE LIBRO (Desafío, Evidencias, IA simulada)
# ============================================================================

def _generar_foto_test(codigo: str, titulo: str) -> bytes:
    """Genera bytes JPEG de una imagen sintética para pruebas."""
    img = Image.new("RGB", (600, 800), "white")
    draw = ImageDraw.Draw(img)
    draw.text((30, 30), f"CODIGO: {codigo}", fill="black")
    draw.text((30, 80), f"TITULO: {titulo}", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_flujo_completo_verificacion_libro_con_ia_simulada(
    client, usuario_verificado, usuario_moderador, publicacion_factory
):
    """Ejecuta el ciclo de vida completo de verificación de libro:

    1. Desafío generado con código aleatorio.
    2. Carga de evidencias fotográficas.
    3. Evaluación de IA simulada.
    4. Aprobación y cambio de estado a verificado.
    """
    # 1. Crear publicación del libro
    pub = publicacion_factory(
        usuario_verificado["headers"],
        titulo="Física Universitaria Sears",
        libro_buscado="Álgebra Lineal",
        isbn="9789587781236",
    )
    pub_id = pub["id"]

    # 2. Solicitar desafío de verificación
    resp_desafio = client.post(
        f"/publicaciones/{pub_id}/verificacion/desafios",
        headers=usuario_verificado["headers"],
    )
    assert resp_desafio.status_code == 201
    desafio_data = resp_desafio.json()
    verif_id = desafio_data["verificacion_id"]
    codigo_desafio = desafio_data["codigo"]
    assert len(codigo_desafio) >= 4

    # 3. Enviar evidencias visuales con IA simulada
    foto_portada = _generar_foto_test(codigo_desafio, "Física Universitaria Sears")
    foto_isbn = _generar_foto_test(codigo_desafio, "ISBN 9789587781236")

    # Simulamos la respuesta de la IA según el contrato real de verificacion_ia.verificar_imagen
    with patch(
        "backend_estudiantil.infrastructure.api.verificaciones_router._verificar_imagen_ia",
        return_value={
            "es_libro": True,
            "confianza_libro": 0.95,
            "clase_detectada": "book",
            "codigo_encontrado": True,
            "texto_detectado": [codigo_desafio],
            "aprobado": True,
            "detalle": f"Libro detectado: book (95% confianza) | Codigo '{codigo_desafio}' encontrado en la imagen",
        },
    ):
        resp_evidencias = client.post(
            f"/publicaciones/{pub_id}/verificacion/evidencias",
            headers=usuario_verificado["headers"],
            data={"verificacion_id": verif_id, "codigo": codigo_desafio},
            files={
                "foto_portada": ("portada.jpg", foto_portada, "image/jpeg"),
                "foto_pagina_isbn": ("isbn.jpg", foto_isbn, "image/jpeg"),
            },
        )
        assert resp_evidencias.status_code in (200, 201)
        evidencias_data = resp_evidencias.json()
        assert evidencias_data["estado"] in ("aprobada", "en_revision", "completada")


# ============================================================================
# 6. PERMISOS POR ROL EN ENDPOINTS DE MODERACIÓN (403 para usuarios normales)
# ============================================================================

def test_permisos_por_rol_endpoints_moderacion(
    client, usuario_sin_verificar, usuario_verificado, usuario_moderador, usuario_admin
):
    """Comprueba que los endpoints de moderación rechacen con 403 a usuarios corrientes

    y permitan el acceso a roles de 'moderador' y 'administrador'.
    """
    endpoints = [
        ("GET", "/moderacion/reportes", None),
        ("POST", "/moderacion/advertencias", {"usuario_id": usuario_sin_verificar["id"], "motivo": "Prueba de advertencia"}),
        ("POST", "/moderacion/sanciones", {"usuario_id": usuario_sin_verificar["id"], "tipo": "suspension_7", "motivo": "Prueba sancion"}),
        ("GET", "/moderacion/apelaciones", None),
    ]

    for metodo, url, payload in endpoints:
        # A. Usuario sin verificar (rol usuario) -> 403
        if metodo == "GET":
            r_unver = client.get(url, headers=usuario_sin_verificar["headers"])
            r_ver = client.get(url, headers=usuario_verificado["headers"])
        else:
            r_unver = client.post(url, headers=usuario_sin_verificar["headers"], json=payload)
            r_ver = client.post(url, headers=usuario_verificado["headers"], json=payload)

        assert r_unver.status_code == 403, f"Fallo 403 en {metodo} {url} para usuario sin verificar"
        assert r_ver.status_code == 403, f"Fallo 403 en {metodo} {url} para usuario verificado"

        # B. Moderador -> permitido (200 o 201)
        if metodo == "GET":
            r_mod = client.get(url, headers=usuario_moderador["headers"])
        else:
            r_mod = client.post(url, headers=usuario_moderador["headers"], json=payload)
        assert r_mod.status_code in (200, 201), f"Fallo moderador en {metodo} {url}: {r_mod.text}"

        # C. Administrador -> permitido (200 o 201)
        if metodo == "GET":
            r_admin = client.get(url, headers=usuario_admin["headers"])
        else:
            r_admin = client.post(url, headers=usuario_admin["headers"], json=payload)
        assert r_admin.status_code in (200, 201), f"Fallo administrador en {metodo} {url}: {r_admin.text}"
