"""seguridad confirmacion correo intentos hash y matching por facultad

Revision ID: 7b8c9d0e1f2a
Revises: 6a7b8c9d0e1f
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "7b8c9d0e1f2a"
down_revision = "6a7b8c9d0e1f"
branch_labels = None
depends_on = None


def _obtener_columnas_existentes(bind, table_name="usuarios") -> set[str]:
    inspector = Inspector.from_engine(bind)
    if table_name not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    existentes = _obtener_columnas_existentes(bind, "usuarios")

    if not existentes:
        return

    # 1. Nuevas columnas de seguridad y perfil
    if "codigo_confirmacion_intentos" not in existentes:
        op.add_column(
            "usuarios",
            sa.Column("codigo_confirmacion_intentos", sa.Integer(), server_default="0", nullable=False),
        )

    if "correo_confirmado" not in existentes:
        op.add_column(
            "usuarios",
            sa.Column("correo_confirmado", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )

    if "facultad" not in existentes:
        op.add_column(
            "usuarios",
            sa.Column("facultad", sa.String(150), nullable=True),
        )

    # 2. Migración de datos:
    # "Poner verificado_comunidad=False a los usuarios que no hayan confirmado su correo
    # por código ni por Google OAuth con email_verified=true; la migración debe hacerlo."
    # Identificar columna de email
    email_col = "correo_institucional" if "correo_institucional" in existentes else "email"
    pwd_col = "password_hash" if "password_hash" in existentes else "hashed_password"

    # Marcar correo_confirmado=True para cuentas federadas de Google (password_hash vacío y verificado_comunidad previo)
    op.execute(
        sa.text(
            f"""
            UPDATE usuarios
            SET correo_confirmado = true
            WHERE {pwd_col} = '' AND verificado_comunidad = true;
            """
        )
    )

    # Usuarios con código pendiente NO han confirmado su correo: poner verificado_comunidad=False
    op.execute(
        sa.text(
            """
            UPDATE usuarios
            SET verificado_comunidad = false, correo_confirmado = false
            WHERE codigo_confirmacion IS NOT NULL;
            """
        )
    )

    # Desverificar usuarios con contraseña local que no hayan confirmado por código ni tengan carné verificado
    carnet_cond = "AND (carnet_estado IS NULL OR carnet_estado != 'verificado')" if "carnet_estado" in existentes else ""
    op.execute(
        sa.text(
            f"""
            UPDATE usuarios
            SET verificado_comunidad = false
            WHERE {pwd_col} != ''
              AND {pwd_col} IS NOT NULL
              AND correo_confirmado = false
              {carnet_cond};
            """
        )
    )

    # Facebook OAuth nunca otorga verificado_comunidad
    op.execute(
        sa.text(
            f"""
            UPDATE usuarios
            SET verificado_comunidad = false, correo_confirmado = false
            WHERE {email_col} LIKE '%@facebook.%';
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    existentes = _obtener_columnas_existentes(bind, "usuarios")

    if "facultad" in existentes:
        op.drop_column("usuarios", "facultad")
    if "correo_confirmado" in existentes:
        op.drop_column("usuarios", "correo_confirmado")
    if "codigo_confirmacion_intentos" in existentes:
        op.drop_column("usuarios", "codigo_confirmacion_intentos")
