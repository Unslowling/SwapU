from abc import ABC, abstractmethod

from backend_estudiantil.domain.models.calificacion import Calificacion


class CalificacionRepository(ABC):
    """Puerto para la persistencia de valoraciones y reputación."""

    @abstractmethod
    async def get_by_id(self, calificacion_id: int) -> Calificacion | None:
        ...

    @abstractmethod
    async def list_by_usuario_calificado(self, usuario_id: int) -> list[Calificacion]:
        ...

    @abstractmethod
    async def get_by_trueque_and_calificador(self, trueque_id: int, calificador_id: int) -> Calificacion | None:
        ...

    @abstractmethod
    async def create(self, calificacion: Calificacion) -> Calificacion:
        ...

    @abstractmethod
    async def get_global_rating_stats(self) -> tuple[float, int]:
        ...

