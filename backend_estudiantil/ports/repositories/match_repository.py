from abc import ABC, abstractmethod

from backend_estudiantil.domain.models.match import Match


class MatchRepository(ABC):
    """Puerto para la persistencia de coincidencias (matches)."""

    @abstractmethod
    async def get_by_id(self, match_id: int) -> Match | None:
        ...

    @abstractmethod
    async def list_by_usuario(self, usuario_id: int, skip: int = 0, limit: int = 50) -> list[Match]:
        ...

    @abstractmethod
    async def create(self, match: Match) -> Match:
        ...

    @abstractmethod
    async def get_existing_match(self, origen_id: int, destino_id: int) -> Match | None:
        ...

    async def get_existing_destination_ids(self, origen_id: int) -> set[int]:
        """Retorna el conjunto de IDs de publicaciones destino que ya tienen match con origen_id."""
        return set()
