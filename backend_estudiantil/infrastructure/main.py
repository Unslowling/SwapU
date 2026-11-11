import asyncio
from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select, text

from backend_estudiantil.adapters.db import (
    CategoriaORM,
    get_engine,
    get_session_factory,
    verificar_conexion_db,
)
from backend_estudiantil.config.settings import settings
from backend_estudiantil.infrastructure.api.admin_router import router as admin_router
from backend_estudiantil.infrastructure.api.auth_router import router as auth_router
from backend_estudiantil.infrastructure.api.calificaciones_router import (
    router as calificaciones_router,
)
from backend_estudiantil.infrastructure.api.catalogo_router import (
    router as catalogo_router,
)
from backend_estudiantil.infrastructure.api.chat_router import router as chat_router
from backend_estudiantil.infrastructure.api.facebook_oauth_router import (
    router as facebook_oauth_router,
)
from backend_estudiantil.infrastructure.api.google_oauth_router import (
    router as google_oauth_router,
)
from backend_estudiantil.infrastructure.api.matches_router import (
    router as matches_router,
)
from backend_estudiantil.infrastructure.api.moderacion_router import (
    router as moderacion_router,
)
from backend_estudiantil.infrastructure.api.publicaciones_router import (
    router as publicaciones_router,
)
from backend_estudiantil.infrastructure.api.tickets_router import (
    router as tickets_router,
)
from backend_estudiantil.infrastructure.api.trueques_router import (
    router as trueques_router,
)
from backend_estudiantil.infrastructure.api.users_router import router as users_router
from backend_estudiantil.infrastructure.api.verificaciones_router import (
    router as verificaciones_router,
)
from backend_estudiantil.infrastructure.audit_middleware import AuditMiddleware
from backend_estudiantil.infrastructure.logging import configure_logging
from backend_estudiantil.infrastructure.security_headers_middleware import (
    SecurityHeadersMiddleware,
)
from backend_estudiantil.infrastructure.redis_circuit_breaker import (
    slowapi_redis_circuit_breaker,
)
from backend_estudiantil.infrastructure.verificacion_ia import precalentar

configure_logging()


def _init_limiter() -> Limiter:
    """Configura el almacenamiento de Slowapi en Redis con timeouts cortos (<1s) y respaldo transparente en memoria."""
    storage_uri = "memory://"
    storage_options = {"socket_connect_timeout": 0.5, "socket_timeout": 0.5}
    if getattr(settings, "REDIS_URL", None) and not slowapi_redis_circuit_breaker.is_open:
        try:
            import redis

            r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5)
            r.ping()
            storage_uri = settings.REDIS_URL
            slowapi_redis_circuit_breaker.record_success()
        except Exception as e:
            slowapi_redis_circuit_breaker.record_failure(e)
            storage_uri = "memory://"
    return Limiter(
        key_func=get_remote_address,
        default_limits=["100/min"],
        storage_uri=storage_uri,
        storage_options=storage_options,
        in_memory_fallback_enabled=True,
        swallow_errors=True,
    )


limiter = _init_limiter()

CATEGORIAS_INICIALES = (
    (1, "Ingeniería y Tecnología"),
    (2, "Medicina y Salud"),
    (3, "Ciencias Básicas"),
    (4, "Derecho y Políticas"),
    (5, "Economía y Negocios"),
    (6, "Humanidades"),
)


async def inicializar_categorias():
    """Inicializa las categorías base únicamente si faltan registros, evitando escrituras innecesarias."""
    factory = get_session_factory()
    insertadas = 0
    async with factory() as session:
        for categoria_id, nombre in CATEGORIAS_INICIALES:
            categoria = await session.get(CategoriaORM, categoria_id)
            if categoria is None:
                existente = await session.execute(
                    select(CategoriaORM).where(CategoriaORM.nombre == nombre)
                )
                if existente.scalar_one_or_none() is None:
                    session.add(CategoriaORM(id=categoria_id, nombre=nombre))
                    insertadas += 1
        if insertadas > 0:
            await session.commit()

    if insertadas > 0 and get_engine().dialect.name == "postgresql":
        async with get_engine().begin() as connection:
            await connection.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('categorias', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM categorias), 1))"
                )
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestor de ciclo de vida moderno de FastAPI (Lifespan) sin alteración automática de esquema."""
    engine = get_engine()
    # Solo inicializar categorías automáticamente en bases SQLite efímeras de prueba si las tablas existen
    if engine.dialect.name == "sqlite":
        try:
            await inicializar_categorias()
        except Exception as _exc:
            logging.getLogger(__name__).debug("Omitiendo inicialización de categorías en SQLite: %s", _exc)
    # Precalentar modelos de IA desde el lifespan
    try:
        asyncio.create_task(asyncio.to_thread(precalentar))
    except Exception as _e:
        logging.getLogger(__name__).warning("No se pudo ejecutar precalentar IA: %s", _e)
    try:
        yield
    finally:
        await get_engine().dispose()


app = FastAPI(
    title="Plataforma de Trueque Estudiantil",
    description="API Backend para intercambio de artículos y libros entre estudiantes universitarios.",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter

# Configuración de CORS segura (Nunca '*' con credenciales)
raw_cors = settings.get_cors_origins()
if "*" in raw_cors:
    cors_origins = ["*"]
    cors_credentials = False
else:
    cors_origins = [o for o in raw_cors if o != "*"]
    if not cors_origins:
        cors_origins = ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]
    cors_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=cors_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Middleware de Cabeceras de Seguridad (X-Content-Type-Options, X-Frame-Options, CSP, HSTS)
app.add_middleware(SecurityHeadersMiddleware)

# Capa de Captura: Middleware de Auditoría bajo la Regla de las 5W
app.add_middleware(AuditMiddleware)


# Manejador de error para Rate Limit
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})


# Inclusión de Routers (Auth, Usuarios, Admin, Google OAuth)
app.include_router(auth_router)
app.include_router(google_oauth_router)
app.include_router(facebook_oauth_router)
app.include_router(users_router)
app.include_router(admin_router)
# Routers del dominio principal de trueque
app.include_router(publicaciones_router)
app.include_router(matches_router)
app.include_router(trueques_router)
app.include_router(calificaciones_router)
app.include_router(chat_router)
app.include_router(verificaciones_router)
app.include_router(tickets_router)
app.include_router(moderacion_router)
app.include_router(catalogo_router)

# Compatibilidad con FastAPI 0.140+ / Starlette 1.7+ (_IncludedRouter sin atributo 'path')
try:
    import prometheus_fastapi_instrumentator.routing as pfi_routing

    _orig_get_route_name = pfi_routing._get_route_name

    def _safe_get_route_name(scope, routes, *args, **kwargs):
        safe_routes = [r for r in routes if hasattr(r, "path")]
        return _orig_get_route_name(scope, safe_routes)

    pfi_routing._get_route_name = _safe_get_route_name
except Exception:
    pass

# Instrumentación de métricas con Prometheus
Instrumentator().instrument(app).expose(app)


# Health checks
@app.get("/health", tags=["health"])
async def health_check():
    """Verificación básica de salud de la API."""
    return {"status": "ok", "app": "Plataforma de Trueque Estudiantil"}


@app.get("/health/db", tags=["health"])
async def health_db_check():
    """Verificación directa de la conexión activa a la base de datos."""
    resultado = await verificar_conexion_db()
    return {"database": resultado}


# Montaje de frontend estático si existe
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
