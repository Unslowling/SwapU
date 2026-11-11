"""Prepara una base de datos NUEVA para el despliegue y crea el administrador inicial.

Se ejecuta antes de iniciar el servidor (ver render.yaml). Es seguro ejecutarlo en cada arranque:

1. Esquema: SOLO si la base no tiene ninguna tabla, crea las tablas de los modelos ORM,
   las categorías base y la organización USBMED. Si ya existen tablas (por ejemplo, una
   copia de `swapu`), NO modifica el esquema ni los datos.
2. Administrador inicial: si están definidas ADMIN_EMAIL_INICIAL y ADMIN_PASSWORD_INICIAL
   y ese correo no existe, crea la cuenta con rol administrador. Si ya existe, no la cambia.
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sqlalchemy as sa  # noqa: E402

from backend_estudiantil.adapters.db import Base, OrganizacionORM, get_engine  # noqa: E402
from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (  # noqa: E402
    SQLAlchemyUserRepository,
)
from backend_estudiantil.adapters.security.password_hasher import hash_password_async  # noqa: E402
from backend_estudiantil.config.settings import settings  # noqa: E402
from backend_estudiantil.domain.models.user import User  # noqa: E402


async def preparar_esquema() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        tablas = await conn.run_sync(lambda c: sa.inspect(c).get_table_names())
        if tablas:
            print(f"[init] La base ya tiene {len(tablas)} tablas: no se modifica el esquema.")
            return
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            OrganizacionORM.__table__.insert().values(
                nombre="Universidad de San Buenaventura Medellín",
                tipo="universidad",
                dominios=["usbmed.edu.co", "tau.usbmed.edu.co"],
                politicas={"max_publicaciones": 10},
            )
        )
        print("[init] Base vacía: esquema creado.")

    # Categorías base (inserta solo las que falten y ajusta la secuencia en PostgreSQL)
    from backend_estudiantil.infrastructure.main import inicializar_categorias

    await inicializar_categorias()
    print("[init] Categorías base listas.")


async def crear_admin_inicial() -> None:
    correo = (os.getenv("ADMIN_EMAIL_INICIAL") or "").strip().lower()
    clave = os.getenv("ADMIN_PASSWORD_INICIAL") or ""
    if not correo or not clave:
        print("[init] ADMIN_EMAIL_INICIAL / ADMIN_PASSWORD_INICIAL no definidas: sin administrador inicial.")
        return
    if len(clave) < 8:
        print("[init] ADMIN_PASSWORD_INICIAL debe tener al menos 8 caracteres: no se crea el administrador.")
        return
    repo = SQLAlchemyUserRepository()
    if await repo.get_by_email(correo):
        print("[init] El administrador inicial ya existe: no se modifica.")
        return
    universidad = settings.obtener_universidad_por_dominio(correo)
    await repo.create(
        User(
            correo_institucional=correo,
            password_hash=await hash_password_async(clave),
            name="Administrador SWAPU",
            rol="administrador",
            estado_cuenta="activo",
            correo_confirmado=True,
            verificado_comunidad=bool(universidad),
            universidad=universidad,
        )
    )
    print("[init] Administrador inicial creado.")


async def main() -> None:
    await preparar_esquema()
    await crear_admin_inicial()
    await get_engine().dispose()


if __name__ == "__main__":
    asyncio.run(main())
