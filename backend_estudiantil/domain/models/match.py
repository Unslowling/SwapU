from datetime import datetime, timezone


class Match:
    """Entidad de dominio que representa una coincidencia identificada por el motor de matching."""

    def __init__(
        self,
        id: int | None = None,
        publicacion_origen_id: int = 0,
        publicacion_destino_id: int = 0,
        tipo_match: str = "exacta",
        puntuacion: float = 100.0,
        fecha_creacion: datetime | None = None,
    ):
        self.id = id
        self.publicacion_origen_id = publicacion_origen_id
        self.publicacion_destino_id = publicacion_destino_id
        self.tipo_match = tipo_match
        self.puntuacion = float(puntuacion)
        self.fecha_creacion = fecha_creacion or datetime.now(timezone.utc)
