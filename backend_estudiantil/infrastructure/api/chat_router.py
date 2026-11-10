import asyncio
import json
import logging
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from pydantic import BaseModel, Field, field_validator
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.future import select

from backend_estudiantil.adapters.db import (
    MatchORM,
    MensajeORM,
    PublicacionORM,
    TruequeORM,
    UserORM,
    get_session_factory,
)
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.services.moderacion_contenido_service import (
    ModeracionContenidoService,
)
from backend_estudiantil.infrastructure.moderacion_audit_helper import (
    registrar_auditoria_infraccion,
)
from backend_estudiantil.infrastructure.redis_circuit_breaker import (
    chat_redis_circuit_breaker,
)
from backend_estudiantil.infrastructure.security import get_current_user

router = APIRouter(prefix="/trueques", tags=["chat"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        # trueque_id -> {WebSocket: {"user_id": int, "user_name": str}}
        self.active_connections: dict[int, dict[WebSocket, dict]] = {}
        self._subscriptions: dict[int, tuple[object, asyncio.Task]] = {}
        self._lock = asyncio.Lock()
        self._redis: Redis | None = None
        self._publisher: Redis | None = None

    async def connect(self, websocket: WebSocket, trueque_id: int, user_id: int, user_name: str):
        await websocket.accept(subprotocol="bearer")
        async with self._lock:
            if trueque_id not in self.active_connections:
                self.active_connections[trueque_id] = {}
            self.active_connections[trueque_id][websocket] = {
                "user_id": user_id,
                "user_name": user_name,
            }
            online_users = list({info["user_id"] for info in self.active_connections[trueque_id].values()})

            if settings.REDIS_URL and trueque_id not in self._subscriptions:
                if not chat_redis_circuit_breaker.is_open:
                    try:
                        if self._redis is None:
                            self._redis = Redis.from_url(
                                settings.REDIS_URL,
                                decode_responses=True,
                                socket_connect_timeout=0.5,
                                socket_timeout=0.5,
                            )
                        pubsub = self._redis.pubsub()
                        await asyncio.wait_for(
                            pubsub.subscribe(self._channel(trueque_id)),
                            timeout=0.8,
                        )
                        task = asyncio.create_task(self._listen(trueque_id, pubsub))
                        self._subscriptions[trueque_id] = (pubsub, task)
                        chat_redis_circuit_breaker.record_success()
                    except Exception as e:
                        chat_redis_circuit_breaker.record_failure(e)
                        self._redis = None
                        logger.warning("No se pudo conectar a Redis para chat pubsub (%s). Operando en modo memoria local.", e)
                else:
                    logger.debug("Redis circuit breaker ABIERTO para chat pubsub trueque %s. Usando memoria local.", trueque_id)

        # Enviar estado actual de la sala al recién conectado
        try:
            await websocket.send_json({
                "type": "room_state",
                "online_users": online_users,
                "current_user_id": user_id,
            })
        except Exception:
            pass

        # Notificar a los demás que el usuario está en línea
        await self.broadcast(
            {
                "type": "presence",
                "user_id": user_id,
                "user_name": user_name,
                "status": "online",
                "online_users": online_users,
            },
            trueque_id,
            exclude_socket=websocket,
        )

    @staticmethod
    def _channel(trueque_id: int) -> str:
        return f"trueque:{trueque_id}:mensajes"

    async def disconnect(self, websocket: WebSocket, trueque_id: int):
        user_info = None
        async with self._lock:
            connections = self.active_connections.get(trueque_id, {})
            if websocket in connections:
                user_info = connections.pop(websocket)
            if not connections:
                self.active_connections.pop(trueque_id, None)
                subscription = self._subscriptions.pop(trueque_id, None)
            else:
                subscription = None

        if subscription:
            pubsub, task = subscription
            if task is not asyncio.current_task():
                task.cancel()
            await pubsub.unsubscribe(self._channel(trueque_id))
            await pubsub.aclose()

        if user_info and trueque_id in self.active_connections:
            uid = user_info["user_id"]
            user_still_connected = any(
                info["user_id"] == uid for info in self.active_connections[trueque_id].values()
            )
            if not user_still_connected:
                online_users = list({info["user_id"] for info in self.active_connections[trueque_id].values()})
                await self.broadcast(
                    {
                        "type": "presence",
                        "user_id": uid,
                        "user_name": user_info["user_name"],
                        "status": "offline",
                        "online_users": online_users,
                    },
                    trueque_id,
                )

    async def _listen(self, trueque_id: int, pubsub):
        try:
            async for event in pubsub.listen():
                if event["type"] == "message":
                    connections = self.active_connections.get(trueque_id, {})
                    for connection in tuple(connections.keys()):
                        try:
                            await connection.send_text(event["data"])
                        except (WebSocketDisconnect, RuntimeError, OSError):
                            await self.disconnect(connection, trueque_id)
        except asyncio.CancelledError:
            raise
        except (RedisError, WebSocketDisconnect, RuntimeError, OSError):
            logger.exception("Error distribuyendo mensajes WebSocket del trueque %s", trueque_id)
            connections = self.active_connections.get(trueque_id, {})
            for connection in tuple(connections.keys()):
                await connection.close(code=1011)
        finally:
            async with self._lock:
                self._subscriptions.pop(trueque_id, None)

    async def broadcast(self, message: dict, trueque_id: int, exclude_socket: WebSocket | None = None):
        if settings.REDIS_URL and not chat_redis_circuit_breaker.is_open:
            try:
                if self._publisher is None:
                    self._publisher = Redis.from_url(
                        settings.REDIS_URL,
                        decode_responses=True,
                        socket_connect_timeout=0.5,
                        socket_timeout=0.5,
                    )
                await asyncio.wait_for(
                    self._publisher.publish(
                        self._channel(trueque_id), json.dumps(message, ensure_ascii=False)
                    ),
                    timeout=0.8,
                )
                chat_redis_circuit_breaker.record_success()
                return
            except Exception as e:
                chat_redis_circuit_breaker.record_failure(e)
                self._publisher = None
                logger.warning("Redis no disponible en chat broadcast (%s). Usando fallback local.", e)

        connections = self.active_connections.get(trueque_id, {})
        for connection in tuple(connections.keys()):
            if exclude_socket and connection == exclude_socket:
                continue
            try:
                await connection.send_json(message)
            except Exception:
                await self.disconnect(connection, trueque_id)


manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MensajeCreate(BaseModel):
    contenido: str = Field(..., min_length=1, max_length=2000)

    @field_validator("contenido")
    @classmethod
    def validar_contenido(cls, value: str) -> str:
        contenido = value.strip()
        if not contenido:
            raise ValueError("El mensaje no puede estar vacío")
        return contenido


class MensajeRead(BaseModel):
    id: int
    trueque_id: int
    remitente_id: int
    remitente_nombre: str | None = None
    contenido: str
    fecha_envio: datetime
    realtime_delivery: str | None = None


class TruequeInfoRead(BaseModel):
    """Informacion enriquecida del trueque para el panel de chat."""
    id: int
    estado: str
    usuario_propone_id: int
    usuario_propone_nombre: str | None = None
    usuario_recibe_id: int
    usuario_recibe_nombre: str | None = None
    libro_propone: str | None = None
    libro_recibe: str | None = None
    fecha_propuesta: datetime
    fecha_confirmacion: datetime | None = None
    fecha_completado: datetime | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_user_name(session, user_id: int) -> str:
    q = await session.execute(select(UserORM).where(UserORM.id == user_id))
    user = q.scalar_one_or_none()
    if user:
        return f"{user.nombre or ''} {user.apellido or ''}".strip() or f"Usuario #{user_id}"
    return f"Usuario #{user_id}"


async def _get_trueque_or_404(session, trueque_id: int):
    q = await session.execute(select(TruequeORM).where(TruequeORM.id == trueque_id))
    trueque = q.scalar_one_or_none()
    if not trueque:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trueque no encontrado")
    return trueque


def _assert_participant(trueque, user_id: int):
    if user_id not in (trueque.usuario_propone_id, trueque.usuario_recibe_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No eres participante de este trueque")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/{trueque_id}/info",
    response_model=TruequeInfoRead,
    summary="Informacion enriquecida del trueque para el chat",
)
async def obtener_info_trueque(
    trueque_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Retorna informacion completa del trueque incluyendo nombres de participantes y libros."""
    factory = get_session_factory()
    user_id = int(current_user["id"])

    async with factory() as session:
        trueque = await _get_trueque_or_404(session, trueque_id)
        _assert_participant(trueque, user_id)

        nombre_propone = await _get_user_name(session, trueque.usuario_propone_id)
        nombre_recibe = await _get_user_name(session, trueque.usuario_recibe_id)

        # Intentar obtener titulos desde el match asociado
        libro_propone = None
        libro_recibe = None
        if trueque.match_id:
            q_match = await session.execute(select(MatchORM).where(MatchORM.id == trueque.match_id))
            match = q_match.scalar_one_or_none()
            if match:
                q_origen = await session.execute(
                    select(PublicacionORM).where(PublicacionORM.id == match.publicacion_origen_id)
                )
                pub_origen = q_origen.scalar_one_or_none()
                q_destino = await session.execute(
                    select(PublicacionORM).where(PublicacionORM.id == match.publicacion_destino_id)
                )
                pub_destino = q_destino.scalar_one_or_none()
                if pub_origen:
                    libro_propone = pub_origen.titulo
                if pub_destino:
                    libro_recibe = pub_destino.titulo

        return TruequeInfoRead(
            id=trueque.id,
            estado=trueque.estado,
            usuario_propone_id=trueque.usuario_propone_id,
            usuario_propone_nombre=nombre_propone,
            usuario_recibe_id=trueque.usuario_recibe_id,
            usuario_recibe_nombre=nombre_recibe,
            libro_propone=libro_propone,
            libro_recibe=libro_recibe,
            fecha_propuesta=trueque.fecha_propuesta,
            fecha_confirmacion=trueque.fecha_confirmacion,
            fecha_completado=trueque.fecha_completado,
        )


@router.get(
    "/{trueque_id}/mensajes",
    response_model=list[MensajeRead],
    summary="Listar mensajes de chat del trueque",
)
async def listar_mensajes(
    trueque_id: int,
    limit: int = Query(50, ge=1, le=100),
    before_id: int | None = Query(None, gt=0),
    current_user: dict = Depends(get_current_user),
):
    """Retorna una página de mensajes, empezando por los más recientes."""
    factory = get_session_factory()
    user_id = int(current_user["id"])

    async with factory() as session:
        trueque = await _get_trueque_or_404(session, trueque_id)
        _assert_participant(trueque, user_id)

        stmt = (
            select(MensajeORM, UserORM.nombre, UserORM.apellido)
            .outerjoin(UserORM, MensajeORM.remitente_id == UserORM.id)
            .where(
                MensajeORM.trueque_id == trueque_id,
                *([MensajeORM.id < before_id] if before_id is not None else []),
            )
            .order_by(MensajeORM.id.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = reversed(result.all())

        mensajes = []
        for msg, nombre, apellido in rows:
            nombre_completo = (
                f"{nombre or ''} {apellido or ''}".strip() or f"Usuario #{msg.remitente_id}"
            )
            mensajes.append(
                MensajeRead(
                    id=msg.id,
                    trueque_id=msg.trueque_id,
                    remitente_id=msg.remitente_id,
                    remitente_nombre=nombre_completo,
                    contenido=msg.contenido,
                    fecha_envio=msg.fecha_envio,
                )
            )
        return mensajes


_moderacion_service = ModeracionContenidoService()


async def procesar_y_guardar_mensaje_chat(
    session,
    trueque_id: int,
    user_id: int,
    user_name: str,
    contenido_crudo: str,
    es_websocket: bool = False,
    ip_origen: str = "127.0.0.1",
    user_email: str | None = None,
    user_role: str | None = None,
    difundir: bool = True,
) -> tuple[MensajeRead | None, str | None]:
    """Procesa, modera y persiste un mensaje de chat en UN solo punto central
    reutilizado tanto por el endpoint HTTP REST como por el WebSocket.
    """
    contenido = contenido_crudo.strip()
    if not contenido:
        return None, "El mensaje no puede estar vacio"

    trueque = await _get_trueque_or_404(session, trueque_id)
    _assert_participant(trueque, user_id)

    if trueque.estado in ("rechazado", "completado"):
        return None, "No puedes enviar mensajes a un trueque rechazado o completado"

    # Moderación de contenido y vocabulario
    resultado = _moderacion_service.procesar_texto(contenido)

    # Registro de auditoría (Regla de las 5W) para cualquier infracción detectada
    if resultado.accion_auditoria:
        await registrar_auditoria_infraccion(
            usuario_id=user_id,
            recurso=f"trueque:{trueque_id}:mensaje",
            accion=resultado.accion_auditoria,
            severidad=resultado.nivel_severidad or "leve",
            categoria="vocabulario",
            ip_origen=ip_origen,
            metodo_http="WS" if es_websocket else "POST",
            endpoint=f"/trueques/{trueque_id}/ws" if es_websocket else f"/trueques/{trueque_id}/mensajes",
            estado_http=400 if not resultado.es_valido else 200,
            usuario_email=user_email,
            usuario_rol=user_role,
            terminos_count=len(resultado.terminos_detectados),
        )

    if not resultado.es_valido:
        return None, resultado.mensaje_error

    nuevo_mensaje = MensajeORM(
        trueque_id=trueque_id,
        remitente_id=user_id,
        contenido=resultado.texto_final,
    )
    session.add(nuevo_mensaje)
    await session.commit()
    await session.refresh(nuevo_mensaje)

    response_msg = MensajeRead(
        id=nuevo_mensaje.id,
        trueque_id=nuevo_mensaje.trueque_id,
        remitente_id=nuevo_mensaje.remitente_id,
        remitente_nombre=user_name,
        contenido=nuevo_mensaje.contenido,
        fecha_envio=nuevo_mensaje.fecha_envio,
    )

    # Difundir en tiempo real via WebSocket / Redis si fue solicitado
    if difundir:
        msg_dict = response_msg.model_dump()
        msg_dict["fecha_envio"] = msg_dict["fecha_envio"].isoformat()
        msg_dict["type"] = "message"
        try:
            await manager.broadcast(msg_dict, trueque_id)
        except RedisError:
            logger.exception(
                "El mensaje %s se guardó, pero no se pudo distribuir por Redis",
                response_msg.id,
            )
            response_msg.realtime_delivery = "unavailable"

    return response_msg, None


@router.post(
    "/{trueque_id}/mensajes",
    response_model=MensajeRead,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar mensaje al chat del trueque",
)
async def enviar_mensaje(
    trueque_id: int,
    payload: MensajeCreate,
    current_user: dict = Depends(get_current_user),
):
    """Envia un nuevo mensaje al chat con moderación automática de vocabulario."""
    factory = get_session_factory()
    user_id = int(current_user["id"])

    # 1. Operaciones de BD dentro de sesión corta para liberar la conexión de inmediato
    async with factory() as session:
        result = await session.execute(select(UserORM).where(UserORM.id == user_id))
        user_obj = result.scalar_one_or_none()
        from backend_estudiantil.domain.services.moderacion_sanciones_service import (
            usuario_puede_operar,
        )
        res_op = usuario_puede_operar(user_obj)
        if not res_op.puede_operar:
            fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
            )

        nombre_completo = await _get_user_name(session, user_id)
        msg, error = await procesar_y_guardar_mensaje_chat(
            session=session,
            trueque_id=trueque_id,
            user_id=user_id,
            user_name=nombre_completo,
            contenido_crudo=payload.contenido,
            es_websocket=False,
            user_email=current_user.get("email"),
            user_role=current_user.get("role"),
            difundir=False,  # Se difunde fuera del bloque de sesión para liberar conexiones en Postgres
        )
        if error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # 2. Difusión en tiempo real fuera del bloque de sesión de base de datos
    if msg:
        msg_dict = msg.model_dump()
        msg_dict["fecha_envio"] = msg_dict["fecha_envio"].isoformat()
        msg_dict["type"] = "message"
        try:
            await manager.broadcast(msg_dict, trueque_id)
        except RedisError:
            logger.exception(
                "El mensaje %s se guardó, pero no se pudo distribuir por Redis",
                msg.id,
            )
            msg.realtime_delivery = "unavailable"

    return msg


@router.websocket("/{trueque_id}/ws")
async def websocket_endpoint(websocket: WebSocket, trueque_id: int):
    """Canal WebSocket bidireccional en tiempo real (P2P entre participantes).
    Permite enviar mensajes con moderación y auditoría de infracciones.
    """
    protocolos = websocket.scope.get("subprotocols", [])
    if len(protocolos) < 2 or protocolos[0] != "bearer":
        await websocket.close(code=4401)
        return

    try:
        payload = JWTAuthenticator().decode_token(protocolos[1])
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        await websocket.close(code=4401)
        return

    factory = get_session_factory()
    user_name = f"Usuario #{user_id}"
    user_obj = None
    async with factory() as session:
        result = await session.execute(
            select(TruequeORM).where(TruequeORM.id == trueque_id)
        )
        trueque = result.scalar_one_or_none()
        if trueque is None:
            await websocket.close(code=4404)
            return
        result = await session.execute(select(UserORM).where(UserORM.id == user_id))
        user_obj = result.scalar_one_or_none()
        from backend_estudiantil.domain.services.moderacion_sanciones_service import (
            usuario_puede_operar,
        )
        res_op = usuario_puede_operar(user_obj)
        if not res_op.puede_operar:
            await websocket.accept(subprotocol="bearer")
            fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
            await websocket.send_json({
                "type": "error",
                "detail": f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
            })
            await websocket.close(code=4403)
            return
        if user_id not in (trueque.usuario_propone_id, trueque.usuario_recibe_id):
            await websocket.close(code=4403)
            return
        user_name = f"{user_obj.nombre or ''} {user_obj.apellido or ''}".strip() or f"Usuario #{user_id}"

    try:
        await manager.connect(websocket, trueque_id, user_id, user_name)
    except RedisError:
        logger.exception("No se pudo crear la suscripción Redis para el trueque %s", trueque_id)
        await websocket.close(code=1011)
        return

    try:
        while True:
            text = await websocket.receive_text()
            if not text:
                continue

            try:
                data = json.loads(text)
            except Exception:
                data = {"type": "message", "contenido": text}

            msg_type = data.get("type", "message")

            if msg_type == "typing":
                is_typing = bool(data.get("is_typing", False))
                await manager.broadcast(
                    {
                        "type": "typing",
                        "trueque_id": trueque_id,
                        "user_id": user_id,
                        "user_name": user_name,
                        "is_typing": is_typing,
                    },
                    trueque_id,
                    exclude_socket=websocket,
                )

            elif msg_type == "message":
                contenido = str(data.get("contenido", "")).strip()
                if not contenido:
                    continue

                client_host = websocket.client.host if websocket.client else "127.0.0.1"
                async with factory() as session:
                    res_live = await session.execute(select(UserORM).where(UserORM.id == user_id))
                    u_live = res_live.scalar_one_or_none()
                    from backend_estudiantil.domain.services.moderacion_sanciones_service import (
                        usuario_puede_operar,
                    )
                    res_op = usuario_puede_operar(u_live)
                    if not res_op.puede_operar:
                        fin_str = f" Fecha de fin: {res_op.fecha_fin.isoformat()}." if res_op.fecha_fin else ""
                        await websocket.send_json({
                            "type": "error",
                            "detail": f"Tu cuenta se encuentra {res_op.estado_cuenta}. Motivo: {res_op.motivo}.{fin_str}",
                        })
                        continue

                    msg, error = await procesar_y_guardar_mensaje_chat(
                        session=session,
                        trueque_id=trueque_id,
                        user_id=user_id,
                        user_name=user_name,
                        contenido_crudo=contenido,
                        es_websocket=True,
                        ip_origen=client_host,
                        user_email=getattr(user_obj, "correo_institucional", None),
                        user_role=getattr(user_obj, "rol", "usuario"),
                    )
                    if error:
                        await websocket.send_json({"type": "error", "detail": error})
                        continue

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        await manager.disconnect(websocket, trueque_id)
    except Exception as e:
        logger.exception("Error en WebSocket trueque %s: %s", trueque_id, e)
        await manager.disconnect(websocket, trueque_id)
