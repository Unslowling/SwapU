"""
moderacion_sanciones_service.py
-------------------------------
Servicio de dominio hexagonal para la gestión centralizada de sanciones,
advertencias, reportes, apelaciones y la verificación del estado de operación del usuario.

Reglas:
- Escalera de sanciones:
    advertencia -> suspensión de 7 días -> suspensión de 30 días -> bloqueo definitivo.
- Faltas graves van directo a bloqueo definitivo.
- Las advertencias se cuentan dentro de la ventana móvil de settings.SANCIONES_VENTANA_DIAS_ADVERTENCIAS (90 días).
- Al acumular settings.SANCIONES_NUM_ADVERTENCIAS_SUSPENSION (3 advertencias), se escala a suspensión.
- La suspensión vence automáticamente cuando transcurre la fecha_fin sin requerir tareas programadas (self-healing).
- Toda acción registra auditoría en AuditoriaLogORM (ADVERTENCIA_APLICADA, SANCION_APLICADA, SANCION_LEVANTADA, APELACION_RESUELTA).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.future import select

from backend_estudiantil.adapters.db import (
    AdvertenciaORM,
    ApelacionORM,
    AuditoriaLogORM,
    SancionORM,
    UserORM,
    get_session_factory,
)
from backend_estudiantil.config.settings import settings


@dataclass
class ResultadoOperacionUsuario:
    """Resultado de evaluar si un usuario puede operar en la plataforma."""
    puede_operar: bool
    motivo: str | None = None
    fecha_fin: datetime | None = None
    estado_cuenta: str = "activo"

    def __bool__(self) -> bool:
        return self.puede_operar


def _requiere_confirmacion_correo(usuario: Any) -> bool:
    """True si la cuenta es institucional y su correo aún no está confirmado.

    Se controla con CONFIRMACION_CORREO_OBLIGATORIA para poder desactivar la regla
    durante una transición. Si el objeto no trae el dato, no se bloquea (compatibilidad).
    """
    from backend_estudiantil.config.settings import settings

    if not getattr(settings, "CONFIRMACION_CORREO_OBLIGATORIA", True):
        return False
    if getattr(usuario, "correo_confirmado", True):
        return False
    correo = getattr(usuario, "correo_institucional", None) or ""
    return bool(settings.es_dominio_institucional(correo))


def usuario_puede_operar(usuario: Any) -> ResultadoOperacionUsuario:
    """Función de dominio centralizada para evaluar si un usuario puede operar en la plataforma.
    
    Verifica estado_cuenta y fin_suspension. Si la suspensión expiró, permite operar
    (autocumplimiento de suspensión sin tareas en segundo plano).
    """
    if usuario is None:
        return ResultadoOperacionUsuario(
            puede_operar=False,
            motivo="Usuario no encontrado",
            fecha_fin=None,
            estado_cuenta="inactivo",
        )

    estado = getattr(usuario, "estado_cuenta", "activo") or "activo"
    fin_suspension = getattr(usuario, "fin_suspension", None)
    motivo = getattr(usuario, "motivo_sancion", None)

    # 1. Bloqueo definitivo
    if estado == "bloqueado":
        return ResultadoOperacionUsuario(
            puede_operar=False,
            motivo=motivo or "Cuenta bloqueada definitivamente por infracción a los términos de servicio.",
            fecha_fin=None,
            estado_cuenta="bloqueado",
        )

    # 2. Suspensión temporal con verificación de expiración en tiempo real
    if estado == "suspendido":
        if fin_suspension:
            now_utc = datetime.now(timezone.utc)
            fin_utc = fin_suspension if fin_suspension.tzinfo else fin_suspension.replace(tzinfo=timezone.utc)

            # Si ya pasó la fecha de fin, la suspensión terminó sola
            if now_utc >= fin_utc:
                # Actualizar objeto en memoria
                usuario.estado_cuenta = "activo"
                usuario.fin_suspension = None
                usuario.motivo_sancion = None
                return ResultadoOperacionUsuario(
                    puede_operar=True,
                    motivo=None,
                    fecha_fin=None,
                    estado_cuenta="activo",
                )
            else:
                return ResultadoOperacionUsuario(
                    puede_operar=False,
                    motivo=motivo or "Cuenta suspendida temporalmente.",
                    fecha_fin=fin_utc,
                    estado_cuenta="suspendido",
                )
        else:
            return ResultadoOperacionUsuario(
                puede_operar=False,
                motivo=motivo or "Cuenta suspendida.",
                fecha_fin=None,
                estado_cuenta="suspendido",
            )

    # 3. Usuario inactivo
    if hasattr(usuario, "is_active") and not usuario.is_active and estado != "pendiente":
        return ResultadoOperacionUsuario(
            puede_operar=False,
            motivo="Cuenta inactiva.",
            fecha_fin=None,
            estado_cuenta="inactivo",
        )

    # 4. Correo institucional sin confirmar: no puede operar hasta confirmar el código/enlace.
    # Las cuentas generales (dominio no institucional) no requieren confirmación.
    if _requiere_confirmacion_correo(usuario):
        return ResultadoOperacionUsuario(
            puede_operar=False,
            motivo=(
                "Debes confirmar tu correo institucional antes de operar. "
                "Solicita un nuevo código de confirmación si el anterior venció."
            ),
            fecha_fin=None,
            estado_cuenta="pendiente",
        )

    # 5. Cuenta activa
    return ResultadoOperacionUsuario(
        puede_operar=True,
        motivo=None,
        fecha_fin=None,
        estado_cuenta=estado,
    )


async def registrar_auditoria_accion(
    usuario_id: int | None,
    accion: str,
    recurso: str,
    detalle: str,
    usuario_email: str | None = None,
    usuario_rol: str | None = None,
    ip_origen: str = "127.0.0.1",
    metodo_http: str = "POST",
    endpoint: str = "/moderacion",
) -> None:
    """Registra eventos de moderación y sanciones en AuditoriaLogORM respetando las 5W y sin texto ofensivo."""
    factory = get_session_factory()
    async with factory() as session:
        audit = AuditoriaLogORM(
            usuario_id=usuario_id,
            usuario_email=usuario_email,
            usuario_rol=usuario_rol,
            ip_origen=ip_origen,
            accion=accion,
            recurso=recurso,
            metodo_http=metodo_http,
            endpoint=endpoint,
            estado_http=200,
            exito=True,
            detalle=detalle,
        )
        session.add(audit)
        await session.commit()


class ModeracionSancionesService:
    """Servicio de dominio para aplicar sanciones, advertencias, reportes y apelaciones."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory

    @property
    def session_factory(self):
        return self._session_factory if self._session_factory is not None else get_session_factory()

    async def aplicar_advertencia(
        self,
        usuario_id: int,
        motivo: str,
        moderador_id: int | None = None,
        origen: str = "manual",
    ) -> dict:
        """Aplica una advertencia a un usuario y evalúa la escalera de sanciones.
        Si alcanza el umbral de advertencias en la ventana configurable, escala automáticamente a suspensión.
        """
        now = datetime.now(timezone.utc)
        ventana_inicio = now - timedelta(days=settings.SANCIONES_VENTANA_DIAS_ADVERTENCIAS)

        async with self.session_factory() as session:
            # 1. Crear advertencia
            adv = AdvertenciaORM(
                usuario_id=usuario_id,
                moderador_id=moderador_id,
                motivo=motivo,
                origen=origen,
                creado_en=now,
            )
            session.add(adv)
            await session.commit()
            await session.refresh(adv)

            # 2. Contar advertencias dentro de la ventana de días
            res_count = await session.execute(
                select(func.count(AdvertenciaORM.id)).where(
                    AdvertenciaORM.usuario_id == usuario_id,
                    AdvertenciaORM.creado_en >= ventana_inicio,
                )
            )
            total_advertencias = res_count.scalar_one() or 1

        # Auditoría sin guardar texto ofensivo
        await registrar_auditoria_accion(
            usuario_id=usuario_id,
            accion="ADVERTENCIA_APLICADA",
            recurso=f"usuario:{usuario_id}",
            detalle=f"advertencia_id={adv.id}, total_recientes={total_advertencias}, origen={origen}",
        )

        escalado = None
        # 3. Evaluar si se alcanzó el límite para escalar a suspensión
        if total_advertencias >= settings.SANCIONES_NUM_ADVERTENCIAS_SUSPENSION:
            escalado = await self._escalar_sancion_usuario(
                usuario_id=usuario_id,
                motivo_escalamiento=f"Acumulación de {total_advertencias} advertencias en los últimos {settings.SANCIONES_VENTANA_DIAS_ADVERTENCIAS} días.",
                moderador_id=moderador_id,
            )

        return {
            "advertencia_id": adv.id,
            "usuario_id": usuario_id,
            "total_advertencias_ventana": total_advertencias,
            "escalado_a_sancion": escalado is not None,
            "sancion_escalada": escalado,
        }

    async def _escalar_sancion_usuario(
        self,
        usuario_id: int,
        motivo_escalamiento: str,
        moderador_id: int | None = None,
    ) -> dict:
        """Determina y aplica el siguiente peldaño en la escalera de sanciones:
        advertencia -> suspensión 7 días -> suspensión 30 días -> bloqueo definitivo.
        """
        async with self.session_factory() as session:
            result = await session.execute(
                select(SancionORM)
                .where(SancionORM.usuario_id == usuario_id)
                .order_by(SancionORM.id.desc())
            )
            sanciones_anteriores = result.scalars().all()

        tipos_anteriores = [s.tipo for s in sanciones_anteriores]
        tipo_siguiente = self._determinar_siguiente_sancion(tipos_anteriores)

        return await self.aplicar_sancion(
            usuario_id=usuario_id,
            tipo=tipo_siguiente,
            motivo=motivo_escalamiento,
            moderador_id=moderador_id,
        )

    @staticmethod
    def _determinar_siguiente_sancion(tipos_anteriores: list[str]) -> str:
        """Determina el próximo tipo de sanción en función de las previas."""
        if "suspension_30" in tipos_anteriores:
            return "bloqueo"
        elif "suspension_7" in tipos_anteriores:
            return "suspension_30"
        return "suspension_7"

    async def aplicar_sancion(
        self,
        usuario_id: int,
        tipo: str,
        motivo: str,
        moderador_id: int | None = None,
        dias: int | None = None,
    ) -> dict:
        """Aplica una sanción (suspensión_7, suspensión_30, bloqueo) a un usuario."""
        now = datetime.now(timezone.utc)
        tipo = tipo.lower().strip()

        if tipo == "bloqueo":
            fecha_fin = None
            nuevo_estado = "bloqueado"
        elif tipo == "suspension_30" or dias == 30:
            fecha_fin = now + timedelta(days=30)
            nuevo_estado = "suspendido"
            tipo = "suspension_30"
        elif tipo == "suspension_7" or dias == 7:
            fecha_fin = now + timedelta(days=7)
            nuevo_estado = "suspendido"
            tipo = "suspension_7"
        elif dias:
            fecha_fin = now + timedelta(days=dias)
            nuevo_estado = "suspendido"
        else:
            # Por defecto suspensión 7 días si no se especificó
            fecha_fin = now + timedelta(days=7)
            nuevo_estado = "suspendido"
            tipo = "suspension_7"

        async with self.session_factory() as session:
            # Actualizar estado de cuenta del usuario
            res_user = await session.execute(select(UserORM).where(UserORM.id == usuario_id))
            user = res_user.scalar_one_or_none()
            if not user:
                raise ValueError(f"Usuario {usuario_id} no encontrado")

            user.estado_cuenta = nuevo_estado
            user.fin_suspension = fecha_fin
            user.motivo_sancion = motivo

            # Crear registro de sanción
            sancion = SancionORM(
                usuario_id=usuario_id,
                moderador_id=moderador_id,
                tipo=tipo,
                motivo=motivo,
                fecha_inicio=now,
                fecha_fin=fecha_fin,
                estado="activa",
                creado_en=now,
            )
            session.add(sancion)
            await session.commit()
            await session.refresh(sancion)

        # Auditoría
        await registrar_auditoria_accion(
            usuario_id=usuario_id,
            accion="SANCION_APLICADA",
            recurso=f"usuario:{usuario_id}",
            detalle=f"sancion_id={sancion.id}, tipo={tipo}, fecha_fin={fecha_fin.isoformat() if fecha_fin else 'indefinida'}",
        )

        return {
            "sancion_id": sancion.id,
            "usuario_id": usuario_id,
            "tipo": tipo,
            "estado_cuenta": nuevo_estado,
            "motivo": motivo,
            "fecha_inicio": now.isoformat(),
            "fecha_fin": fecha_fin.isoformat() if fecha_fin else None,
        }

    async def levantar_sancion(
        self,
        sancion_id: int,
        moderador_id: int,
        motivo: str,
    ) -> dict:
        """Levanta una sanción activa y restaura el estado del usuario si no tiene otras sanciones."""
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            res = await session.execute(select(SancionORM).where(SancionORM.id == sancion_id))
            sancion = res.scalar_one_or_none()
            if not sancion:
                raise ValueError(f"Sanción {sancion_id} no encontrada")

            sancion.estado = "levantada"
            sancion.levantada_en = now
            sancion.levantada_por_id = moderador_id
            sancion.motivo_levantamiento = motivo

            # Verificar si el usuario tiene otras sanciones activas
            res_otras = await session.execute(
                select(SancionORM).where(
                    SancionORM.usuario_id == sancion.usuario_id,
                    SancionORM.id != sancion_id,
                    SancionORM.estado == "activa",
                )
            )
            otras_activas = res_otras.scalars().all()

            if not otras_activas:
                res_user = await session.execute(select(UserORM).where(UserORM.id == sancion.usuario_id))
                user = res_user.scalar_one_or_none()
                if user:
                    user.estado_cuenta = "activo"
                    user.fin_suspension = None
                    user.motivo_sancion = None

            await session.commit()
            await session.refresh(sancion)

        await registrar_auditoria_accion(
            usuario_id=sancion.usuario_id,
            accion="SANCION_LEVANTADA",
            recurso=f"sancion:{sancion_id}",
            detalle=f"levantada_por={moderador_id}, motivo={motivo}",
        )

        return {
            "sancion_id": sancion.id,
            "usuario_id": sancion.usuario_id,
            "estado": "levantada",
            "mensaje": "Sanción levantada exitosamente.",
        }

    async def crear_apelacion(self, sancion_id: int, usuario_id: int, motivo: str) -> dict:
        """Permite al usuario apelar una sanción. Máximo una apelación por sanción."""
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            res_sancion = await session.execute(select(SancionORM).where(SancionORM.id == sancion_id))
            sancion = res_sancion.scalar_one_or_none()
            if not sancion:
                raise ValueError("Sanción no encontrada")

            if sancion.usuario_id != usuario_id:
                raise PermissionError("No puedes apelar una sanción que no te pertenece")

            # Comprobar si ya apeló esta sanción
            res_existente = await session.execute(select(ApelacionORM).where(ApelacionORM.sancion_id == sancion_id))
            if res_existente.scalar_one_or_none():
                raise ValueError("Ya has enviado una apelación para esta sanción. Solo se permite una apelación por sanción.")

            apelacion = ApelacionORM(
                sancion_id=sancion_id,
                usuario_id=usuario_id,
                motivo=motivo,
                estado="pendiente",
                creado_en=now,
            )
            session.add(apelacion)
            await session.commit()
            await session.refresh(apelacion)

        return {
            "apelacion_id": apelacion.id,
            "sancion_id": sancion_id,
            "estado": "pendiente",
            "mensaje": "Apelación radicada correctamente. Será revisada por un moderador.",
        }

    async def resolver_apelacion(
        self,
        apelacion_id: int,
        moderador_id: int,
        aprobada: bool,
        respuesta: str,
    ) -> dict:
        """Resuelve una apelación. Si es aprobada, levanta la sanción asociada automáticamente."""
        now = datetime.now(timezone.utc)
        async with self.session_factory() as session:
            res_ap = await session.execute(select(ApelacionORM).where(ApelacionORM.id == apelacion_id))
            apelacion = res_ap.scalar_one_or_none()
            if not apelacion:
                raise ValueError("Apelación no encontrada")

            if apelacion.estado != "pendiente":
                raise ValueError("Esta apelación ya ha sido resuelta previamente")

            apelacion.estado = "aprobada" if aprobada else "rechazada"
            apelacion.moderador_id = moderador_id
            apelacion.respuesta = respuesta
            apelacion.resuelto_en = now

            sancion_id = apelacion.sancion_id
            usuario_id = apelacion.usuario_id
            await session.commit()
            await session.refresh(apelacion)

        # Si se aprobó, levantar la sanción
        if aprobada:
            await self.levantar_sancion(
                sancion_id=sancion_id,
                moderador_id=moderador_id,
                motivo=f"Apelación #{apelacion_id} aprobada: {respuesta}",
            )

        await registrar_auditoria_accion(
            usuario_id=usuario_id,
            accion="APELACION_RESUELTA",
            recurso=f"apelacion:{apelacion_id}",
            detalle=f"resultado={'aprobada' if aprobada else 'rechazada'}, moderador_id={moderador_id}",
        )

        return {
            "apelacion_id": apelacion.id,
            "estado": apelacion.estado,
            "respuesta": respuesta,
            "mensaje": "Apelación resuelta con éxito.",
        }
