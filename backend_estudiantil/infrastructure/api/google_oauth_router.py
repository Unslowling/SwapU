import json

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from backend_estudiantil.adapters.security.google_oauth2_authenticator import (
    GoogleOAuth2Authenticator,
)
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.models.user import User
from backend_estudiantil.ports.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth/google", tags=["auth"])

def get_user_repository() -> UserRepository:
    return SQLAlchemyUserRepository()

def get_jwt_authenticator() -> JWTAuthenticator:
    return JWTAuthenticator()

def get_google_authenticator() -> GoogleOAuth2Authenticator:
    return GoogleOAuth2Authenticator()

@router.get("/login")
async def google_login(authenticator: GoogleOAuth2Authenticator = Depends(get_google_authenticator)):
    """Redirige al usuario a la URL de autorización de Google OAuth2."""
    url = await authenticator.get_authorization_url()
    return RedirectResponse(url)

@router.get("/callback")
async def google_callback(
    code: str,
    request: Request,
    response: Response,
    repo: UserRepository = Depends(get_user_repository),
    jwt_auth: JWTAuthenticator = Depends(get_jwt_authenticator),
    google_auth: GoogleOAuth2Authenticator = Depends(get_google_authenticator),
):
    """Callback de Google OAuth2. Intercambia el código por tokens y perfil, y responde con HTML para la ventana popup."""
    token_data = await google_auth.exchange_code(code)
    access_token_google = token_data.get("access_token")
    if not access_token_google:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing access token from Google")

    userinfo = await google_auth.get_userinfo(access_token_google)
    email = userinfo.get("email")
    name = userinfo.get("name")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google account has no email")

    # Exigir estrictamente email_verified=true en Google OAuth
    email_verified = userinfo.get("email_verified")
    if email_verified is None:
        email_verified = userinfo.get("verified_email")

    if not email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La cuenta de Google debe tener el correo verificado (email_verified=true)",
        )

    es_inst = settings.es_dominio_institucional(email) and bool(email_verified)
    uni = settings.obtener_universidad_por_dominio(email) if es_inst else None

    # Si no existe, crear al usuario automáticamente
    user = await repo.get_by_email(email)
    if not user:
        user = User(
            correo_institucional=email,
            password_hash="",  # Sin contraseña para usuarios federados con Google
            name=name,
            rol="usuario",
            estado_cuenta="activo",
            verificado_comunidad=es_inst,
            universidad=uni,
            perfil_completo=bool(name and uni),
            foto_url=userinfo.get("picture"),
        )
        user = await repo.create(user)
    else:
        # Si ya existía, pero es institucional y Google certifica que el correo está verificado
        modificado = False
        if es_inst and not user.verificado_comunidad:
            user.verificado_comunidad = True
            if not user.universidad:
                user.universidad = uni
            user.codigo_confirmacion = None
            user.codigo_confirmacion_expira = None
            modificado = True
        if userinfo.get("picture") and not user.foto_url:
            user.foto_url = userinfo.get("picture")
            modificado = True
        if modificado:
            user = await repo.update(user)

    # Emitir tokens JWT
    role = user.rol
    payload = {"sub": str(user.id), "role": role}
    access_jwt = jwt_auth.create_access_token(payload)
    refresh_jwt = jwt_auth.create_refresh_token(payload)

    user_data = {
        "id": str(user.id),
        "email": user.correo_institucional,
        "name": user.name,
        "role": user.rol,
        "is_active": True,
        "carrera": user.programa_area or "",
        "universidad": user.universidad or "",
        "telefono": user.telefono or "",
        "semestre": getattr(user, "semestre", None),
        "verificado_comunidad": getattr(user, "verificado_comunidad", False),
        "verificado": getattr(user, "verificado_comunidad", False),
        "perfil_completo": getattr(user, "perfil_completo", False),
        "avatar": user.foto_url or f"https://ui-avatars.com/api/?name={name.replace(' ', '+') if name else 'U'}&background=ea4335&color=fff&size=150"
    }

    if "application/json" in request.headers.get("accept", ""):
        res = JSONResponse(
            content={
                "access_token": access_jwt,
                "role": user.rol,
                "user": user_data,
            }
        )
    else:
        # Render HTML for popup
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Autenticación Exitosa</title></head>
        <body>
        <script>
            window.opener.postMessage({{
                type: "OAUTH_SUCCESS",
                provider: "google",
                token: "{access_jwt}",
                user: {json.dumps(user_data)}
            }}, "*");
            window.close();
        </script>
        </body>
        </html>
        """
        res = HTMLResponse(content=html_content)

    res.set_cookie(
        key="refresh_token",
        value=refresh_jwt,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=60 * 60 * 24 * settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
    return res
