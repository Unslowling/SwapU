
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.models.match import Match
from backend_estudiantil.domain.models.publicacion import Publicacion
from backend_estudiantil.ports.repositories.match_repository import MatchRepository
from backend_estudiantil.ports.repositories.publicacion_repository import (
    PublicacionRepository,
)
from backend_estudiantil.ports.repositories.user_repository import UserRepository


class MatchService:
    """
    Motor de coincidencias entre publicaciones.
    Identifica y registra matches cuando hay complementariedad entre
    lo que un usuario ofrece y lo que otro busca.
    """

    def __init__(
        self,
        match_repo: MatchRepository,
        publicacion_repo: PublicacionRepository,
        user_repo: UserRepository | None = None,
    ):
        self.match_repo = match_repo
        self.publicacion_repo = publicacion_repo
        if user_repo is None:
            from backend_estudiantil.adapters.db.sqlalchemy_user_repository import (
                SQLAlchemyUserRepository,
            )
            self.user_repo = SQLAlchemyUserRepository()
        else:
            self.user_repo = user_repo

    async def buscar_matches_para_publicacion(self, publicacion_id: int) -> list[Match]:
        """
        Busca publicaciones complementarias a la dada y crea matches automáticamente.
        Lógica: si la publicacion A ofrece 'libro_X' y A.libro_buscado coincide
        con B.titulo, entonces hay un match potencial.
        Da prioridad a candidatos de la misma universidad solo si ambos usuarios están verificados.
        """
        pub_origen = await self.publicacion_repo.get_by_id(publicacion_id)
        if not pub_origen:
            raise ValueError(f"Publicación {publicacion_id} no encontrada")

        matches_creados: list[Match] = []

        if not pub_origen.libro_buscado:
            return matches_creados  # Sin búsqueda activa, no hay matching

        # Buscar publicaciones que ofrezcan lo que esta publicación busca
        candidatas = await self.publicacion_repo.list_activas(
            busqueda=pub_origen.libro_buscado,
            limit=100,
        )

        user_origen = await self.user_repo.get_by_id(pub_origen.usuario_id) if self.user_repo else None

        # Optimización Rendimiento: Carga en lote de matches existentes para evitar N consultas repetidas
        existing_destination_ids: set[int] = set()
        if hasattr(self.match_repo, "get_existing_destination_ids"):
            existing_destination_ids = await self.match_repo.get_existing_destination_ids(pub_origen.id)

        # Filtrar candidatos viables
        candidatas_viables = [
            p for p in candidatas
            if p.id != pub_origen.id
            and p.usuario_id != pub_origen.usuario_id
            and p.id not in existing_destination_ids
        ]

        # Optimización Rendimiento: Carga en lote de usuarios candidatos en 1 sola consulta
        users_map = {}
        if self.user_repo and hasattr(self.user_repo, "get_by_ids"):
            uids = list({p.usuario_id for p in candidatas_viables if p.usuario_id})
            users_map = await self.user_repo.get_by_ids(uids)

        candidatos_evaluados = []
        for pub_destino in candidatas_viables:
            # Si el repo no soporta batch, fallback a consulta individual
            if not existing_destination_ids:
                existente = await self.match_repo.get_existing_match(pub_origen.id, pub_destino.id)
                if existente:
                    continue

            user_destino = users_map.get(pub_destino.usuario_id)
            if user_destino is None and self.user_repo:
                user_destino = await self.user_repo.get_by_id(pub_destino.usuario_id)

            # Afinidad y prioridades: SOLO si ambos usuarios están verificados
            bonificacion_afinidad = 0.0
            ambos_verificados = bool(
                user_origen
                and user_destino
                and getattr(user_origen, "verificado_comunidad", False)
                and getattr(user_destino, "verificado_comunidad", False)
            )

            if ambos_verificados:
                # 1. Misma universidad
                if (
                    user_origen.universidad
                    and user_destino.universidad
                    and user_origen.universidad.strip().lower() == user_destino.universidad.strip().lower()
                ):
                    bonificacion_afinidad += settings.MATCHING_PESO_MISMA_UNIVERSIDAD

                # 2. Misma facultad o carrera
                facultad_origen = (getattr(user_origen, "facultad", None) or "").strip().lower()
                facultad_destino = (getattr(user_destino, "facultad", None) or "").strip().lower()
                carrera_origen = (getattr(user_origen, "programa_area", None) or "").strip().lower()
                carrera_destino = (getattr(user_destino, "programa_area", None) or "").strip().lower()

                coincide_facultad = bool(facultad_origen and facultad_destino and facultad_origen == facultad_destino)
                coincide_carrera = bool(carrera_origen and carrera_destino and carrera_origen == carrera_destino)

                if coincide_facultad or coincide_carrera:
                    bonificacion_afinidad += settings.MATCHING_PESO_MISMA_FACULTAD_CARRERA

                # 3. Semestre cercano (en menor medida, diferencia <= 2)
                semestre_origen = getattr(user_origen, "semestre", None)
                semestre_destino = getattr(user_destino, "semestre", None)
                if semestre_origen is not None and semestre_destino is not None:
                    try:
                        diferencia_sem = abs(int(semestre_origen) - int(semestre_destino))
                        if diferencia_sem <= 2:
                            bonificacion_afinidad += settings.MATCHING_PESO_SEMESTRE_CERCANO
                    except (ValueError, TypeError):
                        pass

            puntuacion_base = self._calcular_puntuacion(pub_origen, pub_destino)
            puntuacion_total = min(100.0, round(puntuacion_base + bonificacion_afinidad, 2))

            candidatos_evaluados.append({
                "pub_destino": pub_destino,
                "bonificacion_afinidad": bonificacion_afinidad,
                "puntuacion": puntuacion_total,
            })

        # Ordenar dando prioridad a candidatos con mayor afinidad verificada, luego por puntuación
        candidatos_evaluados.sort(key=lambda x: (x["bonificacion_afinidad"], x["puntuacion"]), reverse=True)

        for item in candidatos_evaluados:
            pub_destino = item["pub_destino"]
            puntuacion = item["puntuacion"]
            tipo = "exacta" if puntuacion >= 90.0 else "similar"

            nuevo_match = Match(
                publicacion_origen_id=pub_origen.id,
                publicacion_destino_id=pub_destino.id,
                tipo_match=tipo,
                puntuacion=puntuacion,
            )
            match_creado = await self.match_repo.create(nuevo_match)
            matches_creados.append(match_creado)

        return matches_creados

    def _calcular_puntuacion(self, origen: Publicacion, destino: Publicacion) -> float:
        """
        Calcula una puntuación de coincidencia entre 0 y 100.
        Compara el libro buscado por origen con el título ofrecido por destino.
        """
        if not origen.libro_buscado or not destino.titulo:
            return 0.0

        buscado = origen.libro_buscado.lower().strip()
        ofrecido = destino.titulo.lower().strip()

        # Coincidencia exacta
        if buscado == ofrecido:
            return 100.0

        # Coincidencia parcial (buscado contenido en ofrecido o viceversa)
        if buscado in ofrecido or ofrecido in buscado:
            return 75.0

        # Coincidencia por palabras clave
        palabras_buscado = set(buscado.split())
        palabras_ofrecido = set(ofrecido.split())
        if palabras_buscado and palabras_ofrecido:
            comunes = palabras_buscado & palabras_ofrecido
            ratio = len(comunes) / max(len(palabras_buscado), len(palabras_ofrecido))
            if ratio > 0:
                return round(ratio * 60.0, 2)

        return 0.0

    async def obtener_match(self, match_id: int) -> Match:
        match = await self.match_repo.get_by_id(match_id)
        if not match:
            raise ValueError(f"Match {match_id} no encontrado")
        return match

    async def listar_matches_usuario(self, usuario_id: int, skip: int = 0, limit: int = 50) -> list[Match]:
        return await self.match_repo.list_by_usuario(usuario_id, skip=skip, limit=limit)
