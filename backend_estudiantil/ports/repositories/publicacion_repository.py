from abc import ABC, abstractmethod

from backend_estudiantil.domain.models.publicacion import Publicacion


class PublicacionRepository(ABC):
    """Puerto para la persistencia de publicaciones."""

    @abstractmethod
    async def get_by_id(self, publicacion_id: int) -> Publicacion | None:
        ...

    @abstractmethod
    async def list_activas(
        self,
        skip: int = 0,
        limit: int = 50,
        categoria_id: int | None = None,
        busqueda: str | None = None,
        organizacion_id: int | None = None,
    ) -> list[Publicacion]:
        ...

    @abstractmethod
    async def list_by_usuario(self, usuario_id: int) -> list[Publicacion]:
        ...

    @abstractmethod
    async def count_activas_by_usuario(self, usuario_id: int) -> int:
        ...

    @abstractmethod
    async def create(self, publicacion: Publicacion) -> Publicacion:
        ...

    @abstractmethod
    async def update(self, publicacion: Publicacion) -> Publicacion:
        ...

    @abstractmethod
    async def delete(self, publicacion_id: int) -> None:
        ...
