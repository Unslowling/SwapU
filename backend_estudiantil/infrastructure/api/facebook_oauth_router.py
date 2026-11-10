import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from backend_estudiantil.adapters.security.facebook_oauth2_authenticator import (
    FacebookOAuth2Authenticator,
)
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.models.user import User
from backend_estudiantil.ports.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth/facebook", tags=["auth"])

def get_user_repository() -> UserRepository:
    return SQLAlchemyUserRepository()

def get_jwt_authenticator() -> JWTAuthenticator:
    return JWTAuthenticator()

def get_facebook_authenticator() -> FacebookOAuth2Authenticator:
    return FacebookOAuth2Authenticator()

@router.get("/login")
async def facebook_login(authenticator: FacebookOAuth2Authenticator = Depends(get_facebook_authenticator)):
    url = await authenticator.get_authorization_url()
    return RedirectResponse(url)

@router.get("/callback")
async def facebook_callback(
    code: str,
    response: Response,
    repo: UserRepository = Depends(get_user_repository),
    jwt_auth: JWTAuthenticator = Depends(get_jwt_authenticator),
    facebook_auth: FacebookOAuth2Authenticator = Depends(get_facebook_authenticator),
):
    token_data = await facebook_auth.exchange_code(code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing access token from Facebook")

    userinfo = await facebook_auth.get_userinfo(access_token)
    email = userinfo.get("email")
    name = userinfo.get("name")
    
    if not email:
        email = f"{userinfo.get('id')}@facebook.local"

    user = await repo.get_by_email(email)
    if not user:
        uni = settings.obtener_universidad_por_dominio(email)
        user = User(
            correo_institucional=email,
            password_hash="",
            name=name,
            rol="usuario",
            estado_cuenta="activo",
            verificado_comunidad=False,  # Facebook OAuth nunca otorga verificado_comunidad
            universidad=uni,
            perfil_completo=bool(name and uni),
        )
        await repo.create(user)

    role = user.rol
    payload = {"sub": str(user.id), "role": role}
    access_jwt = jwt_auth.create_access_token(payload)
    refresh_jwt = jwt_auth.create_refresh_token(payload)

    response.set_cookie(
        key="refresh_token",
        value=refresh_jwt,
        httponly=settings.COOKIE_HTTPONLY,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=60 * 60 * 24 * settings.REFRESH_TOKEN_EXPIRE_DAYS,
    )
    
    user_data = {
        "id": str(user.id),
        "email": user.correo_institucional,
        "name": user.name,
        "role": user.rol,
        "is_active": True,
        "avatar": f"https://ui-avatars.com/api/?name={name.replace(' ', '+') if name else 'U'}&background=1877F2&color=fff&size=150"
    }

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Autenticación Exitosa</title></head>
    <body>
    <script>
        window.opener.postMessage({{
            type: "OAUTH_SUCCESS",
            provider: "facebook",
            token: "{access_jwt}",
            user: {json.dumps(user_data)}
        }}, "*");
        window.close();
    </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
