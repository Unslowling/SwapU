"""
scripts/explain_queries.py
--------------------------
Muestra los planes de ejecución reales en PostgreSQL (EXPLAIN ANALYZE)
SIN desactivar enable_seqscan (enable_seqscan = on por defecto).
Demuestra el uso real de los índices ix_publicaciones_* con 10.000+ filas en la base de datos.
"""

import asyncio
import os
import sys
import sqlalchemy as sa

sys.path.insert(0, os.path.abspath("."))

from backend_estudiantil.adapters.db import get_engine


async def main():
    engine = get_engine()
    async with engine.connect() as conn:
        # Confirmar que enable_seqscan está activo (on) por defecto
        seqscan_status = (await conn.execute(sa.text("SHOW enable_seqscan;"))).scalar()
        print(f"\n=== ESTADO DE ENABLE_SEQSCAN: {seqscan_status} (POR DEFECTO, SIN FORZAR) ===\n")

        queries = [
            (
                "PUBLICACIONES: Filtro por estado_publicacion y categoria_id (ix_publicaciones_estado_categoria)",
                "EXPLAIN ANALYZE SELECT * FROM publicaciones WHERE estado_publicacion = 'activa' AND categoria_id = 3",
            ),
            (
                "PUBLICACIONES: Filtro por usuario_id y estado_publicacion (ix_publicaciones_usuario_estado)",
                "EXPLAIN ANALYZE SELECT * FROM publicaciones WHERE usuario_id = 1 AND estado_publicacion = 'activa'",
            ),
            (
                "PUBLICACIONES: Ordenación por fecha_publicacion con paginación (ix_publicaciones_estado_fecha)",
                "EXPLAIN ANALYZE SELECT * FROM publicaciones WHERE estado_publicacion = 'activa' ORDER BY fecha_publicacion DESC LIMIT 20",
            ),
            (
                "MATCHES: Búsqueda por publicación origen y puntuación (ix_matches_origen_puntuacion)",
                "EXPLAIN ANALYZE SELECT * FROM matches WHERE publicacion_origen_id = 1 ORDER BY puntuacion DESC",
            ),
            (
                "MENSAJES: Carga de historial cronológico por trueque (ix_mensajes_trueque_fecha)",
                "EXPLAIN ANALYZE SELECT * FROM mensajes WHERE trueque_id = 1 ORDER BY fecha_envio ASC",
            ),
        ]

        for title, q in queries:
            print("=================================================================")
            print(f"QUERY: {title}")
            print(f"SQL: {q}")
            print("-----------------------------------------------------------------")
            res = await conn.execute(sa.text(q))
            for row in res:
                print(" ", row[0])
            print()

        print("\n=== ÍNDICES ACTIVOS EN POSTGRESQL ===")
        idx_res = await conn.execute(sa.text("""
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename IN ('publicaciones', 'matches', 'mensajes', 'trueques')
            ORDER BY tablename, indexname;
        """))
        for row in idx_res:
            print(f"{row[0]} | {row[1]} | {row[2]}")


if __name__ == "__main__":
    asyncio.run(main())
