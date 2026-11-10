"""
backend_estudiantil/infrastructure/security_headers_middleware.py
-----------------------------------------------------------------
Middleware para inyectar cabeceras HTTP de seguridad en todas las respuestas:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Referrer-Policy: strict-origin-when-cross-origin
- Content-Security-Policy: básica y compatible con el frontend actual
- Strict-Transport-Security (HSTS): cuando COOKIE_SECURE está activo o ENV=prod
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from backend_estudiantil.config.settings import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # 1. Prevenir inferencia MIME incorrecta
        response.headers["X-Content-Type-Options"] = "nosniff"

        # 2. Prevenir clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # 3. Política de referencia segura
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 4. Content Security Policy (básica y permisiva para recursos locales, estilos, scripts y websockets)
        csp = (
            "default-src 'self' 'unsafe-inline' https: data:; "
            "img-src 'self' data: https: blob:; "
            "connect-src 'self' ws: wss: http: https:; "
            "font-src 'self' https: data:; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp

        # 5. HSTS cuando la conexión exige transporte seguro
        if getattr(settings, "COOKIE_SECURE", False) or settings.ENV.lower() in ("prod", "production"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
