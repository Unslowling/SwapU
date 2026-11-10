import asyncio
import hashlib

import bcrypt


def hash_password(password: str) -> str:
    """Genera un hash seguro con bcrypt y salting para una contraseña plana (síncrono)."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña plana coincide con el hash almacenado (bcrypt o sha256 legado) (síncrono)."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        # Soporte de respaldo para hashes sha256 anteriores
        legacy_hash = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
        return legacy_hash == hashed_password

async def hash_password_async(password: str) -> str:
    """Genera hash con bcrypt ejecutándose en hilo worker mediante asyncio.to_thread para no bloquear el bucle de eventos."""
    return await asyncio.to_thread(hash_password, password)

async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    """Verifica hash con bcrypt ejecutándose en hilo worker mediante asyncio.to_thread para no bloquear el bucle de eventos."""
    return await asyncio.to_thread(verify_password, plain_password, hashed_password)
