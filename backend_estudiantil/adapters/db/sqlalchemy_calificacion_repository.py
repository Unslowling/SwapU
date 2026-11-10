
# pyrefly: ignore [missing-import]
from sqlalchemy.future import select

from backend_estudiantil.adapters.db import CalificacionORM, get_session_factory
from backend_estudiantil.domain.models.calificacion import Calificacion
from backend_estudiantil.ports.repositories.calificacion_repository import (
    CalificacionRepository,
)


class SQLAlchemyCalificacionRepository(CalificacionRepository):
    """Implementación SQLAlchemy del repositorio de calificaciones sobre la tabla 'calificaciones'."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    @property
    def session_factory(self):
        return self._session_factory if self._session_factory is not None else get_session_factory()

    def _to_entity(self, orm: CalificacionORM) -> Calificacion:
        return Calificacion(
            id=orm.id,
            trueque_id=orm.trueque_id,
            usuario_califica_id=orm.usuario_califica_id,
            usuario_calificado_id=orm.usuario_calificado_id,
            estrellas=orm.estrellas,
            resena=orm.resena,
            fecha_calificacion=orm.fecha_calificacion,
        )

    async def get_by_id(self, calificacion_id: int) -> Calificacion | None:
        async with self.session_factory() as session:
            result = await session.execute(
                select(CalificacionORM).where(CalificacionORM.id == calificacion_id)
            )
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def list_by_usuario_calificado(self, usuario_id: int) -> list[Calificacion]:
        """Retorna todas las calificaciones recibidas por un usuario."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(CalificacionORM).where(CalificacionORM.usuario_calificado_id == usuario_id)
            )
            orms = result.scalars().all()
            return [self._to_entity(o) for o in orms]

    async def get_by_trueque_and_calificador(
        self, trueque_id: int, calificador_id: int
    ) -> Calificacion | None:
        """Verifica si un usuario ya calificó en un trueque (una calificación por participante)."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(CalificacionORM).where(
                    CalificacionORM.trueque_id == trueque_id,
                    CalificacionORM.usuario_califica_id == calificador_id,
                )
            )
            orm = result.scalar_one_or_none()
            return self._to_entity(orm) if orm else None

    async def create(self, calificacion: Calificacion) -> Calificacion:
        async with self.session_factory() as session:
            orm = CalificacionORM(
                trueque_id=calificacion.trueque_id,
                usuario_califica_id=calificacion.usuario_califica_id,
                usuario_calificado_id=calificacion.usuario_calificado_id,
                estrellas=calificacion.estrellas,
                resena=calificacion.resena,
            )
            session.add(orm)
            await session.commit()
            await session.refresh(orm)
            return self._to_entity(orm)

    async def get_global_rating_stats(self) -> tuple[float, int]:
        """Calcula la media global (m) y el total de calificaciones registradas en la plataforma."""
        from sqlalchemy import func
        async with self.session_factory() as session:
            result = await session.execute(
                select(func.avg(CalificacionORM.estrellas), func.count(CalificacionORM.id))
            )
            avg, count = result.one()
            media = float(avg) if avg is not None else 5.0
            total = int(count) if count is not None else 0
            return (media, total)

