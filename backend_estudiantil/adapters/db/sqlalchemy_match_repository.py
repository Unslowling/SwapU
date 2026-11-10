
from sqlalchemy import or_
from sqlalchemy.future import select

from backend_estudiantil.adapters.db import (
    MatchORM,
    PublicacionORM,
    TruequeORM,
    get_session_factory,
)
from backend_estudiantil.domain.models.match import Match
from backend_estudiantil.ports.repositories.match_repository import MatchRepository


class SQLAlchemyMatchRepository(MatchRepository):
    """Implementación SQLAlchemy del repositorio de matches sobre la tabla 'matches'."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    @property
    def session_factory(self):
        return self._session_factory if self._session_factory is not None else get_session_factory()

    def _to_entity(self, orm: MatchORM) -> Match:
        return Match(
            id=orm.id,
            publicacion_origen_id=orm.publicacion_origen_id,
            publicacion_destino_id=orm.publicacion_destino_id,
            tipo_match=orm.tipo_match,
            puntuacion=float(orm.puntuacion),
            fecha_creacion=orm.fecha_creacion,
        )

    async def get_by_id(self, match_id: int) -> Match | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(MatchORM).where(MatchORM.id == match_id)
            )
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def list_by_usuario(self, usuario_id: int, skip: int = 0, limit: int = 50) -> list[Match]:
        """Retorna matches paginados donde el usuario tiene publicaciones de origen o destino."""
        async with self.session_factory() as session:
            # Subconsulta: IDs de publicaciones del usuario
            pub_ids_result = await session.execute(
                select(PublicacionORM.id).where(PublicacionORM.usuario_id == usuario_id)
            )
            pub_ids = [row[0] for row in pub_ids_result.fetchall()]

            if not pub_ids:
                return []

            query = (
                select(MatchORM)
                .where(
                    or_(
                        MatchORM.publicacion_origen_id.in_(pub_ids),
                        MatchORM.publicacion_destino_id.in_(pub_ids),
                    ),
                    ~MatchORM.id.in_(
                        select(TruequeORM.match_id).where(
                            TruequeORM.estado != "rechazado",
                            TruequeORM.match_id.is_not(None),
                        )
                    ),
                )
                .order_by(MatchORM.id.desc())
                .offset(skip)
                .limit(limit)
            )
            result = await session.execute(query)
            orms = result.scalars().all()
            return [self._to_entity(o) for o in orms]

    async def create(self, match: Match) -> Match:
        async with self.session_factory() as session:
            orm = MatchORM(
                publicacion_origen_id=match.publicacion_origen_id,
                publicacion_destino_id=match.publicacion_destino_id,
                tipo_match=match.tipo_match,
                puntuacion=match.puntuacion,
            )
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    async def get_existing_match(self, origen_id: int, destino_id: int) -> Match | None:
        """Verifica si ya existe un match entre dos publicaciones (en cualquier dirección)."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(MatchORM).where(
                    or_(
                        (MatchORM.publicacion_origen_id == origen_id) & (MatchORM.publicacion_destino_id == destino_id),
                        (MatchORM.publicacion_origen_id == destino_id) & (MatchORM.publicacion_destino_id == origen_id),
                    )
                )
            )
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def get_existing_destination_ids(self, origen_id: int) -> set[int]:
        """Retorna en lote el conjunto de IDs de publicaciones que ya tienen match con origen_id."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(MatchORM.publicacion_origen_id, MatchORM.publicacion_destino_id).where(
                    or_(
                        MatchORM.publicacion_origen_id == origen_id,
                        MatchORM.publicacion_destino_id == origen_id,
                    )
                )
            )
            dest_ids = set()
            for orig, dest in result.fetchall():
                if orig == origen_id:
                    dest_ids.add(dest)
                else:
                    dest_ids.add(orig)
            return dest_ids
