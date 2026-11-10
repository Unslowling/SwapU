"""
audit_middleware.py
-------------------
Capa de Captura del Sistema Auditor (Regla de las 5W).

Intercepta todas las solicitudes HTTP que ingresan al backend FastAPI,
extrae los metadatos de seguridad y contexto (Who, What, When, Where, Why),
mide tiempos de respuesta, emite logs estructurados y persiste de manera
asíncrona y segura los registros en la base de datos (PostgreSQL/SQLite).
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend_estudiantil.adapters.db import AuditoriaLogORM, get_session_factory
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator

logger = logging.getLogger("backend_estudiantil.audit")


def _clasificar_accion_y_recurso(metodo: str, ruta: str) -> tuple[str, str]:
    """Mapea una ruta HTTP y método a una acción de negocio (What) y recurso."""
    metodo = metodo.upper()
    ruta_limpia = ruta.rstrip("/")

    # Autenticación y Cuentas
    if "/auth/login" in ruta:
        return "INICIO_SESION", "auth"
    if "/auth/register" in ruta:
        return "REGISTRO_USUARIO", "auth"
    if "/auth/refresh" in ruta:
        return "RENOVACION_TOKEN", "auth"
    if "/auth/logout" in ruta:
        return "CIERRE_SESION", "auth"
    if "/auth/google" in ruta:
        return "OAUTH_GOOGLE", "auth"
    if "/auth/facebook" in ruta:
        return "OAUTH_FACEBOOK", "auth"

    # Verificación de libros e IA
    if "/verificacion/desafios" in ruta:
        return "GENERAR_DESAFIO_IA", "verificaciones"
    if "/verificacion/evidencias" in ruta:
        return "SUBIR_EVIDENCIA_LIBRO", "verificaciones"
    if "/verificaciones/pendientes" in ruta:
        return "CONSULTAR_EVIDENCIAS_PENDIENTES", "verificaciones"
    if "/verificaciones" in ruta and "/revision" in ruta:
        return "MODERACION_LIBRO_IA", "verificaciones"
    if "/verificaciones" in ruta and "/evidencia" in ruta:
        return "DESCARGA_FOTO_EVIDENCIA", "verificaciones"

    # Trueques y Negociación P2P
    if "/trueques" in ruta and "/confirmar" in ruta:
        return "CONFIRMAR_TRUEQUE", "trueques"
    if "/trueques" in ruta and "/completar" in ruta:
        return "COMPLETAR_TRUEQUE", "trueques"
    if "/trueques" in ruta and "/rechazar" in ruta:
        return "RECHAZAR_TRUEQUE", "trueques"
    if "/trueques" in ruta and "/mensajes" in ruta:
        return ("ENVIAR_MENSAJE_CHAT" if metodo == "POST" else "CONSULTAR_MENSAJES_CHAT"), "chat"
    if "/trueques/proponer" in ruta or (ruta_limpia == "/trueques" and metodo == "POST"):
        return "PROPONER_TRUEQUE", "trueques"
    if "/trueques" in ruta:
        return f"{metodo}_TRUEQUE", "trueques"

    # Publicaciones
    if "/publicaciones" in ruta:
        if metodo == "POST":
            return "CREAR_PUBLICACION", "publicaciones"
        if metodo == "PUT":
            return "ACTUALIZAR_PUBLICACION", "publicaciones"
        if metodo == "DELETE":
            return "ELIMINAR_PUBLICACION", "publicaciones"
        return "CONSULTAR_PUBLICACIONES", "publicaciones"

    # Administración y Moderación
    if "/moderacion/sanciones" in ruta:
        if metodo == "POST" and "/revocar" in ruta:
            return "REVOCAR_SANCION", "moderacion"
        if metodo == "POST":
            return "APLICAR_SANCION", "moderacion"
        return "CONSULTAR_SANCIONES", "moderacion"
    if "/reportes" in ruta:
        return "REGISTRAR_REPORTE" if metodo == "POST" else "CONSULTAR_REPORTES", "moderacion"
    if "/admin/trueques/expirar" in ruta:
        return "EXPIRAR_TRUEQUES_INACTIVOS", "administracion"
    if "/admin/users" in ruta and "/promote" in ruta:
        return "PROMOVER_USUARIO_MODERADOR", "administracion"
    if "/admin/auditoria" in ruta:
        return "CONSULTAR_LOGS_AUDITORIA", "auditoria"


    # Confirmación de correo
    if "/auth/confirmar" in ruta:
        return "CONFIRMAR_CORREO_INSTITUCIONAL", "auth"
    if "/auth/reenviar-codigo" in ruta:
        return "REENVIAR_CODIGO_CONFIRMACION", "auth"

    # Calificaciones
    if "/calificaciones" in ruta:
        return "REGISTRAR_CALIFICACION" if metodo == "POST" else "CONSULTAR_CALIFICACIONES", "calificaciones"

    # Usuarios
    if "/usuarios/me" in ruta:
        return "GESTION_PERFIL_PROPIO", "usuarios"
    if "/usuarios" in ruta:
        return f"{metodo}_USUARIOS", "usuarios"

    # General
    accion_def = f"{metodo}_{ruta_limpia.strip('/').replace('/', '_').upper() or 'ROOT'}"
    return accion_def[:100], "general"


def _extraer_identidad_token(request: Request) -> tuple[int | None, str | None, str | None]:
    """Extrae usuario_id, email y rol a partir del Bearer token o cookies (Who)."""
    token = None
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        return None, None, None

    try:
        authenticator = JWTAuthenticator()
        payload = authenticator.decode_token(token)
        sub = payload.get("sub")
        user_id = int(sub) if sub and str(sub).isdigit() else None
        email = payload.get("email")
        role = payload.get("role")
        return user_id, email, role
    except Exception:
        return None, None, None


async def _guardar_log_auditoria(datos_log: dict):
    """Persistencia asíncrona segura del log en la base de datos."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            registro = AuditoriaLogORM(**datos_log)
            session.add(registro)
            await session.commit()
    except Exception as exc:
        logger.error("Error al persistir log de auditoría 5W: %s", exc)


class AuditMiddleware(BaseHTTPMiddleware):
    """Middleware Interceptor de Auditoría bajo la Regla de las 5W."""

    # Rutas que no requieren auditoría pesada para evitar sobrecargar BD
    RUTAS_IGNORADAS = {"/health", "/health/db", "/metrics", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next) -> Response:
        ruta = request.url.path
        metodo = request.method

        # Omitir recursos estáticos o healthchecks simples
        if ruta in self.RUTAS_IGNORADAS or ruta.startswith(("/css/", "/js/", "/oauth/")):
            return await call_next(request)

        # ── 1. Who (Quién) ──
        # Obtener IP real considerando proxys inversos (Docker/Nginx)
        x_forwarded_for = request.headers.get("x-forwarded-for")
        ip_origen = (
            x_forwarded_for.split(",")[0].strip()
            if x_forwarded_for
            else (request.client.host if request.client else "127.0.0.1")
        )
        user_agent = request.headers.get("user-agent", "")[:250]
        user_id, user_email, user_role = _extraer_identidad_token(request)

        # ── 2. What (Qué) & Where (Dónde) ──
        accion, recurso = _clasificar_accion_y_recurso(metodo, ruta)
        endpoint = ruta[:255]

        # ── 3. When (Cuándo) ──
        inicio_perf = time.perf_counter()
        fecha_hora = datetime.now(timezone.utc)

        detalle = "Petición procesada"
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
            exito = 200 <= status_code < 400

            if exito:
                detalle = f"Operación completada con éxito ({status_code})"
            elif status_code == 401:
                detalle = "No autorizado: credenciales o token inválido/ausente"
            elif status_code == 403:
                detalle = "Acceso denegado: permisos insuficientes para el recurso"
            elif status_code == 404:
                detalle = "Recurso no encontrado"
            elif status_code == 422:
                detalle = "Error de validación en los parámetros de la solicitud"
            elif status_code == 429:
                detalle = "Tasa de peticiones excedida (Rate Limit)"
            else:
                detalle = f"Respuesta con código HTTP {status_code}"

        except Exception as exc:
            status_code = 500
            exito = False
            detalle = f"Excepción interna en servidor: {str(exc)[:200]}"
            raise
        finally:
            duracion_ms = round((time.perf_counter() - inicio_perf) * 1000, 2)

            # Generador de Logs estructurados (Salida estándar / consola)
            nivel = logging.INFO if exito else logging.WARNING
            logger.log(
                nivel,
                "AUDIT [5W] | Who: [ID=%s, Email=%s, Rol=%s, IP=%s] | What: %s (%s) | When: %s | Where: %s %s | Why: HTTP %s (%s ms) - %s",
                user_id or "ANONIMO",
                user_email or "-",
                user_role or "-",
                ip_origen,
                accion,
                recurso,
                fecha_hora.isoformat(),
                metodo,
                endpoint,
                status_code,
                duracion_ms,
                detalle,
            )

            # Capa de Almacenamiento: Guardar de forma asíncrona sin bloquear la respuesta
            datos_auditoria = {
                "usuario_id": user_id,
                "usuario_email": user_email,
                "usuario_rol": user_role,
                "ip_origen": ip_origen,
                "user_agent": user_agent,
                "accion": accion,
                "recurso": recurso,
                "fecha_hora": fecha_hora,
                "metodo_http": metodo,
                "endpoint": endpoint,
                "estado_http": status_code,
                "exito": exito,
                "detalle": detalle,
                "duracion_ms": duracion_ms,
            }
            asyncio.create_task(_guardar_log_auditoria(datos_auditoria))

        return response
