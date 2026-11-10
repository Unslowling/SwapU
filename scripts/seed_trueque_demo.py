"""
Script de seed: crea un trueque entre ana.perez@usbmed.edu.co y carlos.gomez@usbmed.edu.co
para poder probar el chat con conversación activa.

Ejecutar desde la raíz del proyecto:
    python scripts/seed_trueque_demo.py
"""

import asyncio
import sys
from pathlib import Path

# Agrega la raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

# Importa modelos ORM
from backend_estudiantil.adapters.db import (
    MatchORM,
    PublicacionORM,
    TruequeORM,
    UserORM,
    CategoriaORM,
)
from backend_estudiantil.config.settings import settings

EMAIL_ANA = "ana.perez@usbmed.edu.co"
EMAIL_CARLOS = "carlos.gomez@usbmed.edu.co"


async def main():
    print(f"Conectando a: {settings.DATABASE_URL}")
    engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # 1. Buscar usuarios
        res = await session.execute(
            select(UserORM).where(UserORM.correo_institucional.in_([EMAIL_ANA, EMAIL_CARLOS]))
        )
        usuarios = {u.correo_institucional: u for u in res.scalars().all()}

        if EMAIL_ANA not in usuarios:
            print(f"ERROR: Usuario no encontrado: {EMAIL_ANA}")
            sys.exit(1)
        if EMAIL_CARLOS not in usuarios:
            print(f"ERROR: Usuario no encontrado: {EMAIL_CARLOS}")
            sys.exit(1)

        ana = usuarios[EMAIL_ANA]
        carlos = usuarios[EMAIL_CARLOS]
        print(f"OK Ana Perez     -> id={ana.id}")
        print(f"OK Carlos Gomez  -> id={carlos.id}")

        # 2. Categoria por defecto
        res_cat = await session.execute(select(CategoriaORM).limit(1))
        categoria = res_cat.scalar_one_or_none()
        categoria_id = categoria.id if categoria else None
        print(f"Categoria usada: id={categoria_id} ({categoria.nombre if categoria else 'ninguna'})")

        # 3. Publicacion de Ana (si no tiene ninguna activa)
        res_pub_ana = await session.execute(
            select(PublicacionORM).where(
                PublicacionORM.usuario_id == ana.id,
                PublicacionORM.estado_publicacion == "activa",
            ).limit(1)
        )
        pub_ana = res_pub_ana.scalar_one_or_none()
        if pub_ana is None:
            pub_ana = PublicacionORM(
                usuario_id=ana.id,
                titulo="Calculo Diferencial - Larson (Demo Ana)",
                autor="Ron Larson",
                estado_libro="Buen estado",
                estado_publicacion="activa",
                tipo_transaccion="trueque",
                libro_buscado="Algebra Lineal - Grossman",
                categoria_id=categoria_id,
            )
            session.add(pub_ana)
            await session.flush()
            print(f"Publicacion creada para Ana -> id={pub_ana.id}")
        else:
            print(f"Publicacion existente de Ana -> id={pub_ana.id} | '{pub_ana.titulo}'")

        # 4. Publicacion de Carlos (si no tiene ninguna activa)
        res_pub_carlos = await session.execute(
            select(PublicacionORM).where(
                PublicacionORM.usuario_id == carlos.id,
                PublicacionORM.estado_publicacion == "activa",
            ).limit(1)
        )
        pub_carlos = res_pub_carlos.scalar_one_or_none()
        if pub_carlos is None:
            pub_carlos = PublicacionORM(
                usuario_id=carlos.id,
                titulo="Algebra Lineal - Grossman (Demo Carlos)",
                autor="Stanley Grossman",
                estado_libro="Buen estado",
                estado_publicacion="activa",
                tipo_transaccion="trueque",
                libro_buscado="Calculo Diferencial - Larson",
                categoria_id=categoria_id,
            )
            session.add(pub_carlos)
            await session.flush()
            print(f"Publicacion creada para Carlos -> id={pub_carlos.id}")
        else:
            print(f"Publicacion existente de Carlos -> id={pub_carlos.id} | '{pub_carlos.titulo}'")

        # 5. Verificar que no exista ya un trueque activo entre ellos
        res_trueque_existente = await session.execute(
            select(TruequeORM).where(
                sa.or_(
                    sa.and_(
                        TruequeORM.usuario_propone_id == ana.id,
                        TruequeORM.usuario_recibe_id == carlos.id,
                    ),
                    sa.and_(
                        TruequeORM.usuario_propone_id == carlos.id,
                        TruequeORM.usuario_recibe_id == ana.id,
                    ),
                ),
                TruequeORM.estado.in_(["propuesto", "confirmado"]),
            ).limit(1)
        )
        trueque_existente = res_trueque_existente.scalar_one_or_none()
        if trueque_existente:
            print(
                f"\nYa existe un trueque activo entre Ana y Carlos -> "
                f"id={trueque_existente.id}, estado='{trueque_existente.estado}'"
            )
            print("No se creara uno nuevo. Listo para probar el chat!")
            await engine.dispose()
            return

        # 6. Crear Match
        res_match = await session.execute(
            select(MatchORM).where(
                sa.or_(
                    sa.and_(
                        MatchORM.publicacion_origen_id == pub_ana.id,
                        MatchORM.publicacion_destino_id == pub_carlos.id,
                    ),
                    sa.and_(
                        MatchORM.publicacion_origen_id == pub_carlos.id,
                        MatchORM.publicacion_destino_id == pub_ana.id,
                    ),
                )
            ).limit(1)
        )
        match = res_match.scalar_one_or_none()
        if match is None:
            match = MatchORM(
                publicacion_origen_id=pub_ana.id,
                publicacion_destino_id=pub_carlos.id,
                tipo_match="exacta",
                puntuacion=95.0,
            )
            session.add(match)
            await session.flush()
            print(f"Match creado -> id={match.id}")
        else:
            print(f"Match existente -> id={match.id}")

        # 7. Crear Trueque
        trueque = TruequeORM(
            match_id=match.id,
            usuario_propone_id=ana.id,
            usuario_recibe_id=carlos.id,
            estado="propuesto",
        )
        session.add(trueque)
        await session.commit()
        await session.refresh(trueque)

        print(f"\nTrueque creado exitosamente!")
        print(f"  id          = {trueque.id}")
        print(f"  proponente  = Ana Perez       (id={ana.id})")
        print(f"  receptor    = Carlos Gomez    (id={carlos.id})")
        print(f"  estado      = {trueque.estado}")
        print(f"  match_id    = {trueque.match_id}")
        print(f"\nAhora puedes abrir el chat con trueque_id={trueque.id}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
