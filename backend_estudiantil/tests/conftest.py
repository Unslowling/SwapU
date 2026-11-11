import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from backend_estudiantil.config.settings import settings

# Forzar una URL SQLite segura desde la carga de conftest para impedir
# que cualquier importación o tarea en segundo plano utilice PostgreSQL de .env
_SAFE_FALLBACK_DB_URL = "sqlite+aiosqlite:///:memory:"
settings.DATABASE_URL = _SAFE_FALLBACK_DB_URL

from backend_estudiantil.adapters.db import (  # noqa: E402
    Base,
    CategoriaORM,
    OrganizacionORM,
    TruequeORM,
    UserORM,
    get_engine,
    get_session_factory,
)
from backend_estudiantil.infrastructure.main import (  # noqa: E402
    CATEGORIAS_INICIALES,
    app,
)

# Asegurar que el motor global apunte inicialmente a SQLite
get_engine(_SAFE_FALLBACK_DB_URL)


@pytest.fixture(scope="function", autouse=True)
def isolated_db(request, tmp_path):
    """Inicializa automáticamente una base de datos SQLite temporal aislada para cada prueba."""
    original_storage = settings.BOOK_VERIFICATION_STORAGE_PATH
    storage_dir = tmp_path / "private-photos"
    storage_dir.mkdir(parents=True, exist_ok=True)
    settings.BOOK_VERIFICATION_STORAGE_PATH = str(storage_dir)

    # Si es una prueba unitaria pura, mantener SQLite en memoria sin crear archivo en disco
    if request.node.get_closest_marker("unit") is not None and "client" not in request.fixturenames:
        settings.DATABASE_URL = _SAFE_FALLBACK_DB_URL
        engine = get_engine(_SAFE_FALLBACK_DB_URL)
        assert engine.dialect.name == "sqlite"
        yield _SAFE_FALLBACK_DB_URL
        settings.DATABASE_URL = _SAFE_FALLBACK_DB_URL
        settings.BOOK_VERIFICATION_STORAGE_PATH = original_storage
        return

    db_file = tmp_path / f"test_{uuid.uuid4().hex[:8]}.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"

    assert "postgresql" not in test_db_url.lower(), (
        "BLOQUEO DE SEGURIDAD: Las pruebas no pueden utilizar PostgreSQL."
    )

    settings.DATABASE_URL = test_db_url
    engine = get_engine(test_db_url)
    assert engine.dialect.name == "sqlite", (
        f"BLOQUEO DE SEGURIDAD: Dialecto inesperado en pruebas: {engine.dialect.name}"
    )

    from backend_estudiantil.infrastructure.api import tickets_router
    tickets_router.service.session_factory = get_session_factory()

    async def init_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            for categoria_id, nombre in CATEGORIAS_INICIALES:
                await conn.execute(
                    CategoriaORM.__table__.insert().values(id=categoria_id, nombre=nombre)
                )
            await conn.execute(
                OrganizacionORM.__table__.insert().values(
                    nombre="Universidad de San Buenaventura Medellín",
                    tipo="universidad",
                    dominios=["usbmed.edu.co", "tau.usbmed.edu.co"],
                    politicas={"max_publicaciones": 10},
                )
            )
        await engine.dispose()

    asyncio.run(init_tables())

    yield test_db_url

    async def cleanup():
        active_engine = get_engine()
        await active_engine.dispose()
        await engine.dispose()

    asyncio.run(cleanup())
    try:
        db_file.unlink(missing_ok=True)
    except OSError:
        pass
    settings.DATABASE_URL = _SAFE_FALLBACK_DB_URL
    settings.BOOK_VERIFICATION_STORAGE_PATH = original_storage
    get_engine(_SAFE_FALLBACK_DB_URL)


@pytest.fixture(scope="function")
def client(isolated_db):
    """Cliente de pruebas FastAPI con base de datos aislada."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_chat_manager():
    """Limpia el gestor de WebSockets entre pruebas para evitar conexiones residuales."""
    from backend_estudiantil.infrastructure.api.chat_router import manager
    manager.active_connections.clear()
    manager._subscriptions.clear()
    yield
    manager.active_connections.clear()
    manager._subscriptions.clear()


def _crear_usuario(
    client: TestClient,
    email: str,
    name: str = "Test User",
    role: str = "usuario",
    verificado: bool = False,
    universidad: str = "Universidad de San Buenaventura Medellín",
    facultad: str = "Ingeniería",
    semestre: int = 5,
):
    """Helper para registrar y obtener token de usuario en la base de datos de test."""
    reg = client.post(
        "/auth/register",
        json={"name": name, "email": email, "password": "password123", "role": role},
    )
    assert reg.status_code == 201, reg.text
    user_id = reg.json().get("id")

    # Si se pide verificado o rol especial, actualizar en la base de datos
    factory = get_session_factory()

    async def update_user():
        from sqlalchemy.future import select
        async with factory() as session:
            res = await session.execute(select(UserORM).where(UserORM.correo_institucional == email))
            u = res.scalar_one_or_none()
            if u:
                u.verificado_comunidad = verificado
                u.rol = role
                u.universidad = universidad
                u.facultad = facultad
                u.semestre = semestre
                await session.commit()
                return u.id
        return user_id

    real_id = asyncio.run(update_user()) or user_id

    login = client.post(
        "/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "id": real_id,
        "email": email,
        "name": name,
        "role": role,
        "verificado": verificado,
        "token": token,
        "headers": headers,
    }


@pytest.fixture
def usuario_sin_verificar(client):
    """Usuario estudiante activo pero sin verificar comunidad institucional."""
    email = f"unverified_{uuid.uuid4().hex[:6]}@gmail.com"
    return _crear_usuario(client, email=email, name="Estudiante No Verificado", role="usuario", verificado=False)


@pytest.fixture
def usuario_verificado(client):
    """Usuario estudiante verificado perteneciente a una institución."""
    email = f"verified_{uuid.uuid4().hex[:6]}@tau.usbmed.edu.co"
    return _crear_usuario(client, email=email, name="Estudiante Verificado", role="usuario", verificado=True)


@pytest.fixture
def usuario_moderador(client):
    """Usuario con rol moderador."""
    email = f"mod_{uuid.uuid4().hex[:6]}@usbmed.edu.co"
    return _crear_usuario(client, email=email, name="Moderador General", role="moderador", verificado=True)


@pytest.fixture
def usuario_admin(client):
    """Usuario con rol administrador."""
    email = f"admin_{uuid.uuid4().hex[:6]}@admin.usbmed.edu.co"
    return _crear_usuario(client, email=email, name="Administrador Sistema", role="administrador", verificado=True)


@pytest.fixture
def publicacion_factory(client):
    """Factoría para crear publicaciones asociadas a usuarios en la base de datos."""
    def _crear_pub(user_headers: dict, titulo: str = "Cálculo Diferencial", libro_buscado: str = "Álgebra Lineal", isbn: str = "9789587781234"):
        resp = client.post(
            "/publicaciones/",
            headers=user_headers,
            json={
                "titulo": titulo,
                "autor": "Stewart",
                "isbn": isbn,
                "edicion": "8va",
                "estado_libro": "bueno",
                "descripcion": "Libro en excelente estado de estudio",
                "libro_buscado": libro_buscado,
                "tipo_transaccion": "trueque",
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _crear_pub


@pytest.fixture
def trueque_factory(client):
    """Factoría para crear un trueque confirmado entre dos usuarios."""
    def _crear_trueque(user1: dict, user2: dict):
        factory = get_session_factory()

        async def _insert_trueque():
            async with factory() as session:
                t = TruequeORM(
                    usuario_propone_id=user1["id"],
                    usuario_recibe_id=user2["id"],
                    estado="propuesto",
                )
                session.add(t)
                await session.commit()
                await session.refresh(t)
                return t.id

        trueque_id = asyncio.run(_insert_trueque())
        return trueque_id

    return _crear_trueque


@pytest.fixture(autouse=True)
def _confirmacion_correo_desactivada_en_pruebas_heredadas(monkeypatch):
    """Las pruebas heredadas registran correos institucionales sin confirmarlos.
    La regla de confirmación se prueba explícitamente en test_confirmacion_correo_obligatoria.py.
    """
    monkeypatch.setattr(settings, "CONFIRMACION_CORREO_OBLIGATORIA", False)
