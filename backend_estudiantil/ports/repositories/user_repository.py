from abc import ABC, abstractmethod

from backend_estudiantil.domain.models.user import User


class UserRepository(ABC):
    """Puerto (interfaz) para las operaciones de persistencia del usuario."""

    @abstractmethod
    async def get_by_id(self, user_id: str) -> User | None:
        """Obtiene un usuario por su ID."""
        ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None:
        """Obtiene un usuario por su correo electrónico."""
        ...

    @abstractmethod
    async def create(self, user: User) -> User:
        """Persiste un nuevo usuario."""
        ...

    @abstractmethod
    async def update(self, user: User) -> User:
        """Actualiza la información de un usuario existente."""
        ...

    @abstractmethod
    async def delete(self, user_id: str) -> None:
        """Elimina un usuario por su ID."""
        ...

    @abstractmethod
    async def list(self, skip: int = 0, limit: int = 100) -> list[User]:
        """Lista usuarios con paginación."""
        ...
