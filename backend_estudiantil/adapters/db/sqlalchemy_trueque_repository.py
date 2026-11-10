
from sqlalchemy import and_, or_
from sqlalchemy.future import select

from backend_estudiantil.adapters.db import (
    MatchORM,
    PublicacionORM,
    TruequeORM,
    get_session_factory,
)
from backend_estudiantil.domain.models.trueque import Trueque
from backend_estudiantil.ports.repositories.trueque_repository import TruequeRepository


class SQLAlchemyTruequeRepository(TruequeRepository):
    """Implementación SQLAlchemy del repositorio de trueques sobre la tabla 'trueques'."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    @property
    def session_factory(self):
        return self._session_factory if self._session_factory is not None else get_session_factory()

    def _to_entity(self, orm: TruequeORM) -> Trueque:
        return Trueque(
            id=orm.id,
            match_id=orm.match_id,
            usuario_propone_id=orm.usuario_propone_id,
            usuario_recibe_id=orm.usuario_recibe_id,
            estado=orm.estado,
            fecha_propuesta=orm.fecha_propuesta,
            fecha_confirmacion=orm.fecha_confirmacion,
            fecha_completado=orm.fecha_completado,
        )

    async def get_by_id(self, trueque_id: int) -> Trueque | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(TruequeORM).where(TruequeORM.id == trueque_id)
            )
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def list_by_usuario(
        self, usuario_id: int, estado: str | None = None, skip: int = 0, limit: int = 50
    ) -> list[Trueque]:
        """Retorna trueques en los que el usuario participa (como proponente o receptor)."""
        async with self.session_factory() as session:
            from sqlalchemy import or_
            query = select(TruequeORM).where(
                or_(
                    TruequeORM.usuario_propone_id == usuario_id,
                    TruequeORM.usuario_recibe_id == usuario_id,
                )
            )
            if estado:
                query = query.where(TruequeORM.estado == estado)
            query = query.order_by(TruequeORM.id.desc()).offset(skip).limit(limit)
            result = await session.execute(query)
            orms = result.scalars().all()
            return [self._to_entity(o) for o in orms]

    async def create(self, trueque: Trueque) -> Trueque:
        async with self.session_factory() as session:
            orm = TruequeORM(
                match_id=trueque.match_id,
                usuario_propone_id=trueque.usuario_propone_id,
                usuario_recibe_id=trueque.usuario_recibe_id,
                estado=trueque.estado,
            )
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    async def create_from_publications(
        self,
        usuario_propone_id: int,
        publicacion_origen_id: int,
        publicacion_destino_id: int,
        usuario_recibe_id: int | None = None,
    ) -> Trueque:
        async with self.session_factory() as session:
            result = await session.execute(
                select(PublicacionORM)
                .where(
                    PublicacionORM.id.in_(
                        [publicacion_origen_id, publicacion_destino_id]
                    )
                )
                .with_for_update()
            )
            publicaciones = {pub.id: pub for pub in result.scalars().all()}
            origen = publicaciones.get(publicacion_origen_id)
            destino = publicaciones.get(publicacion_destino_id)

            if origen is None or destino is None:
                raise ValueError("Una o ambas publicaciones no existen")
            if origen.id == destino.id:
                raise ValueError("Debes seleccionar dos publicaciones diferentes")
            if origen.usuario_id != usuario_propone_id:
                raise PermissionError("Solo puedes ofrecer una publicación propia")
            if origen.usuario_id == destino.usuario_id:
                raise ValueError("No puedes proponer un trueque contigo mismo")
            if usuario_recibe_id is not None and usuario_recibe_id != destino.usuario_id:
                raise ValueError("El usuario receptor no corresponde a la publicación solicitada")
            if str(origen.estado_publicacion) != "activa":
                raise ValueError("La publicación que ofreces no está activa")
            if str(destino.estado_publicacion) != "activa":
                raise ValueError("La publicación solicitada no está activa")

            propuesta_existente = await session.execute(
                select(TruequeORM)
                .join(MatchORM, TruequeORM.match_id == MatchORM.id)
                .where(
                    or_(
                        and_(
                            MatchORM.publicacion_origen_id == origen.id,
                            MatchORM.publicacion_destino_id == destino.id,
                        ),
                        and_(
                            MatchORM.publicacion_origen_id == destino.id,
                            MatchORM.publicacion_destino_id == origen.id,
                        ),
                    ),
                    TruequeORM.estado != "rechazado",
                )
            )
            if propuesta_existente.scalar_one_or_none() is not None:
                raise ValueError("Ya existe un trueque activo o completado entre estos libros")

            result = await session.execute(
                select(MatchORM).where(
                    MatchORM.publicacion_origen_id == origen.id,
                    MatchORM.publicacion_destino_id == destino.id,
                )
            )
            match = result.scalar_one_or_none()
            if match is None:
                match = MatchORM(
                    publicacion_origen_id=origen.id,
                    publicacion_destino_id=destino.id,
                    tipo_match="similar",
                    puntuacion=0,
                )
                session.add(match)
                await session.flush()

            trueque = TruequeORM(
                match_id=match.id,
                usuario_propone_id=usuario_propone_id,
                usuario_recibe_id=destino.usuario_id,
                estado="propuesto",
            )
            session.add(trueque)
            await session.commit()
            await session.refresh(trueque)
            return self._to_entity(trueque)

    async def create_from_match(
        self,
        usuario_propone_id: int,
        match_id: int,
        usuario_recibe_id: int | None = None,
    ) -> Trueque:
        async with self.session_factory() as session:
            result = await session.execute(
                select(MatchORM).where(MatchORM.id == match_id)
            )
            match = result.scalar_one_or_none()
            if match is None:
                raise ValueError("El match indicado no existe")

            result = await session.execute(
                select(PublicacionORM)
                .where(
                    PublicacionORM.id.in_(
                        [match.publicacion_origen_id, match.publicacion_destino_id]
                    )
                )
                .with_for_update()
            )
            publicaciones = {pub.id: pub for pub in result.scalars().all()}
            origen = publicaciones.get(match.publicacion_origen_id)
            destino = publicaciones.get(match.publicacion_destino_id)
            if origen is None or destino is None:
                raise ValueError("Las publicaciones asociadas al match no existen")
            if origen.usuario_id != usuario_propone_id:
                raise PermissionError("Solo puedes proponer un trueque con un match de tu publicación")
            if usuario_recibe_id is not None and usuario_recibe_id != destino.usuario_id:
                raise ValueError("El usuario receptor no corresponde al match")
            if origen.usuario_id == destino.usuario_id:
                raise ValueError("No puedes proponer un trueque contigo mismo")
            if str(origen.estado_publicacion) != "activa" or str(destino.estado_publicacion) != "activa":
                raise ValueError("Ambas publicaciones deben estar activas")
            propuesta_existente = await session.execute(
                select(TruequeORM).where(
                    TruequeORM.match_id == match.id,
                    TruequeORM.estado != "rechazado",
                )
            )
            if propuesta_existente.scalar_one_or_none() is not None:
                raise ValueError("Ya existe un trueque activo o completado para este match")

            trueque = TruequeORM(
                match_id=match.id,
                usuario_propone_id=usuario_propone_id,
                usuario_recibe_id=destino.usuario_id,
                estado="propuesto",
            )
            session.add(trueque)
            await session.commit()
            await session.refresh(trueque)
            return self._to_entity(trueque)

    async def update(self, trueque: Trueque) -> Trueque:
        async with self.session_factory() as session:
            result = await session.execute(
                select(TruequeORM).where(TruequeORM.id == trueque.id)
            )
            orm = result.scalar_one_or_none()
            if not orm:
                raise ValueError("Trueque no encontrado para actualizar")
            orm.estado = trueque.estado
            orm.fecha_confirmacion = trueque.fecha_confirmacion
            orm.fecha_completado = trueque.fecha_completado
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)
