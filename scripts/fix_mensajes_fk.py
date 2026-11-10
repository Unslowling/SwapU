"""
Corrige la FK rota en la tabla 'mensajes' usando asyncpg directamente.
"""
import asyncio
import asyncpg

DB_DSN = "postgresql://postgres:123456@localhost:5432/trueque"


async def fix():
    conn = await asyncpg.connect(DB_DSN)
    try:
        # 1. Eliminar FK rota
        await conn.execute("ALTER TABLE mensajes DROP CONSTRAINT IF EXISTS mensajes_chat_id_fkey")
        print("DROP mensajes_chat_id_fkey: OK")

        # 2. Eliminar FK correcta si ya existe (idempotente)
        await conn.execute("ALTER TABLE mensajes DROP CONSTRAINT IF EXISTS mensajes_trueque_id_fkey")
        print("DROP mensajes_trueque_id_fkey (si existia): OK")

        # 3. Crear FK correcta
        await conn.execute(
            "ALTER TABLE mensajes ADD CONSTRAINT mensajes_trueque_id_fkey "
            "FOREIGN KEY (trueque_id) REFERENCES trueques(id) ON DELETE CASCADE"
        )
        print("ADD FK mensajes -> trueques: OK")

        # 4. Verificar FKs
        rows = await conn.fetch(
            "SELECT conname, pg_get_constraintdef(oid) "
            "FROM pg_constraint "
            "WHERE conrelid = 'mensajes'::regclass AND contype = 'f'"
        )
        print("\nFKs activas en tabla 'mensajes':")
        for row in rows:
            print(" ", dict(row))

        # 5. Marcar migración como aplicada en alembic_version
        current = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"\nAlembic version actual: {current}")
        if current == "9d0e1f2a3b4c":
            await conn.execute("UPDATE alembic_version SET version_num = 'a1b2c3d4e5f6'")
            print("Alembic version actualizada a: a1b2c3d4e5f6")
        else:
            print("Alembic version sin cambios (ya esta en otro estado)")

        print("\nFix completado exitosamente.")
    finally:
        await conn.close()


asyncio.run(fix())
