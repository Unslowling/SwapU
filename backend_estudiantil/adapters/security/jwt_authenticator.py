import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from backend_estudiantil.config.settings import settings
from backend_estudiantil.ports.security.authenticator import Authenticator


class JWTAuthenticator(Authenticator):
    """Implementación de Authenticator con PyJWT, identificador único JTI y expiración configurable."""

    def _create_token(self, data: dict[str, Any], expires_delta: timedelta) -> str:
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        expire = now + expires_delta
        # Inyectar jti único por RFC 7519 para evitar tokens idénticos emitidos en el mismo segundo
        to_encode.update({
            "jti": str(uuid.uuid4()),
            "exp": expire,
            "iat": now,
        })
        token = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return token

    def create_access_token(self, data: dict[str, Any]) -> str:
        if "role" not in data:
            data["role"] = "user"
        expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return self._create_token(data, expires)

    def create_refresh_token(self, data: dict[str, Any]) -> str:
        if "role" not in data:
            data["role"] = "user"
        expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        return self._create_token(data, expires)

    def decode_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise ValueError("Token expirado")
        except jwt.InvalidTokenError as exc:
            raise ValueError(f"Token inválido: {exc}")
