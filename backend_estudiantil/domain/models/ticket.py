from datetime import datetime, timezone


class Ticket:
    """Entidad de dominio para la gestión de tickets de revisión y comunicación con el estudiante."""

    ESTADOS_VALIDOS = ("abierto", "en_revision", "esperando_estudiante", "resuelto", "cerrado")
    PRIORIDADES_VALIDAS = ("baja", "media", "alta")

    def __init__(
        self,
        id: int | None = None,
        publicacion_id: int = 0,
        usuario_id: int = 0,
        moderador_id: int | None = None,
        asunto: str = "",
        estado: str = "abierto",
        prioridad: str = "media",
        creado_en: datetime | None = None,
        actualizado_en: datetime | None = None,
    ):
        if not asunto or len(asunto.strip()) < 3:
            raise ValueError("El asunto del ticket debe tener al menos 3 caracteres")
        if estado not in self.ESTADOS_VALIDOS:
            raise ValueError(f"Estado de ticket inválido. Debe ser uno de: {self.ESTADOS_VALIDOS}")
        if prioridad not in self.PRIORIDADES_VALIDAS:
            raise ValueError(f"Prioridad inválida. Debe ser una de: {self.PRIORIDADES_VALIDAS}")

        self.id = id
        self.publicacion_id = publicacion_id
        self.usuario_id = usuario_id
        self.moderador_id = moderador_id
        self.asunto = asunto.strip()
        self.estado = estado
        self.prioridad = prioridad
        self.creado_en = creado_en or datetime.now(timezone.utc)
        self.actualizado_en = actualizado_en or datetime.now(timezone.utc)


class TicketMensaje:
    """Entidad de dominio que representa una intervención/mensaje en el ticket."""

    def __init__(
        self,
        id: int | None = None,
        ticket_id: int = 0,
        remitente_id: int = 0,
        contenido: str = "",
        es_del_sistema: bool = False,
        creado_en: datetime | None = None,
    ):
        if not contenido or not contenido.strip():
            raise ValueError("El contenido del mensaje no puede estar vacío")

        self.id = id
        self.ticket_id = ticket_id
        self.remitente_id = remitente_id
        self.contenido = contenido.strip()
        self.es_del_sistema = es_del_sistema
        self.creado_en = creado_en or datetime.now(timezone.utc)

