"""politicas de publicacion, reputacion, sanciones y organizaciones

Revision ID: 8c9d0e1f2a3b
Revises: 7b8c9d0e1f2a
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "8c9d0e1f2a3b"
down_revision = "7b8c9d0e1f2a"
branch_labels = None
depends_on = None


def _get_tables(bind) -> set[str]:
    inspector = Inspector.from_engine(bind)
    return set(inspector.get_table_names())


def _get_columns(bind, table_name: str) -> set[str]:
    inspector = Inspector.from_engine(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _get_tables(bind)

    # 1. Agregar 'suspendido' al enum estado_cuenta_enum si es PostgreSQL
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'estado_cuenta_enum') THEN
                    BEGIN
                        ALTER TYPE estado_cuenta_enum ADD VALUE IF NOT EXISTS 'suspendido';
                    EXCEPTION
                        WHEN duplicate_object THEN NULL;
                    END;
                END IF;
            END
            $$;
            """
        )

    # 2. Tabla organizaciones
    if "organizaciones" not in tables:
        op.create_table(
            "organizaciones",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
            sa.Column("nombre", sa.String(255), unique=True, nullable=False),
            sa.Column("tipo", sa.String(50), nullable=False, server_default="universidad"),
            sa.Column("dominios", sa.JSON(), nullable=False, server_default='["usbmed.edu.co"]'),
            sa.Column("politicas", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # Insertar organización por defecto
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            INSERT INTO organizaciones (nombre, tipo, dominios, politicas)
            SELECT 'Universidad de San Buenaventura Medellín', 'universidad', '["usbmed.edu.co"]'::json, '{"max_publicaciones_verificado": 10, "permite_prestamos": true}'::json
            WHERE NOT EXISTS (
                SELECT 1 FROM organizaciones WHERE nombre = 'Universidad de San Buenaventura Medellín'
            );
            """
        )
    else:
        op.execute(
            """
            INSERT INTO organizaciones (nombre, tipo, dominios, politicas)
            SELECT 'Universidad de San Buenaventura Medellín', 'universidad', '["usbmed.edu.co"]', '{"max_publicaciones_verificado": 10, "permite_prestamos": true}'
            WHERE NOT EXISTS (
                SELECT 1 FROM organizaciones WHERE nombre = 'Universidad de San Buenaventura Medellín'
            );
            """
        )

    # 3. Columnas en usuarios
    cols_usuarios = _get_columns(bind, "usuarios")
    with op.batch_alter_table("usuarios") as batch_op:
        if "organizacion_id" not in cols_usuarios:
            batch_op.add_column(sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", name="fk_usuarios_organizacion_id"), nullable=True))
        if "fin_suspension" not in cols_usuarios:
            batch_op.add_column(sa.Column("fin_suspension", sa.DateTime(timezone=True), nullable=True))
        if "motivo_sancion" not in cols_usuarios:
            batch_op.add_column(sa.Column("motivo_sancion", sa.String(500), nullable=True))

    # Asignar organización por defecto a usuarios existentes de usbmed.edu.co
    op.execute(
        """
        UPDATE usuarios
        SET organizacion_id = (SELECT id FROM organizaciones WHERE nombre = 'Universidad de San Buenaventura Medellín' LIMIT 1)
        WHERE (correo_institucional LIKE '%@usbmed.edu.co' OR correo_institucional LIKE '%.usbmed.edu.co')
          AND organizacion_id IS NULL;
        """
    )

    # 4. Columnas en publicaciones
    if "publicaciones" in tables:
        cols_publicaciones = _get_columns(bind, "publicaciones")
        with op.batch_alter_table("publicaciones") as batch_op:
            if "organizacion_id" not in cols_publicaciones:
                batch_op.add_column(sa.Column("organizacion_id", sa.Integer(), sa.ForeignKey("organizaciones.id", name="fk_publicaciones_organizacion_id"), nullable=True))
            if "tipo_transaccion" not in cols_publicaciones:
                batch_op.add_column(sa.Column("tipo_transaccion", sa.String(20), nullable=False, server_default="trueque"))
            if "fecha_devolucion" not in cols_publicaciones:
                batch_op.add_column(sa.Column("fecha_devolucion", sa.DateTime(timezone=True), nullable=True))

        # Asignar organización a publicaciones según el usuario autor
        if bind.dialect.name == "postgresql":
            op.execute(
                """
                UPDATE publicaciones
                SET organizacion_id = usuarios.organizacion_id
                FROM usuarios
                WHERE publicaciones.usuario_id = usuarios.id
                  AND publicaciones.organizacion_id IS NULL
                  AND usuarios.organizacion_id IS NOT NULL;
                """
            )
        else:
            op.execute(
                """
                UPDATE publicaciones
                SET organizacion_id = (
                    SELECT usuarios.organizacion_id FROM usuarios
                    WHERE usuarios.id = publicaciones.usuario_id
                )
                WHERE publicaciones.organizacion_id IS NULL;
                """
            )

    # 5. Tabla reportes (creación o ajuste de columnas existentes)
    if "reportes" not in tables:
        op.create_table(
            "reportes",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
            sa.Column("reportante_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
            sa.Column("objetivo_id", sa.Integer(), nullable=False),
            sa.Column("tipo_objetivo", sa.String(50), nullable=False),
            sa.Column("motivo", sa.Text(), nullable=False),
            sa.Column("estado", sa.String(50), nullable=False, server_default="pendiente"),
            sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("revisado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("revisado_en", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolucion", sa.Text(), nullable=True),
        )
    else:
        cols_reportes = _get_columns(bind, "reportes")
        if "reportante_id" not in cols_reportes:
            op.add_column("reportes", sa.Column("reportante_id", sa.Integer(), nullable=True))
            if "usuario_reporta_id" in cols_reportes:
                op.execute("UPDATE reportes SET reportante_id = usuario_reporta_id WHERE reportante_id IS NULL")
            op.alter_column("reportes", "reportante_id", nullable=False)
        if "objetivo_id" not in cols_reportes:
            op.add_column("reportes", sa.Column("objetivo_id", sa.Integer(), nullable=True))
            if "publicacion_id" in cols_reportes:
                op.execute("UPDATE reportes SET objetivo_id = publicacion_id WHERE objetivo_id IS NULL")
            op.alter_column("reportes", "objetivo_id", nullable=False)
        if "usuario_reporta_id" in cols_reportes:
            op.alter_column("reportes", "usuario_reporta_id", nullable=True)
        if "publicacion_id" in cols_reportes:
            op.alter_column("reportes", "publicacion_id", nullable=True)
        if "tipo_objetivo" not in cols_reportes:
            op.add_column("reportes", sa.Column("tipo_objetivo", sa.String(50), nullable=False, server_default="publicacion"))
        if "estado" not in cols_reportes:
            op.add_column("reportes", sa.Column("estado", sa.String(50), nullable=False, server_default="pendiente"))
        if "creado_en" not in cols_reportes:
            op.add_column("reportes", sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
        if "revisado_por_id" not in cols_reportes:
            op.add_column("reportes", sa.Column("revisado_por_id", sa.Integer(), nullable=True))
        if "revisado_en" not in cols_reportes:
            op.add_column("reportes", sa.Column("revisado_en", sa.DateTime(timezone=True), nullable=True))
        if "resolucion" not in cols_reportes:
            op.add_column("reportes", sa.Column("resolucion", sa.Text(), nullable=True))

    # 6. Tabla advertencias
    if "advertencias" not in tables:
        op.create_table(
            "advertencias",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
            sa.Column("moderador_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("motivo", sa.Text(), nullable=False),
            sa.Column("origen", sa.String(50), nullable=False, server_default="manual"),
            sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # 7. Tabla sanciones
    if "sanciones" not in tables:
        op.create_table(
            "sanciones",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
            sa.Column("moderador_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("tipo", sa.String(50), nullable=False),
            sa.Column("motivo", sa.Text(), nullable=False),
            sa.Column("fecha_inicio", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("fecha_fin", sa.DateTime(timezone=True), nullable=True),
            sa.Column("estado", sa.String(50), nullable=False, server_default="activa"),
            sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("levantada_en", sa.DateTime(timezone=True), nullable=True),
            sa.Column("levantada_por_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("motivo_levantamiento", sa.Text(), nullable=True),
        )

    # 8. Tabla apelaciones
    if "apelaciones" not in tables:
        op.create_table(
            "apelaciones",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
            sa.Column("sancion_id", sa.Integer(), sa.ForeignKey("sanciones.id"), unique=True, nullable=False),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
            sa.Column("motivo", sa.Text(), nullable=False),
            sa.Column("estado", sa.String(50), nullable=False, server_default="pendiente"),
            sa.Column("moderador_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
            sa.Column("respuesta", sa.Text(), nullable=True),
            sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("resuelto_en", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    op.drop_table("apelaciones")
    op.drop_table("sanciones")
    op.drop_table("advertencias")
    op.drop_table("reportes")
    op.drop_column("publicaciones", "fecha_devolucion")
    op.drop_column("publicaciones", "tipo_transaccion")
    op.drop_column("publicaciones", "organizacion_id")
    op.drop_column("usuarios", "motivo_sancion")
    op.drop_column("usuarios", "fin_suspension")
    op.drop_column("usuarios", "organizacion_id")
    op.drop_table("organizaciones")
