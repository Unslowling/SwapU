from collections.abc import AsyncGenerator

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

from backend_estudiantil.config.settings import settings

Base = declarative_base()

def _build_engine_kwargs(target_url: str) -> dict:
    kwargs = {"echo": False, "future": True}
    if "sqlite" not in target_url:
        kwargs.update({
            "pool_size": 15,
            "max_overflow": 15,
            "pool_recycle": 300,
            "pool_pre_ping": True,
            "pool_timeout": 30,
        })
    return kwargs

_SSLMODES_ASYNCPG = {"require", "verify-ca", "verify-full", "prefer", "allow", "disable"}


def _normalizar_url(url: str) -> tuple[str, dict]:
    """Adapta URLs de proveedores (postgres://, postgresql://, ?sslmode=require) al driver asyncpg.

    asyncpg no acepta 'sslmode' ni 'channel_binding' en la URL: se traducen a connect_args.
    """
    connect_args: dict = {}
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+asyncpg://") and "?" in url:
        base, query = url.split("?", 1)
        restantes = []
        for parametro in filter(None, query.split("&")):
            clave, _, valor = parametro.partition("=")
            if clave == "sslmode":
                if valor in _SSLMODES_ASYNCPG and valor != "disable":
                    connect_args["ssl"] = valor
            elif clave == "channel_binding":
                continue
            else:
                restantes.append(parametro)
        url = base + ("?" + "&".join(restantes) if restantes else "")
    return url, connect_args


def _crear_motor(url: str):
    url_real, connect_args = _normalizar_url(url)
    kwargs = _build_engine_kwargs(url_real)
    if connect_args:
        kwargs["connect_args"] = connect_args
    return create_async_engine(url_real, **kwargs)


# Motor y fábrica de sesiones global
_url_motor = settings.DATABASE_URL
engine = _crear_motor(_url_motor)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

def get_engine(url: str | None = None):
    """Retorna o regenera el motor y la fábrica de sesiones si cambió la URL.

    Se compara contra la URL configurada guardada (no contra str(engine.url), que oculta la
    contraseña y provocaría crear un pool nuevo en cada llamada con PostgreSQL).
    """
    global engine, AsyncSessionLocal, _url_motor
    target_url = url or settings.DATABASE_URL
    if target_url != _url_motor:
        engine = _crear_motor(target_url)
        _url_motor = target_url
        AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    return engine

def get_session_factory():
    """Retorna la fábrica de sesiones activa correspondiente al motor actual."""
    get_engine()
    return AsyncSessionLocal

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Generador de sesión de base de datos para inyección de dependencias en FastAPI."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def verificar_conexion_db() -> dict:
    """Verifica si la conexión activa a la base de datos responde exitosamente."""
    try:
        active_engine = get_engine()
        async with active_engine.connect() as conn:
            await conn.execute(sa.text("SELECT 1"))
        return {
            "status": "conectado",
            "dialecto": active_engine.dialect.name,
            "url": f"{active_engine.url.drivername}://{active_engine.url.host or 'localhost'}/{active_engine.url.database or ''}",
        }
    except Exception as exc:
        return {"status": "error", "detalle": str(exc)}

# ==============================================================================
# MODELOS ORM DE LA PLATAFORMA DE TRUEQUE ESTUDIANTIL (EN ESPAÑOL)
tipo_usuario_enum = sa.Enum("estudiante", "docente", "administrativo", name="tipo_usuario_enum")
rol_enum = sa.Enum("usuario", "administrador", "moderador", name="rol_enum")
estado_cuenta_enum = sa.Enum("pendiente", "activo", "bloqueado", "suspendido", name="estado_cuenta_enum")
estado_publicacion_enum = sa.Enum("activa", "inactiva", "eliminada", name="estado_publicacion_enum")
tipo_match_enum = sa.Enum("exacta", "similar", name="tipo_match_enum")
estado_trueque_enum = sa.Enum("propuesto", "confirmado", "rechazado", "completado", name="estado_trueque_enum")


class OrganizacionORM(Base):
    """Tabla 'organizaciones' académicas, universitarias y bibliotecas."""
    __tablename__ = "organizaciones"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    nombre = sa.Column(sa.String(255), unique=True, nullable=False)
    tipo = sa.Column(sa.String(50), nullable=False, default="universidad")  # universidad, biblioteca, otra
    dominios = sa.Column(sa.JSON, nullable=False, default=list)             # ["usbmed.edu.co"]
    politicas = sa.Column(sa.JSON, nullable=False, default=dict)            # configuraciones específicas
    creado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    usuarios = relationship("UserORM", back_populates="organizacion", foreign_keys="UserORM.organizacion_id")
    publicaciones = relationship("PublicacionORM", back_populates="organizacion", foreign_keys="PublicacionORM.organizacion_id")


class UserORM(Base):
    """Tabla 'usuarios' en PostgreSQL."""
    __tablename__ = "usuarios"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    nombre = sa.Column(sa.String, nullable=False)
    apellido = sa.Column(sa.String, nullable=True)
    correo_institucional = sa.Column(sa.String, unique=True, nullable=False, index=True)
    password_hash = sa.Column(sa.String, nullable=False)
    tipo_usuario = sa.Column(tipo_usuario_enum, default="estudiante", nullable=False)
    programa_area = sa.Column(sa.String, nullable=True)
    facultad = sa.Column(sa.String(150), nullable=True)
    rol = sa.Column(rol_enum, default="usuario", nullable=False)
    verificado_comunidad = sa.Column(sa.Boolean, default=False, nullable=False)
    estado_cuenta = sa.Column(estado_cuenta_enum, default="activo", nullable=False)
    fecha_registro = sa.Column(sa.DateTime, default=sa.func.now(), nullable=False)
    # Campos de perfil extendido
    telefono = sa.Column(sa.String(30), nullable=True)
    universidad = sa.Column(sa.String(150), nullable=True)
    semestre = sa.Column(sa.Integer, nullable=True)
    foto_url = sa.Column(sa.String(512), nullable=True)
    carnet_path = sa.Column(sa.String(512), nullable=True)
    carnet_estado = sa.Column(sa.String(50), nullable=True, default=None)
    carnet_rechazo_motivo = sa.Column(sa.String(500), nullable=True, default=None)
    perfil_completo = sa.Column(sa.Boolean, default=False, nullable=False)
    codigo_confirmacion = sa.Column(sa.String(64), nullable=True)
    codigo_confirmacion_expira = sa.Column(sa.DateTime, nullable=True)
    codigo_confirmacion_intentos = sa.Column(sa.Integer, default=0, nullable=False, server_default="0")
    correo_confirmado = sa.Column(sa.Boolean, default=False, nullable=False, server_default=sa.text("false"))
    # Organizacion y suspension
    organizacion_id = sa.Column(sa.Integer, sa.ForeignKey("organizaciones.id"), nullable=True)
    fin_suspension = sa.Column(sa.DateTime(timezone=True), nullable=True)
    motivo_sancion = sa.Column(sa.String(500), nullable=True)

    # Relaciones
    organizacion = relationship("OrganizacionORM", back_populates="usuarios", foreign_keys=[organizacion_id])
    publicaciones = relationship("PublicacionORM", back_populates="usuario", cascade="all, delete-orphan", foreign_keys="PublicacionORM.usuario_id")


class CategoriaORM(Base):
    """Tabla 'categorias' de libros y materiales académicos."""
    __tablename__ = "categorias"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    nombre = sa.Column(sa.String, nullable=False, unique=True)

    publicaciones = relationship("PublicacionORM", back_populates="categoria")


class PublicacionORM(Base):
    """Tabla 'publicaciones' de artículos ofertados y buscados."""
    __tablename__ = "publicaciones"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    usuario_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False, index=True)
    titulo = sa.Column(sa.String, nullable=False, index=True)
    autor = sa.Column(sa.String, nullable=True)
    isbn = sa.Column(sa.String, nullable=True)
    edicion = sa.Column(sa.String, nullable=True)
    categoria_id = sa.Column(sa.Integer, sa.ForeignKey("categorias.id"), nullable=True)
    estado_libro = sa.Column(sa.String, nullable=True)
    descripcion = sa.Column(sa.Text, nullable=True)
    libro_buscado = sa.Column(sa.String, nullable=True, index=True)
    estado_publicacion = sa.Column(estado_publicacion_enum, default="activa", nullable=False)
    fecha_publicacion = sa.Column(sa.DateTime, default=sa.func.now(), nullable=False)
    tipo_transaccion = sa.Column(sa.String(20), default="trueque", nullable=False, server_default="trueque")
    fecha_devolucion = sa.Column(sa.DateTime(timezone=True), nullable=True)
    organizacion_id = sa.Column(sa.Integer, sa.ForeignKey("organizaciones.id"), nullable=True)

    # Relaciones
    usuario = relationship("UserORM", back_populates="publicaciones", foreign_keys=[usuario_id])
    categoria = relationship("CategoriaORM", back_populates="publicaciones")
    organizacion = relationship("OrganizacionORM", back_populates="publicaciones", foreign_keys=[organizacion_id])


class VerificacionPublicacionORM(Base):
    """Desafío visual y evidencia privada para revisar una publicación de libro."""

    __tablename__ = "verificaciones_publicacion"
    __table_args__ = (
        sa.Index("ix_verificaciones_publicacion_estado", "estado"),
        sa.Index("ix_verificaciones_publicacion_usuario", "usuario_id"),
    )

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    publicacion_id = sa.Column(
        sa.Integer, sa.ForeignKey("publicaciones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    usuario_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    codigo_hash = sa.Column(sa.String(64), nullable=False)
    estado = sa.Column(sa.String(24), nullable=False, default="desafio")
    intentos_codigo = sa.Column(sa.SmallInteger, nullable=False, default=0)
    portada_path = sa.Column(sa.String(512), nullable=True)
    pagina_isbn_path = sa.Column(sa.String(512), nullable=True)
    portada_sha256 = sa.Column(sa.String(64), nullable=True)
    pagina_isbn_sha256 = sa.Column(sa.String(64), nullable=True)
    creado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    vence_en = sa.Column(sa.DateTime(timezone=True), nullable=False)
    enviado_en = sa.Column(sa.DateTime(timezone=True), nullable=True)
    revisado_por_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=True)
    revisado_en = sa.Column(sa.DateTime(timezone=True), nullable=True)
    nota_revision = sa.Column(sa.String(1000), nullable=True)


class MatchORM(Base):
    """Tabla 'matches' generados por el motor de coincidencias."""
    __tablename__ = "matches"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    publicacion_origen_id = sa.Column(sa.Integer, sa.ForeignKey("publicaciones.id"), nullable=False)
    publicacion_destino_id = sa.Column(sa.Integer, sa.ForeignKey("publicaciones.id"), nullable=False)
    tipo_match = sa.Column(tipo_match_enum, default="exacta", nullable=False)
    puntuacion = sa.Column(sa.Numeric(5, 2), default=100.0, nullable=False)
    fecha_creacion = sa.Column(sa.DateTime, default=sa.func.now(), nullable=False)

    # Relaciones
    publicacion_origen = relationship("PublicacionORM", foreign_keys=[publicacion_origen_id])
    publicacion_destino = relationship("PublicacionORM", foreign_keys=[publicacion_destino_id])


class TruequeORM(Base):
    """Tabla 'trueques' que representa el estado del intercambio entre dos usuarios."""
    __tablename__ = "trueques"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    match_id = sa.Column(sa.Integer, sa.ForeignKey("matches.id"), nullable=True)
    usuario_propone_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    usuario_recibe_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    estado = sa.Column(estado_trueque_enum, default="propuesto", nullable=False)
    fecha_propuesta = sa.Column(sa.DateTime, default=sa.func.now(), nullable=False)
    fecha_confirmacion = sa.Column(sa.DateTime, nullable=True)
    fecha_completado = sa.Column(sa.DateTime, nullable=True)

    # Relaciones
    usuario_propone = relationship("UserORM", foreign_keys=[usuario_propone_id])
    usuario_recibe = relationship("UserORM", foreign_keys=[usuario_recibe_id])
    match = relationship("MatchORM")
    calificaciones = relationship("CalificacionORM", back_populates="trueque")


class CalificacionORM(Base):
    """Tabla 'calificaciones' post-trueque para calcular reputación."""
    __tablename__ = "calificaciones"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    trueque_id = sa.Column(sa.Integer, sa.ForeignKey("trueques.id"), nullable=False)
    usuario_califica_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    usuario_calificado_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    estrellas = sa.Column(sa.SmallInteger, nullable=False)
    resena = sa.Column(sa.Text, nullable=True)
    fecha_calificacion = sa.Column(sa.DateTime, default=sa.func.now(), nullable=False)

    # Relaciones
    trueque = relationship("TruequeORM", back_populates="calificaciones")
    usuario_califica = relationship("UserORM", foreign_keys=[usuario_califica_id])
    usuario_calificado = relationship("UserORM", foreign_keys=[usuario_calificado_id])


class MensajeORM(Base):
    """Tabla 'mensajes' de chat asociado al intercambio/trueque."""
    __tablename__ = "mensajes"

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    trueque_id = sa.Column(sa.Integer, sa.ForeignKey("trueques.id"), nullable=False, index=True)
    remitente_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    contenido = sa.Column(sa.Text, nullable=False)
    fecha_envio = sa.Column(sa.DateTime, default=sa.func.now(), nullable=False)

    trueque = relationship("TruequeORM")
    remitente = relationship("UserORM", foreign_keys=[remitente_id])


class AuditoriaLogORM(Base):
    """Tabla 'auditorias' para trazabilidad y seguridad bajo la regla de las 5W.
    
    Regla de las 5W:
      - Who (Quién): usuario_id, usuario_email, usuario_rol, ip_origen, user_agent
      - What (Qué): accion, recurso
      - When (Cuándo): fecha_hora (UTC)
      - Where (Dónde): metodo_http, endpoint
      - Why (Por qué): estado_http, exito, detalle, duracion_ms
    """
    __tablename__ = "auditorias"
    __table_args__ = (
        sa.Index("ix_auditorias_fecha_hora", "fecha_hora"),
        sa.Index("ix_auditorias_usuario_id", "usuario_id"),
        sa.Index("ix_auditorias_accion", "accion"),
        sa.Index("ix_auditorias_estado_http", "estado_http"),
    )

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True)
    # Who (Quién)
    usuario_id = sa.Column(sa.Integer, nullable=True)
    usuario_email = sa.Column(sa.String(150), nullable=True)
    usuario_rol = sa.Column(sa.String(50), nullable=True)
    ip_origen = sa.Column(sa.String(64), nullable=False, default="127.0.0.1")
    user_agent = sa.Column(sa.String(256), nullable=True)
    # What (Qué)
    accion = sa.Column(sa.String(100), nullable=False)
    recurso = sa.Column(sa.String(100), nullable=True)
    # When (Cuándo)
    fecha_hora = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    # Where (Dónde)
    metodo_http = sa.Column(sa.String(10), nullable=False)
    endpoint = sa.Column(sa.String(255), nullable=False)
    # Why (Por qué)
    estado_http = sa.Column(sa.Integer, nullable=False)
    exito = sa.Column(sa.Boolean, default=True, nullable=False)
    detalle = sa.Column(sa.Text, nullable=True)
    duracion_ms = sa.Column(sa.Float, nullable=True)


class ReporteORM(Base):
    """Tabla 'reportes' para moderación de contenido y comportamiento."""
    __tablename__ = "reportes"
    __table_args__ = (
        sa.Index("ix_reportes_estado", "estado"),
        sa.Index("ix_reportes_tipo_objetivo", "tipo_objetivo"),
    )

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    reportante_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    objetivo_id = sa.Column(sa.Integer, nullable=False)
    tipo_objetivo = sa.Column(sa.String(50), nullable=False)  # "calificacion", "publicacion", "usuario", "mensaje"
    motivo = sa.Column(sa.Text, nullable=False)
    estado = sa.Column(sa.String(50), nullable=False, default="pendiente", server_default="pendiente")  # pendiente, revisado, descartado, sancionado
    creado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    revisado_por_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=True)
    revisado_en = sa.Column(sa.DateTime(timezone=True), nullable=True)
    resolucion = sa.Column(sa.Text, nullable=True)

    reportante = relationship("UserORM", foreign_keys=[reportante_id])
    revisado_por = relationship("UserORM", foreign_keys=[revisado_por_id])


class AdvertenciaORM(Base):
    """Tabla 'advertencias' aplicadas a usuarios por moderadores o de forma automática."""
    __tablename__ = "advertencias"
    __table_args__ = (
        sa.Index("ix_advertencias_usuario_id", "usuario_id"),
        sa.Index("ix_advertencias_creado_en", "creado_en"),
    )

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    usuario_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    moderador_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=True)
    motivo = sa.Column(sa.Text, nullable=False)
    origen = sa.Column(sa.String(50), default="manual", nullable=False)  # manual, automatico
    creado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    usuario = relationship("UserORM", foreign_keys=[usuario_id])
    moderador = relationship("UserORM", foreign_keys=[moderador_id])


class SancionORM(Base):
    """Tabla 'sanciones' aplicadas a usuarios: suspensiones temporales y bloqueos definitivos."""
    __tablename__ = "sanciones"
    __table_args__ = (
        sa.Index("ix_sanciones_usuario_id", "usuario_id"),
        sa.Index("ix_sanciones_estado", "estado"),
    )

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    usuario_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    moderador_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=True)
    tipo = sa.Column(sa.String(50), nullable=False)  # advertencia, suspension_7, suspension_30, bloqueo
    motivo = sa.Column(sa.Text, nullable=False)
    fecha_inicio = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    fecha_fin = sa.Column(sa.DateTime(timezone=True), nullable=True)
    estado = sa.Column(sa.String(50), nullable=False, default="activa", server_default="activa")  # activa, cumplida, levantada
    creado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    levantada_en = sa.Column(sa.DateTime(timezone=True), nullable=True)
    levantada_por_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=True)
    motivo_levantamiento = sa.Column(sa.Text, nullable=True)

    usuario = relationship("UserORM", foreign_keys=[usuario_id])
    moderador = relationship("UserORM", foreign_keys=[moderador_id])
    levantada_por = relationship("UserORM", foreign_keys=[levantada_por_id])
    apelacion = relationship("ApelacionORM", uselist=False, back_populates="sancion")


class ApelacionORM(Base):
    """Tabla 'apelaciones' enviadas por usuarios frente a una sanción (máximo 1 por sanción)."""
    __tablename__ = "apelaciones"
    __table_args__ = (
        sa.Index("ix_apelaciones_estado", "estado"),
        sa.Index("ix_apelaciones_usuario_id", "usuario_id"),
    )

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    sancion_id = sa.Column(sa.Integer, sa.ForeignKey("sanciones.id"), unique=True, nullable=False)
    usuario_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=False)
    motivo = sa.Column(sa.Text, nullable=False)
    estado = sa.Column(sa.String(50), nullable=False, default="pendiente", server_default="pendiente")  # pendiente, aprobada, rechazada
    moderador_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id"), nullable=True)
    respuesta = sa.Column(sa.Text, nullable=True)
    creado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    resuelto_en = sa.Column(sa.DateTime(timezone=True), nullable=True)

    sancion = relationship("SancionORM", back_populates="apelacion")
    usuario = relationship("UserORM", foreign_keys=[usuario_id])
    moderador = relationship("UserORM", foreign_keys=[moderador_id])



class TicketORM(Base):
    """Tabla 'tickets_revision' para la comunicación y seguimiento de libros en revisión."""
    __tablename__ = "tickets_revision"
    __table_args__ = (
        sa.Index("ix_tickets_revision_publicacion_id", "publicacion_id"),
        sa.Index("ix_tickets_revision_usuario_id", "usuario_id"),
        sa.Index("ix_tickets_revision_moderador_id", "moderador_id"),
        sa.Index("ix_tickets_revision_estado", "estado"),
    )

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    publicacion_id = sa.Column(sa.Integer, sa.ForeignKey("publicaciones.id", ondelete="CASCADE"), nullable=False)
    usuario_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    moderador_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    asunto = sa.Column(sa.String(200), nullable=False)
    estado = sa.Column(sa.String(50), nullable=False, default="abierto", server_default="abierto")
    prioridad = sa.Column(sa.String(20), nullable=False, default="media", server_default="media")
    creado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    actualizado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    # Relaciones
    publicacion = relationship("PublicacionORM")
    usuario = relationship("UserORM", foreign_keys=[usuario_id])
    moderador = relationship("UserORM", foreign_keys=[moderador_id])
    mensajes = relationship("TicketMensajeORM", back_populates="ticket", cascade="all, delete-orphan", order_by="TicketMensajeORM.id.asc()")


class TicketMensajeORM(Base):
    """Tabla 'ticket_mensajes' que almacena la conversación dentro de un ticket de revisión."""
    __tablename__ = "ticket_mensajes"
    __table_args__ = (
        sa.Index("ix_ticket_mensajes_ticket_id", "ticket_id"),
        sa.Index("ix_ticket_mensajes_remitente_id", "remitente_id"),
    )

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, index=True)
    ticket_id = sa.Column(sa.Integer, sa.ForeignKey("tickets_revision.id", ondelete="CASCADE"), nullable=False)
    remitente_id = sa.Column(sa.Integer, sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    contenido = sa.Column(sa.Text, nullable=False)
    es_del_sistema = sa.Column(sa.Boolean, default=False, server_default=sa.text("false"), nullable=False)
    creado_en = sa.Column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)

    ticket = relationship("TicketORM", back_populates="mensajes")
    remitente = relationship("UserORM", foreign_keys=[remitente_id])
