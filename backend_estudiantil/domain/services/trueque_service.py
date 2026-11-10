
from backend_estudiantil.domain.models.trueque import Trueque
from backend_estudiantil.ports.repositories.trueque_repository import TruequeRepository


class TruequeService:
    """
    Servicio de dominio para la gestión del ciclo de vida de los trueques.
    Maneja las transiciones de estado: propuesto → confirmado → completado / rechazado.
    """

    ESTADOS_VALIDOS = {"propuesto", "confirmado", "completado", "rechazado"}

    def __init__(self, repo: TruequeRepository):
        self.repo = repo

    async def proponer_trueque(
        self,
        usuario_propone_id: int,
        usuario_recibe_id: int | None = None,
        match_id: int | None = None,
        publicacion_origen_id: int | None = None,
        publicacion_destino_id: int | None = None,
    ) -> Trueque:
        """Crea una nueva propuesta de trueque entre dos usuarios."""
        if (publicacion_origen_id is None) != (publicacion_destino_id is None):
            raise ValueError("Debes indicar ambas publicaciones para proponer el trueque")
        if publicacion_origen_id is not None and publicacion_destino_id is not None:
            return await self.repo.create_from_publications(
                usuario_propone_id,
                publicacion_origen_id,
                publicacion_destino_id,
                usuario_recibe_id,
            )
        if match_id is not None:
            return await self.repo.create_from_match(
                usuario_propone_id, match_id, usuario_recibe_id
            )
        raise ValueError("Debes indicar un match o las publicaciones del trueque")

    async def obtener_trueque(self, trueque_id: int) -> Trueque:
        trueque = await self.repo.get_by_id(trueque_id)
        if not trueque:
            raise ValueError(f"Trueque {trueque_id} no encontrado")
        return trueque

    async def listar_trueques_usuario(
        self, usuario_id: int, estado: str | None = None, skip: int = 0, limit: int = 50
    ) -> list[Trueque]:
        if estado and estado not in self.ESTADOS_VALIDOS:
            raise ValueError(f"Estado inválido: {estado}. Válidos: {self.ESTADOS_VALIDOS}")
        return await self.repo.list_by_usuario(usuario_id, estado=estado, skip=skip, limit=limit)

    async def confirmar_trueque(self, trueque_id: int, usuario_id: int) -> Trueque:
        """El usuario receptor confirma la propuesta de trueque."""
        trueque = await self.obtener_trueque(trueque_id)
        if trueque.usuario_recibe_id != usuario_id:
            raise PermissionError("Solo el usuario receptor puede confirmar el trueque")
        trueque.confirmar()
        return await self.repo.update(trueque)

    async def completar_trueque(self, trueque_id: int, usuario_id: int) -> Trueque:
        """Cualquier participante puede marcar el trueque como completado."""
        trueque = await self.obtener_trueque(trueque_id)
        if usuario_id not in (trueque.usuario_propone_id, trueque.usuario_recibe_id):
            raise PermissionError("Solo los participantes del trueque pueden completarlo")
        trueque.completar()
        return await self.repo.update(trueque)

    async def rechazar_trueque(self, trueque_id: int, usuario_id: int) -> Trueque:
        """El usuario receptor puede rechazar la propuesta."""
        trueque = await self.obtener_trueque(trueque_id)
        if usuario_id not in (trueque.usuario_propone_id, trueque.usuario_recibe_id):
            raise PermissionError("Solo los participantes pueden rechazar el trueque")
        trueque.rechazar()
        return await self.repo.update(trueque)
