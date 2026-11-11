"""Asigna el rol de ADMINISTRADOR a un usuario existente y con correo confirmado.

El registro público nunca concede roles. Este script es la vía operativa para crear
el primer administrador (o uno nuevo) de forma explícita y auditable.

Uso (desde la carpeta jojual, con .venv activo y el .env configurado):
    python scripts/crear_administrador.py correo@usbmed.edu.co

Antes de escribir muestra la base de datos de destino (sin contraseña) y exige
escribir SI. Solo modifica la fila del usuario indicado.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from backend_estudiantil.adapters.db import get_engine  # noqa: E402


async def main(correo: str) -> int:
    engine = get_engine()
    destino = engine.url.render_as_string(hide_password=True)
    async with engine.begin() as conn:
        fila = (
            await conn.execute(
                text("SELECT id, rol, correo_confirmado FROM usuarios WHERE correo_institucional = :c"),
                {"c": correo},
            )
        ).first()
        if fila is None:
            print("No existe un usuario con ese correo. El usuario debe registrarse primero.")
            return 1
        uid, rol, confirmado = fila
        if rol == "administrador":
            print(f"El usuario id={uid} ya es administrador. No se hicieron cambios.")
            return 0
        if not confirmado:
            print("El correo de ese usuario no está confirmado. Debe confirmarlo antes de recibir el rol.")
            return 1

        print(f"Base de datos de destino: {destino}")
        print(f"Usuario id={uid} | rol actual={rol}")
        try:
            respuesta = input("Escribe SI para asignar el rol de administrador: ").strip()
        except EOFError:
            respuesta = ""
        if respuesta != "SI":
            print("Cancelado. No se hicieron cambios.")
            return 1

        await conn.execute(
            text("UPDATE usuarios SET rol = 'administrador' WHERE id = :id"),
            {"id": uid},
        )
    print(f"Rol administrador asignado al usuario id={uid}.")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python scripts/crear_administrador.py correo@institucional")
        sys.exit(2)
    sys.exit(asyncio.run(main(sys.argv[1])))
