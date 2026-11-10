
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (
    SQLAlchemyUserRepository,
)
from backend_estudiantil.adapters.security.jwt_authenticator import JWTAuthenticator
from backend_estudiantil.ports.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_user_repository() -> UserRepository:
    return SQLAlchemyUserRepository()

def get_authenticator() -> JWTAuthenticator:
    return JWTAuthenticator()

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    repo: UserRepository = Depends(get_user_repository),
    authenticator: JWTAuthenticator = Depends(get_authenticator),
) -> dict:
    """Extrae y valida el usuario actual a partir del token JWT de autorización."""
    try:
        payload = authenticator.decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        user = await repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        from backend_estudiantil.domain.services.moderacion_sanciones_service import (
            usuario_puede_operar,
        )
        res_op = usuario_puede_operar(user)
        if not res_op.puede_operar:
            fin_str = f" hasta {res_op.fecha_fin.strftime('%Y-%m-%d %H:%M:%S UTC')}." if res_op.fecha_fin else "."
            motivo_str = f" Motivo: {res_op.motivo}." if res_op.motivo else ""
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cuenta {res_op.estado_cuenta}{fin_str}{motivo_str}",
            )
        if user.estado_cuenta == "activo" and getattr(user, "_suspension_expirada", False):
            await repo.update(user)
        return {
            "id": user.id,
            "email": user.correo_institucional,
            "role": user.rol or payload.get("role", "usuario"),
            "name": user.name,
            "is_active": user.is_active,
            "telefono": user.telefono,
            "carrera": user.programa_area,
            "universidad": user.universidad,
            "created_at": user.fecha_registro.isoformat() if hasattr(user.fecha_registro, "isoformat") else str(user.fecha_registro),
            "updated_at": user.fecha_registro.isoformat() if hasattr(user.fecha_registro, "isoformat") else str(user.fecha_registro),
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
