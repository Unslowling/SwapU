
from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.models.calificacion import Calificacion
from backend_estudiantil.ports.repositories.calificacion_repository import (
    CalificacionRepository,
)
from backend_estudiantil.ports.repositories.trueque_repository import TruequeRepository


class CalificacionService:
    """
    Servicio de dominio para la gestión de calificaciones y reputación.
    Solo se puede calificar un trueque completado y una vez por participante.
    """

    def __init__(self, calificacion_repo: CalificacionRepository, trueque_repo: TruequeRepository | None = None):
        self.calificacion_repo = calificacion_repo
        self.trueque_repo = trueque_repo

    async def calificar_trueque(
        self,
        trueque_id: int,
        usuario_califica_id: int,
        usuario_calificado_id: int,
        estrellas: int,
        resena: str | None = None,
    ) -> Calificacion:
        """
        Registra una calificación post-trueque.
        - El trueque debe estar en estado 'completado'.
        - Solo los participantes del trueque pueden calificar.
        - Cada participante puede calificar al otro solo una vez.
        """
        trueque = await self.trueque_repo.get_by_id(trueque_id)
        if not trueque:
            raise ValueError(f"Trueque {trueque_id} no encontrado")

        if trueque.estado != "completado":
            raise ValueError(f"Solo se puede calificar un trueque completado. Estado actual: '{trueque.estado}'")

        participantes = {trueque.usuario_propone_id, trueque.usuario_recibe_id}
        if usuario_califica_id not in participantes:
            raise PermissionError("Solo los participantes del trueque pueden calificar")

        if usuario_calificado_id not in participantes:
            raise ValueError("El usuario calificado debe ser participante del trueque")

        if usuario_califica_id == usuario_calificado_id:
            raise ValueError("Un usuario no puede calificarse a sí mismo")

        # Verificar que no haya calificado ya
        existente = await self.calificacion_repo.get_by_trueque_and_calificador(
            trueque_id, usuario_califica_id
        )
        if existente:
            raise ValueError("Ya has calificado este trueque anteriormente")

        resena_limpia = resena
        if resena and resena.strip():
            from backend_estudiantil.domain.services.moderacion_contenido_service import (
                ModeracionContenidoService,
            )
            from backend_estudiantil.infrastructure.moderacion_audit_helper import (
                registrar_auditoria_infraccion,
            )
            mod = ModeracionContenidoService()
            res = mod.procesar_texto(resena)
            if res.accion_auditoria:
                await registrar_auditoria_infraccion(
                    usuario_id=usuario_califica_id,
                    recurso=f"trueque:{trueque_id}:calificacion",
                    accion=res.accion_auditoria,
                    severidad=res.nivel_severidad or "leve",
                    categoria="vocabulario",
                    metodo_http="POST",
                    endpoint=f"/calificaciones/trueques/{trueque_id}",
                    estado_http=400 if not res.es_valido else 200,
                    terminos_count=len(res.terminos_detectados),
                )
            if not res.es_valido:
                raise ValueError(f"Reseña rechazada: {res.mensaje_error}")
            resena_limpia = res.texto_final

        calificacion = Calificacion(
            trueque_id=trueque_id,
            usuario_califica_id=usuario_califica_id,
            usuario_calificado_id=usuario_calificado_id,
            estrellas=estrellas,
            resena=resena_limpia,
        )
        return await self.calificacion_repo.create(calificacion)

    async def obtener_reputacion_usuario(self, usuario_id: int) -> dict:
        """
        Calcula la reputación bayesiana de un usuario:
          (C * m + suma_de_estrellas) / (C + n)
        con m = media global de la plataforma y C configurable en settings.
        Retorna además el nivel de reputación ('nuevo', 'confiable', 'destacado').
        """
        calificaciones = await self.calificacion_repo.list_by_usuario_calificado(usuario_id)
        media_global, total_global = await self.calificacion_repo.get_global_rating_stats()

        n = len(calificaciones)
        c_param = float(settings.BAYESIAN_C)
        m_param = media_global

        if n == 0:
            bayesiano = None
            nivel = "nuevo"
            promedio_simple = None
        else:
            suma_estrellas = sum(c.estrellas for c in calificaciones)
            promedio_simple = round(suma_estrellas / n, 2)
            bayesiano = round((c_param * m_param + suma_estrellas) / (c_param + n), 2)

            if n < settings.REPUTACION_MIN_RESENAS_CONFIABLE:
                nivel = "nuevo"
            elif n >= settings.REPUTACION_MIN_RESENAS_DESTACADO and bayesiano >= settings.REPUTACION_UMBRAL_DESTACADO:
                nivel = "destacado"
            else:
                nivel = "confiable"

        return {
            "usuario_id": usuario_id,
            "promedio_estrellas": bayesiano,
            "promedio_simple": promedio_simple,
            "promedio_bayesiano": bayesiano,
            "nivel": nivel,
            "total_calificaciones": n,
            "media_global": round(m_param, 2),
            "calificaciones": [
                {
                    "id": c.id,
                    "trueque_id": c.trueque_id,
                    "usuario_califica_id": c.usuario_califica_id,
                    "estrellas": c.estrellas,
                    "resena": c.resena,
                    "fecha_calificacion": c.fecha_calificacion.isoformat() if c.fecha_calificacion else None,
                }
                for c in calificaciones
            ],
        }

    async def listar_calificaciones_usuario(self, usuario_id: int) -> list[Calificacion]:
        return await self.calificacion_repo.list_by_usuario_calificado(usuario_id)
