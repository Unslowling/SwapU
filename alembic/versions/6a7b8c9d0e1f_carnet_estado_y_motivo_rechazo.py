"""agregar carnet_estado y carnet_rechazo_motivo a usuarios

Revision ID: 6a7b8c9d0e1f
Revises: 5e6f7a8b9c0d
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "6a7b8c9d0e1f"
down_revision = "5e6f7a8b9c0d"
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

    if "carnet_estado" not in existentes:
        op.add_column("usuarios", sa.Column("carnet_estado", sa.String(50), nullable=True))

    if "carnet_rechazo_motivo" not in existentes:
        op.add_column("usuarios", sa.Column("carnet_rechazo_motivo", sa.String(500), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    existentes = _obtener_columnas_existentes(bind, "usuarios")

    if not existentes:
        return

    if "carnet_rechazo_motivo" in existentes:
        op.drop_column("usuarios", "carnet_rechazo_motivo")

    if "carnet_estado" in existentes:
        op.drop_column("usuarios", "carnet_estado")
