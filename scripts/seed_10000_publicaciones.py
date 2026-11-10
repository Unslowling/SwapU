"""
scripts/seed_10000_publicaciones.py
-----------------------------------
Siembra 10.000 publicaciones sintéticas en PostgreSQL para medir el impacto real
de los índices compuestos en los planes de ejecución (EXPLAIN ANALYZE) y en
el benchmark de carga de GET /publicaciones sin necesidad de desactivar enable_seqscan.
"""

import asyncio
import os
import random
import sys
import time

sys.path.insert(0, os.path.abspath("."))

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func, text
from backend_estudiantil.adapters.db import (
    get_session_factory,
    PublicacionORM,
    UserORM,
    CategoriaORM,
)

TITULOS_BASE = [
    "Cálculo Diferencial e Integral",
    "Álgebra Lineal y sus Aplicaciones",
    "Física Universitaria Sears Zemansky",
    "Estructuras de Datos y Algoritmos en Python",
    "Sistemas Operativos Modernos Tanenbaum",
    "Redes de Computadores Kurose",
    "Principios de Bioquímica Lehninger",
    "Anatomía Humana Netter",
    "Microeconomía Intermedia Varian",
    "Derecho Constitucional Colombiano",
    "Inteligencia Artificial: Un Enfoque Moderno",
    "Ingeniería de Software Pressman",
    "Química Orgánica Wade",
    "Mecánica de Fluidos White",
    "Probabilidad y Estadística para Ingeniería",
    "Electrónica y Teoría de Circuitos Boylestad",
    "Bases de Datos Relacionales Silberschatz",
    "Metodología de la Investigación Hernández Sampieri",
    "Psicología General Feldman",
    "Filosofía del Derecho y Ética Profesional",
]

AUTORES = [
    "Stewart, James", "Tanenbaum, Andrew", "Kurose, James", "Pressman, Roger",
    "Lehninger, Albert", "Varian, Hal", "Netter, Frank", "Wade, L.G.",
    "Silberschatz, Abraham", "Russell, Stuart", "Boylestad, Robert", "White, Frank"
]


async def seed_publicaciones(total_filas: int = 10000, batch_size: int = 1000):
    factory = get_session_factory()

    async with factory() as session:
        # 1. Obtener IDs de usuarios existentes
        user_ids = (await session.execute(select(UserORM.id).limit(500))).scalars().all()
        if not user_ids:
            # Crear un usuario semilla si la base estuviera vacía
            u = UserORM(
                correo_institucional="seed_user@usbmed.edu.co",
                password_hash="fake",
                nombre="Seed",
                apellido="User",
                rol="usuario",
                estado_cuenta="activo",
            )
            session.add(u)
            await session.commit()
            user_ids = [u.id]

        # 2. Asegurar categorías 1 a 6
        cat_count = (await session.execute(select(func.count(CategoriaORM.id)))).scalar() or 0
        if cat_count == 0:
            categorias = [
                CategoriaORM(id=1, nombre="Ingeniería y Tecnología"),
                CategoriaORM(id=2, nombre="Medicina y Salud"),
                CategoriaORM(id=3, nombre="Ciencias Básicas"),
                CategoriaORM(id=4, nombre="Derecho y Políticas"),
                CategoriaORM(id=5, nombre="Economía y Negocios"),
                CategoriaORM(id=6, nombre="Humanidades"),
            ]
            session.add_all(categorias)
            await session.commit()

        print(f"[*] Iniciando inserción masiva de {total_filas} publicaciones sintéticas...")
        t0 = time.perf_counter()

        inserted = 0
        now = datetime.now(timezone.utc)

        while inserted < total_filas:
            current_batch = min(batch_size, total_filas - inserted)
            mappings = []
            for i in range(current_batch):
                idx = inserted + i
                titulo_base = random.choice(TITULOS_BASE)
                titulo = f"{titulo_base} (Vol. {random.randint(1, 10)}) - Ref #{idx+1}"
                cat_id = random.randint(1, 6)
                user_id = random.choice(user_ids)
                estado_pub = "activa" if random.random() < 0.88 else "inactiva"
                dias_atras = random.randint(0, 180)
                fecha = now - timedelta(days=dias_atras, minutes=random.randint(0, 1440))

                mappings.append({
                    "usuario_id": user_id,
                    "titulo": titulo,
                    "autor": random.choice(AUTORES),
                    "isbn": f"978-958-{random.randint(1000, 9999)}-{random.randint(10, 99)}-{random.randint(0, 9)}",
                    "edicion": f"{random.randint(1, 8)}a Edición",
                    "categoria_id": cat_id,
                    "estado_libro": random.choice(["como nuevo", "bueno", "regular"]),
                    "descripcion": f"Ejemplar sintético de prueba #{idx+1} para evaluación de índices en Postgres.",
                    "libro_buscado": random.choice(TITULOS_BASE),
                    "estado_publicacion": estado_pub,
                    "fecha_publicacion": fecha.replace(tzinfo=None),
                    "tipo_transaccion": "trueque",
                })

            await session.execute(
                PublicacionORM.__table__.insert(),
                mappings
            )
            await session.commit()
            inserted += current_batch
            print(f"  -> Insertadas {inserted}/{total_filas} filas...")

        t1 = time.perf_counter()
        print(f"[OK] Inserción completada con éxito en {t1 - t0:.2f} segundos.")

        # Verificar recuento total
        total = (await session.execute(select(func.count(PublicacionORM.id)))).scalar()
        print(f"[*] Total de publicaciones en la base de datos: {total}")

        # Ejecutar ANALYZE para actualizar las estadísticas de Postgres
        print("[*] Ejecutando ANALYZE publicaciones en PostgreSQL...")
        await session.execute(text("ANALYZE publicaciones;"))
        await session.commit()
        print("[OK] Estadísticas del optimizador actualizadas.")


if __name__ == "__main__":
    asyncio.run(seed_publicaciones())
