
from sqlalchemy.future import select

from backend_estudiantil.adapters.db import UserORM, get_session_factory
from backend_estudiantil.domain.models.user import User
from backend_estudiantil.ports.repositories.user_repository import UserRepository


class SQLAlchemyUserRepository(UserRepository):
    """Implementación en SQLAlchemy del repositorio de usuarios sobre la tabla 'usuarios'."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    @property
    def session_factory(self):
        return self._session_factory if self._session_factory is not None else get_session_factory()

    async def _to_entity(self, orm: UserORM) -> User:
        return User(
            id=orm.id,
            nombre=orm.nombre,
            apellido=orm.apellido,
            correo_institucional=orm.correo_institucional,
            password_hash=orm.password_hash,
            tipo_usuario=getattr(orm, "tipo_usuario", "estudiante"),
            programa_area=getattr(orm, "programa_area", None),
            rol=getattr(orm, "rol", "usuario"),
            verificado_comunidad=getattr(orm, "verificado_comunidad", False),
            estado_cuenta=getattr(orm, "estado_cuenta", "activo"),
            fecha_registro=orm.fecha_registro,
            telefono=getattr(orm, "telefono", None),
            universidad=getattr(orm, "universidad", None),
            semestre=getattr(orm, "semestre", None),
            foto_url=getattr(orm, "foto_url", None),
            carnet_path=getattr(orm, "carnet_path", None),
            carnet_estado=getattr(orm, "carnet_estado", None),
            carnet_rechazo_motivo=getattr(orm, "carnet_rechazo_motivo", None),
            perfil_completo=getattr(orm, "perfil_completo", False),
            codigo_confirmacion=getattr(orm, "codigo_confirmacion", None),
            codigo_confirmacion_expira=getattr(orm, "codigo_confirmacion_expira", None),
            codigo_confirmacion_intentos=getattr(orm, "codigo_confirmacion_intentos", 0) or 0,
            correo_confirmado=getattr(orm, "correo_confirmado", False) or False,
            facultad=getattr(orm, "facultad", None),
            organizacion_id=getattr(orm, "organizacion_id", None),
            fin_suspension=getattr(orm, "fin_suspension", None),
            motivo_sancion=getattr(orm, "motivo_sancion", None),
        )

    async def get_by_id(self, user_id) -> User | None:
        async with self.session_factory() as session:
            try:
                uid = int(user_id)
                result = await session.execute(select(UserORM).where(UserORM.id == uid))
            except (ValueError, TypeError):
                result = await session.execute(select(UserORM).where(UserORM.correo_institucional == str(user_id)))
            orm = result.scalar_one_or_none()
            return await self._to_entity(orm) if orm else None

    async def get_by_ids(self, user_ids: list[int]) -> dict[int, User]:
        """Carga en lote múltiples usuarios por sus IDs numéricos."""
        if not user_ids:
            return {}
        uids = [int(u) for u in user_ids if u is not None]
        if not uids:
            return {}
        async with self.session_factory() as session:
            result = await session.execute(select(UserORM).where(UserORM.id.in_(uids)))
            users = {}
            for orm in result.scalars().all():
                ent = await self._to_entity(orm)
                users[ent.id] = ent
            return users

    async def get_by_email(self, email: str) -> User | None:
        async with self.session_factory() as session:
            result = await session.execute(select(UserORM).where(UserORM.correo_institucional == email))
            orm = result.scalar_one_or_none()
            return await self._to_entity(orm) if orm else None

    async def create(self, user: User) -> User:
        async with self.session_factory() as session:
            orm = UserORM(
                nombre=user.nombre or "Estudiante",
                apellido=user.apellido or "",
                correo_institucional=user.correo_institucional,
                password_hash=user.password_hash,
                tipo_usuario=user.tipo_usuario or "estudiante",
                programa_area=user.programa_area,
                facultad=user.facultad,
                rol=user.rol or "usuario",
                verificado_comunidad=user.verificado_comunidad,
                estado_cuenta=user.estado_cuenta or "activo",
                telefono=user.telefono,
                universidad=user.universidad,
                semestre=user.semestre,
                foto_url=user.foto_url,
                carnet_path=user.carnet_path,
                carnet_estado=user.carnet_estado,
                carnet_rechazo_motivo=user.carnet_rechazo_motivo,
                perfil_completo=user.perfil_completo,
                codigo_confirmacion=user.codigo_confirmacion,
                codigo_confirmacion_expira=user.codigo_confirmacion_expira,
                codigo_confirmacion_intentos=user.codigo_confirmacion_intentos,
                correo_confirmado=user.correo_confirmado,
                organizacion_id=user.organizacion_id,
                fin_suspension=user.fin_suspension,
                motivo_sancion=user.motivo_sancion,
            )
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return await self._to_entity(orm)

    async def update(self, user: User) -> User:
        async with self.session_factory() as session:
            uid = int(user.id)
            result = await session.execute(select(UserORM).where(UserORM.id == uid))
            orm = result.scalar_one_or_none()
            if not orm:
                raise ValueError("User not found for update")
            orm.nombre = user.nombre
            orm.apellido = user.apellido
            orm.correo_institucional = user.correo_institucional
            orm.password_hash = user.password_hash
            orm.rol = user.rol
            orm.estado_cuenta = user.estado_cuenta
            orm.programa_area = user.programa_area
            orm.facultad = user.facultad
            orm.verificado_comunidad = user.verificado_comunidad
            orm.telefono = user.telefono
            orm.universidad = user.universidad
            orm.semestre = user.semestre
            orm.foto_url = user.foto_url
            orm.carnet_path = user.carnet_path
            orm.carnet_estado = user.carnet_estado
            orm.carnet_rechazo_motivo = user.carnet_rechazo_motivo
            orm.perfil_completo = user.perfil_completo
            orm.codigo_confirmacion = user.codigo_confirmacion
            orm.codigo_confirmacion_expira = user.codigo_confirmacion_expira
            orm.codigo_confirmacion_intentos = user.codigo_confirmacion_intentos
            orm.correo_confirmado = user.correo_confirmado
            orm.organizacion_id = user.organizacion_id
            orm.fin_suspension = user.fin_suspension
            orm.motivo_sancion = user.motivo_sancion
            await session.commit()
            await session.refresh(orm)
            return await self._to_entity(orm)

    async def delete(self, user_id) -> None:
        async with self.session_factory() as session:
            try:
                uid = int(user_id)
                result = await session.execute(select(UserORM).where(UserORM.id == uid))
            except (ValueError, TypeError):
                result = await session.execute(select(UserORM).where(UserORM.correo_institucional == str(user_id)))
            orm = result.scalar_one_or_none()
            if orm:
                await session.delete(orm)
                await session.commit()

    async def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        async with self.session_factory() as session:
            result = await session.execute(select(UserORM).order_by(UserORM.id.desc()).offset(skip).limit(limit))
            orms = result.scalars().all()
            return [await self._to_entity(o) for o in orms]

