"""sistema_tickets_revision

Crea las tablas 'tickets_revision' y 'ticket_mensajes' para la
comunicación directa entre moderadores y usuarios cuando un libro va a revisión.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Crear tabla tickets_revision
    op.create_table(
        "tickets_revision",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("publicacion_id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("moderador_id", sa.Integer(), nullable=True),
        sa.Column("asunto", sa.String(length=200), nullable=False),
        sa.Column("estado", sa.String(length=50), server_default="abierto", nullable=False),
        sa.Column("prioridad", sa.String(length=20), server_default="media", nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["publicacion_id"], ["publicaciones.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["moderador_id"], ["usuarios.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tickets_revision_publicacion_id", "tickets_revision", ["publicacion_id"])
    op.create_index("ix_tickets_revision_usuario_id", "tickets_revision", ["usuario_id"])
    op.create_index("ix_tickets_revision_moderador_id", "tickets_revision", ["moderador_id"])
    op.create_index("ix_tickets_revision_estado", "tickets_revision", ["estado"])

    # 2. Crear tabla ticket_mensajes
    op.create_table(
        "ticket_mensajes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("remitente_id", sa.Integer(), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("es_del_sistema", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets_revision.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["remitente_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ticket_mensajes_ticket_id", "ticket_mensajes", ["ticket_id"])
    op.create_index("ix_ticket_mensajes_remitente_id", "ticket_mensajes", ["remitente_id"])


def downgrade() -> None:
    op.drop_table("ticket_mensajes")
    op.drop_table("tickets_revision")

