import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from backend_estudiantil.adapters.notifications.email_sender import SMTPEmailSender
from backend_estudiantil.adapters.security.password_hasher import (
    hash_password_async,
    verify_password_async,
)
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.models.user import User
from backend_estudiantil.ports.notifications.email_sender import EmailSender
from backend_estudiantil.ports.repositories.user_repository import UserRepository
from backend_estudiantil.schemas.user import UserCreate, UserUpdate


class UserService:
    """Servicio de dominio para la lógica de negocio de usuarios y estudiantes."""

    def __init__(self, repo: UserRepository, email_sender: EmailSender | None = None):
        self.repo = repo
        self.email_sender = email_sender or SMTPEmailSender()

    async def _hash_password(self, password: str) -> str:
        """Genera hash seguro de contraseña (bcrypt con asyncio.to_thread)."""
        return await hash_password_async(password)

    async def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Valida una contraseña contra su hash (bcrypt con asyncio.to_thread)."""
        return await verify_password_async(plain_password, hashed_password)

    async def create_user(self, payload: UserCreate) -> User:
        # Verificar si el correo ya existe
        existing = await self.repo.get_by_email(payload.email)
        if existing:
            raise ValueError("El correo electrónico ya está registrado")

        hashed = await self._hash_password(payload.password)

        # Regla: NO marcar verificado_comunidad=True solo por el dominio en registro con contraseña.
        # Si el correo es de dominio institucional, se envía código de confirmación.
        es_inst = settings.es_dominio_institucional(payload.email)
        universidad = settings.obtener_universidad_por_dominio(payload.email) if es_inst else getattr(payload, "universidad", None)
        carrera = getattr(payload, "carrera", None)
        facultad = getattr(payload, "facultad", None)
        nombre = payload.name or ""
        perfil_completo = bool(nombre.strip() and universidad and carrera)

        codigo_conf_hash = None
        codigo_conf_raw = None
        expira_conf = None
        if es_inst:
            codigo_conf_raw = f"{secrets.randbelow(900000) + 100000}"
            codigo_conf_hash = hashlib.sha256(codigo_conf_raw.encode("utf-8")).hexdigest()
            expira_conf = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)

        user = User(
            correo_institucional=payload.email,
            password_hash=hashed,
            name=payload.name,
            rol="administrador" if (payload.role or "").lower() in ("admin", "administrador") else "usuario",
            estado_cuenta="activo",
            verificado_comunidad=False,  # Inicia False hasta que se confirme el código/enlace
            programa_area=carrera,
            facultad=facultad,
            universidad=universidad,
            telefono=getattr(payload, "telefono", None),
            semestre=getattr(payload, "semestre", None),
            foto_url=getattr(payload, "foto_url", None),
            perfil_completo=perfil_completo,
            codigo_confirmacion=codigo_conf_hash,
            codigo_confirmacion_expira=expira_conf,
            codigo_confirmacion_intentos=0,
            correo_confirmado=False,
        )
        created_user = await self.repo.create(user)

        # Enviar código o enlace de confirmación al correo institucional
        if es_inst and codigo_conf_raw:
            enlace = f"{settings.APP_BASE_URL}/auth/confirmar-correo?email={payload.email}&codigo={codigo_conf_raw}"
            try:
                await self.email_sender.send_verification_code(payload.email, codigo_conf_raw, enlace)
            except Exception:
                pass

        return created_user

    async def get_user(self, user_id: str) -> User:
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        return user

    async def get_by_email(self, email: str) -> User | None:
        return await self.repo.get_by_email(email)

    async def get_users(self, skip: int = 0, limit: int = 100) -> list[User]:
        return await self.repo.list(skip=skip, limit=limit)

    async def update_user(self, user_id: str, payload: UserUpdate) -> User:
        user = await self.get_user(user_id)
        if payload.email and payload.email != user.correo_institucional:
            existing = await self.repo.get_by_email(payload.email)
            if existing and existing.id != user.id:
                raise ValueError("El correo electrónico ya está en uso")
            user.correo_institucional = payload.email
            # Regla de seguridad: Si el usuario cambia su correo, verificado_comunidad vuelve a False
            user.verificado_comunidad = False
            user.correo_confirmado = False
            user.carnet_estado = "sin_verificar"
            user.carnet_rechazo_motivo = None

            if settings.es_dominio_institucional(payload.email):
                raw_codigo = f"{secrets.randbelow(900000) + 100000}"
                user.codigo_confirmacion = hashlib.sha256(raw_codigo.encode("utf-8")).hexdigest()
                user.codigo_confirmacion_expira = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
                user.codigo_confirmacion_intentos = 0
                enlace = f"{settings.APP_BASE_URL}/auth/confirmar-correo?email={payload.email}&codigo={raw_codigo}"
                try:
                    await self.email_sender.send_verification_code(payload.email, raw_codigo, enlace)
                except Exception:
                    pass
            else:
                user.codigo_confirmacion = None
                user.codigo_confirmacion_expira = None
                user.codigo_confirmacion_intentos = 0

        if payload.name is not None:
            user.name = payload.name

        if getattr(payload, "carrera", None) is not None:
            user.programa_area = payload.carrera

        if getattr(payload, "facultad", None) is not None:
            user.facultad = payload.facultad

        if getattr(payload, "universidad", None) is not None:
            user.universidad = payload.universidad

        if getattr(payload, "telefono", None) is not None:
            user.telefono = payload.telefono

        if getattr(payload, "semestre", None) is not None:
            user.semestre = payload.semestre

        if getattr(payload, "foto_url", None) is not None:
            user.foto_url = payload.foto_url

        if getattr(payload, "perfil_completo", None) is not None:
            user.perfil_completo = payload.perfil_completo
        else:
            # Autocalcular perfil_completo si cuenta con datos clave
            user.perfil_completo = bool(
                user.name and user.name.strip() and user.universidad and user.programa_area
            )

        if payload.password:
            user.password_hash = await self._hash_password(payload.password)

        return await self.repo.update(user)

    async def promote_to_moderator(self, user_id: str) -> User:
        """Promueve al usuario a rol 'moderador'."""
        user = await self.get_user(user_id)
        user.rol = "moderador"
        return await self.repo.update(user)

    async def deactivate_user(self, user_id: str) -> User:
        """Desactiva un usuario (borrado lógico para preservar integridad de trueques y valoraciones)."""
        user = await self.get_user(user_id)
        user.estado_cuenta = "bloqueado"
        return await self.repo.update(user)

    async def delete_user(self, user_id: str) -> None:
        """Elimina un usuario por su ID."""
        user = await self.repo.get_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        await self.repo.delete(user_id)

    async def confirmar_codigo_verificacion(self, email: str, codigo: str) -> User:
        """Confirma el código de verificación del correo institucional y activa verificado_comunidad.
        Valida usando hmac.compare_digest contra el hash SHA-256 y controla un límite de 5 intentos.
        """
        user = await self.repo.get_by_email(email)
        if not user:
            # Respuesta genérica para no revelar si el correo existe
            raise ValueError("Código de confirmación o correo inválido")

        if user.verificado_comunidad and user.correo_confirmado:
            return user

        if not user.codigo_confirmacion:
            raise ValueError("Código de confirmación o correo inválido")

        # Control de intentos fallidos (máximo 5)
        intentos_actuales = user.codigo_confirmacion_intentos or 0
        if intentos_actuales >= 5:
            user.codigo_confirmacion = None
            user.codigo_confirmacion_expira = None
            user.codigo_confirmacion_intentos = 0
            await self.repo.update(user)
            raise ValueError("Has superado el número máximo de intentos permitidos (5). Debes solicitar un nuevo código")

        # Comparación segura de hash SHA-256 con hmac.compare_digest
        input_hash = hashlib.sha256(codigo.strip().encode("utf-8")).hexdigest()
        if not hmac.compare_digest(user.codigo_confirmacion, input_hash):
            user.codigo_confirmacion_intentos = intentos_actuales + 1
            if user.codigo_confirmacion_intentos >= 5:
                user.codigo_confirmacion = None
                user.codigo_confirmacion_expira = None
                user.codigo_confirmacion_intentos = 0
                await self.repo.update(user)
                raise ValueError("Has superado el número máximo de intentos permitidos (5). Debes solicitar un nuevo código")
            await self.repo.update(user)
            raise ValueError(f"Código de confirmación incorrecto. Intento {user.codigo_confirmacion_intentos} de 5")

        if user.codigo_confirmacion_expira:
            expira = user.codigo_confirmacion_expira
            if expira.tzinfo is not None:
                expira = expira.replace(tzinfo=None)
            ahora = datetime.now(timezone.utc).replace(tzinfo=None)
            if ahora > expira:
                raise ValueError("El código de confirmación ha expirado. Solicita un nuevo código")

        # Activar verificación de comunidad y confirmar correo
        user.verificado_comunidad = True
        user.correo_confirmado = True
        user.carnet_estado = "verificado"
        user.carnet_rechazo_motivo = None
        if not user.universidad:
            user.universidad = settings.obtener_universidad_por_dominio(user.correo_institucional)
        user.codigo_confirmacion = None
        user.codigo_confirmacion_expira = None
        user.codigo_confirmacion_intentos = 0
        user.perfil_completo = bool(user.name and user.universidad and user.programa_area)
        return await self.repo.update(user)

    async def reenviar_codigo_verificacion(self, email: str) -> User | None:
        """Genera y reenvía un nuevo código de confirmación al correo institucional.
        Responde de forma genérica para no revelar si el correo está registrado.
        """
        user = await self.repo.get_by_email(email)
        if not user:
            # Respuesta genérica silenciosa
            return None

        if user.verificado_comunidad and user.correo_confirmado:
            return user

        if not settings.es_dominio_institucional(email):
            return user

        nuevo_codigo_raw = f"{secrets.randbelow(900000) + 100000}"
        user.codigo_confirmacion = hashlib.sha256(nuevo_codigo_raw.encode("utf-8")).hexdigest()
        user.codigo_confirmacion_expira = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
        user.codigo_confirmacion_intentos = 0
        updated_user = await self.repo.update(user)

        enlace = f"{settings.APP_BASE_URL}/auth/confirmar-correo?email={email}&codigo={nuevo_codigo_raw}"
        try:
            await self.email_sender.send_verification_code(email, nuevo_codigo_raw, enlace)
        except Exception:
            pass

        return updated_user

