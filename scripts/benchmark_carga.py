"""
scripts/benchmark_carga.py
--------------------------
Script de prueba de carga asíncrono con HTTPX para evaluar rendimiento en:
1. GET /publicaciones/ (Consulta de catálogo con 10,000+ filas e índices activos)
2. POST /auth/login (Autenticación y cálculo de bcrypt en hilos worker con 40 cuentas distintas)
3. POST /auth/login_same_account (Demostración de rate limiting / protección fuerza bruta con misma cuenta)
4. POST /trueques/{id}/mensajes (Envío de mensajes con moderación, persistencia y broadcast)

Soporta dos modalidades:
- Sin Redis: Valida el Circuit Breaker (cooldown 30s) y fallback inmediato a memoria local (0 ms de sobrecarga).
- Con Redis: Valida el funcionamiento de Redis activo (emulado con FakeServer / Redis en vivo).
"""

import sys
import os
import asyncio
import time
import statistics
import uuid
from typing import List, Dict, Any
from unittest.mock import patch

sys.path.insert(0, os.path.abspath("."))

from httpx import AsyncClient, ASGITransport
import fakeredis
import fakeredis.aioredis
from backend_estudiantil.infrastructure.main import app
from backend_estudiantil.adapters.db import (
    get_session_factory, UserORM, PublicacionORM, MatchORM, TruequeORM
)
from backend_estudiantil.adapters.security.password_hasher import hash_password
from backend_estudiantil.infrastructure.redis_circuit_breaker import (
    chat_redis_circuit_breaker,
    login_redis_circuit_breaker,
    confirmation_redis_circuit_breaker,
    slowapi_redis_circuit_breaker,
)
from backend_estudiantil.infrastructure.login_rate_limiter import login_rate_limiter
from backend_estudiantil.infrastructure.api.chat_router import manager
from sqlalchemy import text


async def setup_benchmark_fixtures():
    """Crea usuarios, publicaciones, trueque y 40 cuentas independientes para el benchmark."""
    uid = uuid.uuid4().hex[:6]
    factory = get_session_factory()
    async with factory() as session:
        # Precomputar hash una sola vez para rapidez en la siembra
        pwd_hash = hash_password("BenchPass123*")

        # 1. Crear usuarios principales para el trueque
        u1 = UserORM(
            correo_institucional=f"bench1_{uid}@usbmed.edu.co",
            password_hash=pwd_hash,
            nombre="Bench",
            apellido="Uno",
            rol="usuario",
            estado_cuenta="activo",
            verificado_comunidad=True,
            universidad="Universidad de San Buenaventura Medellín (USBMED)",
            programa_area="Ingeniería de Sistemas",
        )
        u2 = UserORM(
            correo_institucional=f"bench2_{uid}@usbmed.edu.co",
            password_hash=pwd_hash,
            nombre="Bench",
            apellido="Dos",
            rol="usuario",
            estado_cuenta="activo",
            verificado_comunidad=True,
            universidad="Universidad de San Buenaventura Medellín (USBMED)",
            programa_area="Ingeniería de Sistemas",
        )
        session.add_all([u1, u2])

        # 2. Crear 40 cuentas independientes para aislar latencia pura de bcrypt sin activar rate limiting
        login_accounts = []
        distinct_users = []
        for i in range(40):
            email = f"bench_user_{i}_{uid}@usbmed.edu.co"
            distinct_users.append(
                UserORM(
                    correo_institucional=email,
                    password_hash=pwd_hash,
                    nombre=f"Bench{i}",
                    apellido="Test",
                    rol="usuario",
                    estado_cuenta="activo",
                    verificado_comunidad=True,
                    universidad="Universidad de San Buenaventura Medellín (USBMED)",
                    programa_area="Ingeniería de Sistemas",
                )
            )
            login_accounts.append({"email": email, "password": "BenchPass123*"})

        session.add_all(distinct_users)
        await session.flush()

        # 3. Publicaciones para trueque
        p1 = PublicacionORM(
            usuario_id=u1.id,
            titulo=f"Libro Benchmark A {uid}",
            autor="Autor Bench",
            categoria_id=1,
            estado_publicacion="activa",
        )
        p2 = PublicacionORM(
            usuario_id=u2.id,
            titulo=f"Libro Benchmark B {uid}",
            autor="Autor Bench",
            categoria_id=1,
            estado_publicacion="activa",
        )
        session.add_all([p1, p2])
        await session.flush()

        # 4. Match y Trueque
        m = MatchORM(
            publicacion_origen_id=p1.id,
            publicacion_destino_id=p2.id,
            tipo_match="exacta",
            puntuacion=100.0,
        )
        session.add(m)
        await session.flush()

        t = TruequeORM(
            match_id=m.id,
            usuario_propone_id=u1.id,
            usuario_recibe_id=u2.id,
            estado="propuesto",
        )
        session.add(t)
        await session.flush()

        await session.execute(
            text("INSERT INTO chats (id, trueque_id, fecha_creacion) VALUES (:id, :tid, now()) ON CONFLICT (id) DO NOTHING"),
            {"id": t.id, "tid": t.id}
        )
        await session.commit()

        return {
            "uid": uid,
            "email": u1.correo_institucional,
            "password": "BenchPass123*",
            "user1_id": u1.id,
            "user2_id": u2.id,
            "pub1_id": p1.id,
            "pub2_id": p2.id,
            "match_id": m.id,
            "trueque_id": t.id,
            "login_accounts": login_accounts,
        }


async def cleanup_benchmark_fixtures(data: dict):
    factory = get_session_factory()
    async with factory() as session:
        uid = data["uid"]
        tid = data["trueque_id"]
        mid = data["match_id"]
        pids = [data["pub1_id"], data["pub2_id"]]

        await session.execute(text("DELETE FROM mensajes WHERE trueque_id = :tid"), {"tid": tid})
        await session.execute(text("DELETE FROM chats WHERE id = :tid"), {"tid": tid})
        await session.execute(text("DELETE FROM trueques WHERE id = :tid"), {"tid": tid})
        await session.execute(text("DELETE FROM matches WHERE id = :mid"), {"mid": mid})
        await session.execute(text("DELETE FROM publicaciones WHERE id = ANY(:pids)"), {"pids": pids})
        await session.execute(
            text("DELETE FROM usuarios WHERE correo_institucional LIKE :pat"),
            {"pat": f"%_{uid}@usbmed.edu.co"},
        )
        await session.commit()


async def ejecutar_peticiones_concurrentes(cliente: AsyncClient, request_fn, total: int, concurrencia: int) -> Dict[str, Any]:
    sem = asyncio.Semaphore(concurrencia)
    tiempos: List[float] = []
    errores: int = 0

    async def worker(idx: int):
        nonlocal errores
        async with sem:
            t0 = time.perf_counter()
            try:
                ok = await request_fn(idx)
                if not ok:
                    errores += 1
            except Exception:
                errores += 1
            finally:
                t1 = time.perf_counter()
                tiempos.append((t1 - t0) * 1000.0)  # ms

    tareas = [asyncio.create_task(worker(i)) for i in range(total)]
    await asyncio.gather(*tareas)

    tiempos.sort()
    p50 = statistics.median(tiempos) if tiempos else 0.0
    p95 = tiempos[int(len(tiempos) * 0.95)] if tiempos else 0.0
    avg = statistics.mean(tiempos) if tiempos else 0.0

    return {
        "total": total,
        "concurrencia": concurrencia,
        "avg_ms": round(avg, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
        "errores": errores,
    }


def reset_circuit_breakers():
    """Restablece los circuit breakers a estado inicial."""
    chat_redis_circuit_breaker.reset()
    login_redis_circuit_breaker.reset()
    confirmation_redis_circuit_breaker.reset()
    slowapi_redis_circuit_breaker.reset()
    manager._redis = None
    manager._publisher = None
    login_rate_limiter._redis_client = None


async def run_benchmark(with_redis: bool = False, iterations: int = 40, concurrency: int = 8) -> Dict[str, Any]:
    reset_circuit_breakers()

    fake_server = fakeredis.FakeServer() if with_redis else None

    def fake_redis_async_from_url(*args, **kwargs):
        return fakeredis.aioredis.FakeRedis(server=fake_server, decode_responses=True)

    def fake_redis_sync_from_url(*args, **kwargs):
        return fakeredis.FakeRedis(server=fake_server, decode_responses=True)

    patches = []
    if with_redis:
        patches.append(patch("redis.asyncio.from_url", side_effect=fake_redis_async_from_url))
        patches.append(patch("redis.from_url", side_effect=fake_redis_sync_from_url))
        for p in patches:
            p.start()

    transport = ASGITransport(app=app)
    fixtures = await setup_benchmark_fixtures()
    results = {}

    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Login inicial para obtener token de envío de mensajes
            login_resp = await ac.post("/auth/login", json={
                "email": fixtures["email"],
                "password": fixtures["password"],
            }, headers={"X-Forwarded-For": "10.0.0.1"})
            token = login_resp.json().get("access_token")
            headers = {"Authorization": f"Bearer {token}"}
            trueque_id = fixtures["trueque_id"]

            # 1. Benchmark: GET /publicaciones/
            async def req_publicaciones(idx: int):
                r = await ac.get("/publicaciones/?limit=20")
                return r.status_code == 200

            results["get_publicaciones"] = await ejecutar_peticiones_concurrentes(
                ac, req_publicaciones, total=iterations, concurrencia=concurrency
            )

            # 2. Benchmark: POST /auth/login con cuentas distintas (aislando cálculo puro de bcrypt en hilos)
            async def req_login_distinct(idx: int):
                acc = fixtures["login_accounts"][idx]
                r = await ac.post("/auth/login", json={
                    "email": acc["email"],
                    "password": acc["password"],
                }, headers={"X-Forwarded-For": f"192.168.10.{idx + 1}"})
                return r.status_code == 200

            results["post_login_cuentas_distintas"] = await ejecutar_peticiones_concurrentes(
                ac, req_login_distinct, total=iterations, concurrencia=concurrency
            )

            # 3. Benchmark: POST /auth/login con misma cuenta (demuestra activación de rate limiting 429)
            async def req_login_same(idx: int):
                r = await ac.post("/auth/login", json={
                    "email": fixtures["email"],
                    "password": fixtures["password"],
                }, headers={"X-Forwarded-For": "172.16.0.1"})
                return r.status_code == 200

            results["post_login_misma_cuenta"] = await ejecutar_peticiones_concurrentes(
                ac, req_login_same, total=iterations, concurrencia=concurrency
            )

            # 4. Benchmark: POST /trueques/{id}/mensajes
            async def req_mensaje(idx: int):
                r = await ac.post(
                    f"/trueques/{trueque_id}/mensajes",
                    json={"contenido": f"Mensaje de prueba de carga #{idx}"},
                    headers=headers,
                )
                return r.status_code == 201

            results["post_mensajes"] = await ejecutar_peticiones_concurrentes(
                ac, req_mensaje, total=iterations, concurrencia=concurrency
            )

    finally:
        if with_redis:
            for p in patches:
                p.stop()
        reset_circuit_breakers()
        await cleanup_benchmark_fixtures(fixtures)

    return results


async def main():
    print("=" * 70)
    print("EJECUTANDO BENCHMARK: 1) SIN REDIS (Circuit Breaker & Fallback Memoria)")
    print("=" * 70)
    res_sin_redis = await run_benchmark(with_redis=False)
    for endpoint, m in res_sin_redis.items():
        print(f"[{endpoint}] Total: {m['total']} | Concurrencia: {m['concurrencia']}")
        print(f"  Avg: {m['avg_ms']} ms | p50: {m['p50_ms']} ms | p95: {m['p95_ms']} ms | Errores: {m['errores']}")

    print("\n" + "=" * 70)
    print("EJECUTANDO BENCHMARK: 2) CON REDIS (Activo)")
    print("=" * 70)
    res_con_redis = await run_benchmark(with_redis=True)
    for endpoint, m in res_con_redis.items():
        print(f"[{endpoint}] Total: {m['total']} | Concurrencia: {m['concurrencia']}")
        print(f"  Avg: {m['avg_ms']} ms | p50: {m['p50_ms']} ms | p95: {m['p95_ms']} ms | Errores: {m['errores']}")


if __name__ == "__main__":
    asyncio.run(main())

