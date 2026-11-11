from datetime import datetime, timezone


class Trueque:
    """Entidad de dominio que gestiona el estado y ciclo de vida de un intercambio de libros."""

    def __init__(
        self,
        id: int | None = None,
        match_id: int | None = None,
        usuario_propone_id: int = 0,
        usuario_recibe_id: int = 0,
        estado: str = "propuesto",
        fecha_propuesta: datetime | None = None,
        fecha_confirmacion: datetime | None = None,
        fecha_completado: datetime | None = None,
    ):
        self.id = id
        self.match_id = match_id
        self.usuario_propone_id = usuario_propone_id
        self.usuario_recibe_id = usuario_recibe_id
        self.estado = estado
        self.fecha_propuesta = fecha_propuesta or datetime.now(timezone.utc)
        self.fecha_confirmacion = fecha_confirmacion
        self.fecha_completado = fecha_completado

    def confirmar(self):
        if self.estado != "propuesto":
            raise ValueError(f"No se puede confirmar un trueque en estado '{self.estado}'")
        self.estado = "confirmado"
        self.fecha_confirmacion = datetime.utcnow()

    def completar(self):
        # Solo se completa un trueque confirmado por el receptor (no se puede saltar la confirmación)
        if self.estado != "confirmado":
            raise ValueError(f"No se puede completar un trueque en estado '{self.estado}'")
        self.estado = "completado"
        self.fecha_completado = datetime.utcnow()

    def rechazar(self):
        if self.estado == "completado":
            raise ValueError("Un trueque completado no puede ser rechazado")
        self.estado = "rechazado"
