"""
confirmation_rate_limiter.py
-----------------------------
Rate limiter para endpoints sensibles de confirmación de correo y códigos:
- /auth/confirmar-codigo
- /auth/confirmar-correo
- /auth/reenviar-codigo

Reglas:
- Almacenamiento en Redis con respaldo transparente en memoria local si Redis no está disponible.
- Límite por IP: 30 solicitudes por minuto (60s).
- Límite por correo: 5 solicitudes cada 15 minutos (900s).
- Límite por reenvío de código: 5 solicitudes cada 15 minutos (900s) por correo.
"""

import json
import logging
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

from backend_estudiantil.config.settings import settings
from backend_estudiantil.infrastructure.redis_circuit_breaker import (
    confirmation_redis_circuit_breaker,
)

logger = logging.getLogger(__name__)


class ConfirmationRateLimiter:
    """Rate limiter distribuido con Redis y fallback transparente en memoria."""

    def __init__(
        self,
        ip_max: int = 30,
        ip_window: int = 60,
        email_max: int = 5,
        email_window: int = 900,  # 15 minutos
    ):
        self.ip_max = ip_max
        self.ip_window = ip_window
        self.email_max = email_max
        self.email_window = email_window
        self.circuit_breaker = confirmation_redis_circuit_breaker

        # Memoria local como respaldo: key -> list[timestamps]
        self._memory_history = defaultdict(list)
        self._redis_client = None

    def _get_redis(self):
        if not getattr(settings, "REDIS_URL", None):
            return None
        if self.circuit_breaker.is_open:
            return None

        if self._redis_client is None:
            try:
                import redis
                client = redis.from_url(
                    settings.REDIS_URL,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                    decode_responses=True,
                )
                client.ping()
                self._redis_client = client
                self.circuit_breaker.record_success()
            except Exception as e:
                self.circuit_breaker.record_failure(e)
                self._redis_client = None
        return self._redis_client

    def _check_memory(self, key: str, max_reqs: int, window_sec: int) -> None:
        now = time.time()
        ventana_inicio = now - window_sec
        self._memory_history[key] = [t for t in self._memory_history[key] if t > ventana_inicio]
        if len(self._memory_history[key]) >= max_reqs:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Has superado el límite de intentos para esta operación. Por favor espera un momento antes de reintentar.",
            )
        self._memory_history[key].append(now)

    def _check_key(self, key: str, max_reqs: int, window_sec: int) -> None:
        """Verifica el límite de una clave usando Redis o memoria si Redis falla."""
        r = None
        try:
            r = self._get_redis()
        except Exception:
            r = None

        if r is not None:
            try:
                # Pipeline atómico en Redis
                pipe = r.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_sec)
                res = pipe.execute()
                current_count = res[0]
                if current_count > max_reqs:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Has superado el límite de intentos para esta operación. Por favor espera un momento antes de reintentar.",
                    )
                self.circuit_breaker.record_success()
                return
            except HTTPException:
                raise
            except Exception as e:
                self.circuit_breaker.record_failure(e)
                self._redis_client = None
                logger.warning("Falla al conectar a Redis (%s). Usando memoria local como respaldo.", e)

        # Respaldo en memoria local
        self._check_memory(key, max_reqs, window_sec)

    def _get_client_ip(self, request: Request) -> str:
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "127.0.0.1"

    async def check(self, request: Request) -> None:
        # 1. Límite por IP: 30 por minuto
        ip = self._get_client_ip(request)
        ip_key = f"rl:confirm:ip:{ip}"
        self._check_key(ip_key, self.ip_max, self.ip_window)

        # 2. Extraer correo si está presente en query o body
        email: str | None = request.query_params.get("email")
        if not email and request.method in ("POST", "PUT"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    data = json.loads(body_bytes)
                    if isinstance(data, dict):
                        email = data.get("email")
            except Exception:
                pass

        if email:
            norm_email = str(email).strip().lower()
            # Límite general por correo en confirmaciones (5 por cada 15 minutos)
            email_key = f"rl:confirm:email:{norm_email}"
            self._check_key(email_key, self.email_max, self.email_window)

            # Si es reenvío de código, limitar específicamente reenvíos
            if "reenviar-codigo" in request.url.path:
                resend_key = f"rl:confirm:resend:{norm_email}"
                self._check_key(resend_key, self.email_max, self.email_window)

    def reset(self) -> None:
        """Limpia el almacenamiento en memoria y en Redis si está activo (para tests)."""
        self._memory_history.clear()
        if self._redis_client:
            try:
                self._redis_client.flushdb()
            except Exception:
                pass


confirmation_rate_limiter = ConfirmationRateLimiter(
    ip_max=30,
    ip_window=60,
    email_max=5,
    email_window=900,
)


async def check_rate_limit_confirmacion(request: Request) -> None:
    """Dependencia FastAPI para aplicar rate limit a endpoints de confirmación."""
    await confirmation_rate_limiter.check(request)
