"""Compara el esquema REAL de PostgreSQL con los modelos ORM. SOLO LECTURA.

Uso (desde la carpeta jojual, con .venv activo y el .env configurado):
    python scripts/comparar_esquema.py

Únicamente ejecuta consultas SELECT sobre information_schema. No crea, modifica
ni borra nada, y no ejecuta migraciones.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from backend_estudiantil.adapters.db import Base, get_engine  # noqa: E402

SQL_TABLAS = (
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
)
SQL_COLUMNAS = "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'"


async def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"Este script compara PostgreSQL; el dialecto configurado es '{engine.dialect.name}'.")
        return 1

    async with engine.connect() as conn:
        tablas_bd = {fila[0] for fila in (await conn.execute(text(SQL_TABLAS))).all()}
        columnas_bd: dict[str, set[str]] = {}
        for tabla, columna in (await conn.execute(text(SQL_COLUMNAS))).all():
            columnas_bd.setdefault(tabla, set()).add(columna)
    await engine.dispose()

    tablas_orm = {t.name: {c.name for c in t.columns} for t in Base.metadata.sorted_tables}
    print(f"Tablas en la base: {len(tablas_bd)} | Modelos ORM: {len(tablas_orm)}")

    faltan = sorted(set(tablas_orm) - tablas_bd)
    sobran = sorted(tablas_bd - set(tablas_orm))
    print("Modelos ORM sin tabla en la base:", faltan or "ninguna")
    print("Tablas en la base sin modelo ORM:", sobran or "ninguna")

    hay_diferencias = bool(faltan or sobran)
    for tabla in sorted(set(tablas_orm) & tablas_bd):
        ausentes = tablas_orm[tabla] - columnas_bd.get(tabla, set())
        extra = columnas_bd.get(tabla, set()) - tablas_orm[tabla]
        if ausentes or extra:
            hay_diferencias = True
            print(f"- {tabla}: columnas ORM ausentes en la base={sorted(ausentes) or '-'} | "
                  f"columnas de la base sin ORM={sorted(extra) or '-'}")
    if not hay_diferencias:
        print("Sin diferencias de tablas ni columnas.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
