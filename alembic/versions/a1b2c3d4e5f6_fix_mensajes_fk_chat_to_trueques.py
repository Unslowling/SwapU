"""fix_mensajes_fk_chat_to_trueques

Corrige la FK errónea en la tabla 'mensajes':
- La FK 'mensajes_chat_id_fkey' apuntaba a la tabla 'chats' (que no existe).
- Se elimina esa FK y se crea una nueva apuntando correctamente a 'trueques.id'.

Revision ID: a1b2c3d4e5f6
Revises: 9d0e1f2a3b4c
Create Date: 2026-10-28
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9d0e1f2a3b4c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Eliminar la FK rota que apuntaba a 'chats'
    op.drop_constraint("mensajes_chat_id_fkey", "mensajes", type_="foreignkey")

    # 2. Crear la FK correcta que apunta a 'trueques'
    op.create_foreign_key(
        "mensajes_trueque_id_fkey",
        "mensajes",
        "trueques",
        ["trueque_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Revertir: eliminar FK correcta y restaurar la rota (solo para rollback)
    op.drop_constraint("mensajes_trueque_id_fkey", "mensajes", type_="foreignkey")
    op.create_foreign_key(
        "mensajes_chat_id_fkey",
        "mensajes",
        "chats",
        ["trueque_id"],
        ["id"],
        ondelete="CASCADE",
    )
