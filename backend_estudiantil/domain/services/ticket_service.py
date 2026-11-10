import logging
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend_estudiantil.adapters.db import (
    PublicacionORM,
    TicketMensajeORM,
    TicketORM,
    UserORM,
    get_session_factory,
)
from backend_estudiantil.schemas.ticket import (
    TicketDetalleRead,
    TicketMensajeRead,
    TicketRead,
)

logger = logging.getLogger(__name__)


def _es_moderador(usuario: dict) -> bool:
    rol = usuario.get("role") or usuario.get("rol")
    return rol in ("admin", "administrador", "moderador")


class TicketService:
    """Servicio de dominio para la gestión integral de tickets de revisión de libros."""

    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_factory()

    async def crear_ticket(
        self,
        publicacion_id: int,
        asunto: str,
        mensaje_inicial: str,
        usuario_actual: dict,
        prioridad: str = "media",
    ) -> TicketDetalleRead:
        uid = int(usuario_actual["id"])
        es_mod = _es_moderador(usuario_actual)

        async with self.session_factory() as session:
            # 1. Validar publicación
            pub_res = await session.execute(
                select(PublicacionORM).where(PublicacionORM.id == publicacion_id)
            )
            pub = pub_res.scalar_one_or_none()
            if not pub:
                raise ValueError("La publicación no existe")

            # 2. Validar permisos
            if not es_mod and pub.usuario_id != uid:
                raise PermissionError("No tienes permisos para abrir un ticket para esta publicación")

            # 3. Determinar asignaciones y estado inicial
            ahora = datetime.now(timezone.utc)
            if es_mod:
                moderador_id = uid
                estado_inicial = "esperando_estudiante"
            else:
                moderador_id = None
                estado_inicial = "abierto"

            ticket = TicketORM(
                publicacion_id=pub.id,
                usuario_id=pub.usuario_id,
                moderador_id=moderador_id,
                asunto=asunto.strip(),
                estado=estado_inicial,
                prioridad=prioridad,
                creado_en=ahora,
                actualizado_en=ahora,
            )
            session.add(ticket)
            await session.flush()

            # 4. Crear primer mensaje
            mensaje = TicketMensajeORM(
                ticket_id=ticket.id,
                remitente_id=uid,
                contenido=mensaje_inicial.strip(),
                es_del_sistema=False,
                creado_en=ahora,
            )
            session.add(mensaje)
            await session.commit()

            ticket_id = ticket.id

        return await self.obtener_ticket_detalle(ticket_id, usuario_actual)

    async def enviar_mensaje(
        self,
        ticket_id: int,
        contenido: str,
        usuario_actual: dict,
    ) -> TicketMensajeRead:
        uid = int(usuario_actual["id"])
        es_mod = _es_moderador(usuario_actual)
        ahora = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            ticket_res = await session.execute(
                select(TicketORM).where(TicketORM.id == ticket_id)
            )
            ticket = ticket_res.scalar_one_or_none()
            if not ticket:
                raise ValueError("El ticket no existe")

            if not es_mod and ticket.usuario_id != uid:
                raise PermissionError("No tienes acceso a este ticket")

            # Si es moderador, asignarse si no tenía moderador y cambiar estado
            if es_mod:
                if not ticket.moderador_id:
                    ticket.moderador_id = uid
                ticket.estado = "esperando_estudiante"
            else:
                # Estudiante responde
                ticket.estado = "en_revision"

            ticket.actualizado_en = ahora

            nuevo_mensaje = TicketMensajeORM(
                ticket_id=ticket.id,
                remitente_id=uid,
                contenido=contenido.strip(),
                es_del_sistema=False,
                creado_en=ahora,
            )
            session.add(nuevo_mensaje)
            await session.commit()
            await session.refresh(nuevo_mensaje)

            # Cargar datos del remitente
            user_res = await session.execute(
                select(UserORM).where(UserORM.id == uid)
            )
            remitente = user_res.scalar_one_or_none()
            nombre = f"{remitente.nombre or ''} {remitente.apellido or ''}".strip() if remitente else f"Usuario #{uid}"
            rol = remitente.rol if remitente else "usuario"

            return TicketMensajeRead(
                id=nuevo_mensaje.id,
                ticket_id=nuevo_mensaje.ticket_id,
                remitente_id=nuevo_mensaje.remitente_id,
                remitente_nombre=nombre,
                remitente_rol=rol,
                contenido=nuevo_mensaje.contenido,
                es_del_sistema=nuevo_mensaje.es_del_sistema,
                creado_en=nuevo_mensaje.creado_en,
            )

    async def cambiar_estado(
        self,
        ticket_id: int,
        nuevo_estado: str,
        usuario_actual: dict,
    ) -> TicketRead:
        uid = int(usuario_actual["id"])
        es_mod = _es_moderador(usuario_actual)
        ahora = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            ticket_res = await session.execute(
                select(TicketORM).where(TicketORM.id == ticket_id)
            )
            ticket = ticket_res.scalar_one_or_none()
            if not ticket:
                raise ValueError("El ticket no existe")

            if not es_mod and ticket.usuario_id != uid:
                raise PermissionError("No tienes permisos para modificar este ticket")

            if not es_mod and nuevo_estado not in ("resuelto", "cerrado", "abierto"):
                raise PermissionError("Solo un moderador puede asignar este estado al ticket")

            ticket.estado = nuevo_estado
            ticket.actualizado_en = ahora

            # Mensaje informativo del sistema
            sistema_msg = TicketMensajeORM(
                ticket_id=ticket.id,
                remitente_id=uid,
                contenido=f"Estado del ticket actualizado a '{nuevo_estado}' por {usuario_actual.get('email', 'usuario')}.",
                es_del_sistema=True,
                creado_en=ahora,
            )
            session.add(sistema_msg)
            await session.commit()

        return await self.obtener_ticket_detalle(ticket_id, usuario_actual)

    async def obtener_ticket_detalle(
        self,
        ticket_id: int,
        usuario_actual: dict,
    ) -> TicketDetalleRead:
        uid = int(usuario_actual["id"])
        es_mod = _es_moderador(usuario_actual)

        async with self.session_factory() as session:
            stmt = (
                select(TicketORM)
                .options(
                    selectinload(TicketORM.publicacion),
                    selectinload(TicketORM.usuario),
                    selectinload(TicketORM.moderador),
                    selectinload(TicketORM.mensajes).selectinload(TicketMensajeORM.remitente),
                )
                .where(TicketORM.id == ticket_id)
            )
            res = await session.execute(stmt)
            ticket = res.scalar_one_or_none()
            if not ticket:
                raise ValueError("El ticket no existe")

            if not es_mod and ticket.usuario_id != uid:
                raise PermissionError("No tienes acceso a este ticket")

            mensajes_read = []
            for m in ticket.mensajes:
                rem = m.remitente
                r_nombre = f"{rem.nombre or ''} {rem.apellido or ''}".strip() if rem else f"Usuario #{m.remitente_id}"
                r_rol = rem.rol if rem else "usuario"
                mensajes_read.append(
                    TicketMensajeRead(
                        id=m.id,
                        ticket_id=m.ticket_id,
                        remitente_id=m.remitente_id,
                        remitente_nombre=r_nombre,
                        remitente_rol=r_rol,
                        contenido=m.contenido,
                        es_del_sistema=m.es_del_sistema,
                        creado_en=m.creado_en,
                    )
                )

            u = ticket.usuario
            u_nombre = f"{u.nombre or ''} {u.apellido or ''}".strip() if u else f"Usuario #{ticket.usuario_id}"
            u_email = u.correo_institucional if u else None

            mod = ticket.moderador
            mod_nombre = f"{mod.nombre or ''} {mod.apellido or ''}".strip() if mod else None

            ultimo_msg = mensajes_read[-1].contenido if mensajes_read else None

            return TicketDetalleRead(
                id=ticket.id,
                publicacion_id=ticket.publicacion_id,
                publicacion_titulo=ticket.publicacion.titulo if ticket.publicacion else None,
                usuario_id=ticket.usuario_id,
                usuario_nombre=u_nombre,
                usuario_email=u_email,
                moderador_id=ticket.moderador_id,
                moderador_nombre=mod_nombre,
                asunto=ticket.asunto,
                estado=ticket.estado,
                prioridad=ticket.prioridad,
                creado_en=ticket.creado_en,
                actualizado_en=ticket.actualizado_en,
                mensajes_count=len(mensajes_read),
                ultimo_mensaje=ultimo_msg,
                mensajes=mensajes_read,
            )

    async def listar_tickets(
        self,
        usuario_actual: dict,
        solo_mis_tickets: bool = False,
        estado: str | None = None,
        publicacion_id: int | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[TicketRead]:
        uid = int(usuario_actual["id"])
        es_mod = _es_moderador(usuario_actual)

        async with self.session_factory() as session:
            query = (
                select(TicketORM)
                .options(
                    selectinload(TicketORM.publicacion),
                    selectinload(TicketORM.usuario),
                    selectinload(TicketORM.moderador),
                )
                .order_by(TicketORM.actualizado_en.desc())
            )

            # Si no es moderador o solicita explícitamente sus propios tickets
            if not es_mod or solo_mis_tickets:
                query = query.where(TicketORM.usuario_id == uid)

            if estado:
                query = query.where(TicketORM.estado == estado)
            if publicacion_id:
                query = query.where(TicketORM.publicacion_id == publicacion_id)

            query = query.offset(skip).limit(limit)
            result = await session.execute(query)
            tickets = result.scalars().all()

            salida = []
            for t in tickets:
                u = t.usuario
                u_nombre = f"{u.nombre or ''} {u.apellido or ''}".strip() if u else f"Usuario #{t.usuario_id}"
                mod = t.moderador
                mod_nombre = f"{mod.nombre or ''} {mod.apellido or ''}".strip() if mod else None

                # Conteo rápido de mensajes
                c_stmt = select(func.count(TicketMensajeORM.id)).where(TicketMensajeORM.ticket_id == t.id)
                c_res = await session.execute(c_stmt)
                count = c_res.scalar() or 0

                # Último mensaje
                last_stmt = (
                    select(TicketMensajeORM.contenido)
                    .where(TicketMensajeORM.ticket_id == t.id)
                    .order_by(TicketMensajeORM.id.desc())
                    .limit(1)
                )
                last_res = await session.execute(last_stmt)
                last_msg = last_res.scalar()

                salida.append(
                    TicketRead(
                        id=t.id,
                        publicacion_id=t.publicacion_id,
                        publicacion_titulo=t.publicacion.titulo if t.publicacion else None,
                        usuario_id=t.usuario_id,
                        usuario_nombre=u_nombre,
                        usuario_email=u.correo_institucional if u else None,
                        moderador_id=t.moderador_id,
                        moderador_nombre=mod_nombre,
                        asunto=t.asunto,
                        estado=t.estado,
                        prioridad=t.prioridad,
                        creado_en=t.creado_en,
                        actualizado_en=t.actualizado_en,
                        mensajes_count=count,
                        ultimo_mensaje=last_msg,
                    )
                )

            return salida

