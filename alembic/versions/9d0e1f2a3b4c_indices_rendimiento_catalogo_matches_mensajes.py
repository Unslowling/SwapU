"""indices de rendimiento para catalogo, matches, mensajes y trueques

Revision ID: 9d0e1f2a3b4c
Revises: 8c9d0e1f2a3b
Create Date: 2026-10-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision = "9d0e1f2a3b4c"
down_revision = "8c9d0e1f2a3b"
branch_labels = None
depends_on = None


def _get_indexes(bind, table_name: str) -> set[str] | None:
    inspector = Inspector.from_engine(bind)
    if table_name not in inspector.get_table_names():
        return None
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()

    # Publicaciones
    pub_indexes = _get_indexes(bind, "publicaciones")
    if pub_indexes is not None:
        if "ix_publicaciones_estado_categoria" not in pub_indexes:
            op.create_index(
                "ix_publicaciones_estado_categoria",
                "publicaciones",
                ["estado_publicacion", "categoria_id"],
                unique=False,
            )
        if "ix_publicaciones_usuario_estado" not in pub_indexes:
            op.create_index(
                "ix_publicaciones_usuario_estado",
                "publicaciones",
                ["usuario_id", "estado_publicacion"],
                unique=False,
            )
        if "ix_publicaciones_estado_fecha" not in pub_indexes:
            op.create_index(
                "ix_publicaciones_estado_fecha",
                "publicaciones",
                ["estado_publicacion", "fecha_publicacion"],
                unique=False,
            )

    # Mensajes
    msg_indexes = _get_indexes(bind, "mensajes")
    if msg_indexes is not None:
        if "ix_mensajes_trueque_fecha" not in msg_indexes:
            op.create_index(
                "ix_mensajes_trueque_fecha",
                "mensajes",
                ["trueque_id", "fecha_envio"],
                unique=False,
            )

    # Matches
    match_indexes = _get_indexes(bind, "matches")
    if match_indexes is not None:
        if "ix_matches_origen_puntuacion" not in match_indexes:
            op.create_index(
                "ix_matches_origen_puntuacion",
                "matches",
                ["publicacion_origen_id", "puntuacion"],
                unique=False,
            )

    # Trueques
    trueque_indexes = _get_indexes(bind, "trueques")
    if trueque_indexes is not None:
        if "ix_trueques_propone_estado" not in trueque_indexes:
            op.create_index(
                "ix_trueques_propone_estado",
                "trueques",
                ["usuario_propone_id", "estado"],
                unique=False,
            )
        if "ix_trueques_recibe_estado" not in trueque_indexes:
            op.create_index(
                "ix_trueques_recibe_estado",
                "trueques",
                ["usuario_recibe_id", "estado"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()

    trueque_indexes = _get_indexes(bind, "trueques")
    if "ix_trueques_recibe_estado" in trueque_indexes:
        op.drop_index("ix_trueques_recibe_estado", table_name="trueques")
    if "ix_trueques_propone_estado" in trueque_indexes:
        op.drop_index("ix_trueques_propone_estado", table_name="trueques")

    match_indexes = _get_indexes(bind, "matches")
    if "ix_matches_origen_puntuacion" in match_indexes:
        op.drop_index("ix_matches_origen_puntuacion", table_name="matches")

    msg_indexes = _get_indexes(bind, "mensajes")
    if "ix_mensajes_trueque_fecha" in msg_indexes:
        op.drop_index("ix_mensajes_trueque_fecha", table_name="mensajes")

    pub_indexes = _get_indexes(bind, "publicaciones")
    if "ix_publicaciones_estado_fecha" in pub_indexes:
        op.drop_index("ix_publicaciones_estado_fecha", table_name="publicaciones")
    if "ix_publicaciones_usuario_estado" in pub_indexes:
        op.drop_index("ix_publicaciones_usuario_estado", table_name="publicaciones")
    if "ix_publicaciones_estado_categoria" in pub_indexes:
        op.drop_index("ix_publicaciones_estado_categoria", table_name="publicaciones")
