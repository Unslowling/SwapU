
from sqlalchemy import String, cast, func, or_
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend_estudiantil.adapters.db import PublicacionORM, get_session_factory
from backend_estudiantil.domain.models.publicacion import Publicacion
from backend_estudiantil.ports.repositories.publicacion_repository import (
    PublicacionRepository,
)


class SQLAlchemyPublicacionRepository(PublicacionRepository):
    """Implementación SQLAlchemy del repositorio de publicaciones sobre la tabla 'publicaciones'."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    @property
    def session_factory(self):
        return self._session_factory if self._session_factory is not None else get_session_factory()

    def _to_entity(self, orm: PublicacionORM) -> Publicacion:
        usuario_nombre = None
        usuario_carrera = None
        usuario_universidad = None
        usuario_avatar = None
        categoria_nombre = None

        if orm.__dict__.get("usuario"):
            u = orm.__dict__["usuario"]
            usuario_nombre = f"{u.nombre} {u.apellido or ''}".strip()
            usuario_carrera = getattr(u, "programa_area", None)
            usuario_universidad = getattr(u, "universidad", None)
            usuario_avatar = getattr(u, "foto_url", None)
        if orm.__dict__.get("categoria"):
            categoria_nombre = orm.__dict__["categoria"].nombre

        return Publicacion(
            id=orm.id,
            usuario_id=orm.usuario_id,
            titulo=orm.titulo,
            autor=orm.autor,
            isbn=orm.isbn,
            edicion=orm.edicion,
            categoria_id=orm.categoria_id,
            estado_libro=orm.estado_libro,
            descripcion=orm.descripcion,
            libro_buscado=orm.libro_buscado,
            estado_publicacion=orm.estado_publicacion,
            fecha_publicacion=orm.fecha_publicacion,
            tipo_transaccion=getattr(orm, "tipo_transaccion", "trueque") or "trueque",
            fecha_devolucion=getattr(orm, "fecha_devolucion", None),
            organizacion_id=getattr(orm, "organizacion_id", None),
            usuario_nombre=usuario_nombre,
            usuario_carrera=usuario_carrera,
            usuario_universidad=usuario_universidad,
            usuario_avatar=usuario_avatar,
            categoria_nombre=categoria_nombre,
        )

    async def get_by_id(self, publicacion_id: int) -> Publicacion | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(PublicacionORM)
                .options(selectinload(PublicacionORM.usuario), selectinload(PublicacionORM.categoria))
                .where(PublicacionORM.id == publicacion_id)
            )
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def list_activas(
        self,
        skip: int = 0,
        limit: int = 50,
        categoria_id: int | None = None,
        busqueda: str | None = None,
        organizacion_id: int | None = None,
    ) -> list[Publicacion]:
        async with self.session_factory() as session:
            query = (
                select(PublicacionORM)
                .options(selectinload(PublicacionORM.usuario), selectinload(PublicacionORM.categoria))
                .where(cast(PublicacionORM.estado_publicacion, String) == "activa")
            )

            if organizacion_id is not None:
                query = query.where(PublicacionORM.organizacion_id == organizacion_id)

            if categoria_id is not None:
                query = query.where(PublicacionORM.categoria_id == categoria_id)

            if busqueda:
                patron = f"%{busqueda}%"
                query = query.where(
                    or_(
                        PublicacionORM.titulo.ilike(patron),
                        PublicacionORM.autor.ilike(patron),
                        PublicacionORM.libro_buscado.ilike(patron),
                        PublicacionORM.descripcion.ilike(patron),
                    )
                )

            query = query.order_by(PublicacionORM.fecha_publicacion.desc()).offset(skip).limit(limit)
            result = await session.execute(query)
            orms = result.scalars().all()
            return [self._to_entity(o) for o in orms]

    async def list_by_usuario(self, usuario_id: int) -> list[Publicacion]:
        async with self.session_factory() as session:
            result = await session.execute(
                select(PublicacionORM)
                .options(selectinload(PublicacionORM.usuario), selectinload(PublicacionORM.categoria))
                .where(PublicacionORM.usuario_id == usuario_id)
            )
            orms = result.scalars().all()
            return [self._to_entity(o) for o in orms]

    async def count_activas_by_usuario(self, usuario_id: int) -> int:
        async with self.session_factory() as session:
            result = await session.execute(
                select(func.count(PublicacionORM.id)).where(
                    PublicacionORM.usuario_id == usuario_id,
                    cast(PublicacionORM.estado_publicacion, String) == "activa",
                )
            )
            return result.scalar_one() or 0

    async def create(self, publicacion: Publicacion) -> Publicacion:
        async with self.session_factory() as session:
            orm = PublicacionORM(
                usuario_id=publicacion.usuario_id,
                titulo=publicacion.titulo,
                autor=publicacion.autor,
                isbn=publicacion.isbn,
                edicion=publicacion.edicion,
                categoria_id=publicacion.categoria_id,
                estado_libro=publicacion.estado_libro,
                descripcion=publicacion.descripcion,
                libro_buscado=publicacion.libro_buscado,
                estado_publicacion=publicacion.estado_publicacion,
                tipo_transaccion=publicacion.tipo_transaccion or "trueque",
                fecha_devolucion=publicacion.fecha_devolucion,
                organizacion_id=publicacion.organizacion_id,
            )
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    async def update(self, publicacion: Publicacion) -> Publicacion:
        async with self.session_factory() as session:
            result = await session.execute(
                select(PublicacionORM).where(PublicacionORM.id == publicacion.id)
            )
            orm = result.scalar_one_or_none()
            if not orm:
                raise ValueError("Publicación no encontrada para actualizar")
            orm.titulo = publicacion.titulo
            orm.autor = publicacion.autor
            orm.isbn = publicacion.isbn
            orm.edicion = publicacion.edicion
            orm.categoria_id = publicacion.categoria_id
            orm.estado_libro = publicacion.estado_libro
            orm.descripcion = publicacion.descripcion
            orm.libro_buscado = publicacion.libro_buscado
            orm.estado_publicacion = publicacion.estado_publicacion
            orm.tipo_transaccion = publicacion.tipo_transaccion or "trueque"
            orm.fecha_devolucion = publicacion.fecha_devolucion
            orm.organizacion_id = publicacion.organizacion_id
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    async def delete(self, publicacion_id: int) -> None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(PublicacionORM).where(PublicacionORM.id == publicacion_id)
            )
            orm = result.scalar_one_or_none()
            if orm:
                await session.delete(orm)
                await session.commit()
