"""Utilidades de prueba para crear administradores sin pasar por el registro público.

El registro público nunca concede privilegios (ver UserService.create_user). En las
pruebas, el rol administrador se asigna directamente en la base SQLite temporal aislada.
"""
import sqlite3

from backend_estudiantil.config.settings import settings


def convertir_en_administrador(email: str) -> None:
    """Asigna rol 'administrador' al usuario indicado en la SQLite temporal de la prueba."""
    url = settings.DATABASE_URL
    assert url.startswith("sqlite+aiosqlite:///"), "Solo se permite SQLite temporal en pruebas"
    ruta = url.removeprefix("sqlite+aiosqlite:///")
    con = sqlite3.connect(ruta)
    try:
        cur = con.execute(
            "UPDATE usuarios SET rol = 'administrador' WHERE correo_institucional = ?",
            (email,),
        )
        assert cur.rowcount == 1, f"No se encontró el usuario {email} para promoverlo"
        con.commit()
    finally:
        con.close()
