import pytest

from backend_estudiantil.domain.models.user import User
from backend_estudiantil.domain.services.user_service import UserService
from backend_estudiantil.schemas.user import UserCreate, UserUpdate

pytestmark = pytest.mark.unit

class InMemoryUserRepository:
    """Repositorio en memoria para pruebas unitarias del servicio de usuarios."""
    def __init__(self):
        self.store = {}
        self._next_id = 1

    async def get_by_id(self, user_id):
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            uid = user_id
        return self.store.get(uid)

    async def get_by_email(self, email: str):
        return next((u for u in self.store.values() if u.correo_institucional == email), None)

    async def create(self, user: User):
        # Simular auto-incremento de la BD
        user.id = self._next_id
        self._next_id += 1
        self.store[user.id] = user
        return user

    async def update(self, user: User):
        self.store[user.id] = user
        return user

    async def delete(self, user_id):
        try:
            uid = int(user_id)
        except (ValueError, TypeError):
            uid = user_id
        self.store.pop(uid, None)

    async def list(self, skip: int = 0, limit: int = 100):
        return list(self.store.values())[skip:skip+limit]

@pytest.fixture
def repo():
    return InMemoryUserRepository()

@pytest.fixture
def service(repo):
    return UserService(repo)

@pytest.mark.asyncio
async def test_create_user(service):
    payload = UserCreate(email="test@example.com", password="secret123", name="Tester")
    user = await service.create_user(payload)
    assert user.id is not None
    assert user.correo_institucional == payload.email
    assert user.name == payload.name
    # La contraseña debe almacenarse hasheada
    assert user.password_hash != payload.password

@pytest.mark.asyncio
async def test_get_user(service):
    payload = UserCreate(email="bob@example.com", password="password123", name="Bob")
    created = await service.create_user(payload)
    fetched = await service.get_user(created.id)
    assert fetched.id == created.id
    assert fetched.correo_institucional == created.correo_institucional

@pytest.mark.asyncio
async def test_update_user(service):
    payload = UserCreate(email="alice@example.com", password="password123", name="Alice")
    user = await service.create_user(payload)
    update_payload = UserUpdate(name="Alice Updated")
    updated = await service.update_user(user.id, update_payload)
    assert updated.name == "Alice Updated"

@pytest.mark.asyncio
async def test_delete_user(service):
    payload = UserCreate(email="del@example.com", password="password123", name="Del")
    user = await service.create_user(payload)
    await service.delete_user(user.id)
    with pytest.raises(ValueError):
        await service.get_user(user.id)
