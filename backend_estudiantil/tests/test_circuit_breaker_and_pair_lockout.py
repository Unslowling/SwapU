"""
backend_estudiantil/tests/test_circuit_breaker_and_pair_lockout.py
------------------------------------------------------------------
Pruebas para el Circuit Breaker de Redis, mitigación DoS por pareja (IP + Correo)
y flujo de renovación transparente de tokens JWT (/auth/refresh).
"""

import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from backend_estudiantil.infrastructure.redis_circuit_breaker import RedisCircuitBreaker
from backend_estudiantil.infrastructure.login_rate_limiter import LoginRateLimiter
from backend_estudiantil.infrastructure.main import app
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator


@pytest.mark.unit
def test_redis_circuit_breaker_lifecycle():
    """Valida los estados de CERRADO, ABIERTO y RECUPERACIÓN del Circuit Breaker."""
    cb = RedisCircuitBreaker(cooldown_seconds=30.0, timeout_seconds=0.5)
    assert cb.timeout_seconds < 1.0, "El timeout debe ser menor a 1 segundo"
    assert not cb.is_open, "El circuito debe iniciar CERRADO"

    # Registrar fallo
    cb.record_failure(Exception("Redis unreachable"))
    assert cb.is_open, "El circuito debe abrirse inmediatamente tras un fallo"

    # Éxito restablece
    cb.record_success()
    assert not cb.is_open, "El registro de éxito debe cerrar el circuito"

    # Reset manual
    cb.record_failure()
    assert cb.is_open
    cb.reset()
    assert not cb.is_open


@pytest.mark.unit
def test_login_rate_limiter_pair_lockout_prevents_dos():
    """Verifica que el bloqueo por fuerza bruta sea por pareja (IP + Correo).
    Un atacante desde otra IP no puede bloquear la cuenta de la víctima para su IP legítima.
    """
    limiter = LoginRateLimiter(
        ip_max_per_min=50,
        email_max_per_min=50,
        max_consecutive_failures=5,
        lockout_duration_sec=900,
        window_sec=60,
    )

    attacker_ip = "198.51.100.99"
    victim_ip = "190.85.12.44"
    victim_email = "estudiante@tau.usbmed.edu.co"

    # 1. El atacante falla 5 veces consecutivas
    for _ in range(5):
        limiter.record_failed_attempt(ip=attacker_ip, email=victim_email)

    # 2. El atacante desde su IP queda bloqueado con 429
    with pytest.raises(HTTPException) as exc_info:
        limiter.check_rate_limit(ip=attacker_ip, email=victim_email)
    assert exc_info.value.status_code == 429
    assert "bloqueado temporalmente" in exc_info.value.detail

    # 3. La víctima desde su IP legítima NO está bloqueada y puede acceder
    # (No debe lanzar HTTPException)
    limiter.check_rate_limit(ip=victim_ip, email=victim_email)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_refresh_token_valid_and_expired():
    """Valida la renovación del token de acceso a través de la cookie HttpOnly."""
    auth = JWTAuthenticator()
    transport = ASGITransport(app=app)

    # 1. Crear refresh token válido
    user_payload = {"sub": "999", "role": "usuario"}
    valid_refresh = auth.create_refresh_token(user_payload)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Enviar petición con la cookie refresh_token
        res = await ac.post("/auth/refresh", cookies={"refresh_token": valid_refresh})
        assert res.status_code == 200, f"Error en refresh: {res.text}"
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "usuario"
        assert data["expires_in"] > 0

        # Validar nuevo access token generado
        claims = auth.decode_token(data["access_token"])
        assert claims["sub"] == "999"

        # 2. Token inválido/corrupto debe rechazar con 401
        res_invalid = await ac.post("/auth/refresh", cookies={"refresh_token": "token_invalido_xyz"})
        assert res_invalid.status_code == 401
