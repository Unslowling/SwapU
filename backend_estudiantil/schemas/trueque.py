from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MatchRead(BaseModel):
    id: int
    publicacion_origen_id: int
    publicacion_destino_id: int
    tipo_match: str = Field(description="Tipo: exacta, similar")
    puntuacion: float = Field(description="Puntuación de coincidencia entre 0 y 100")
    fecha_creacion: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TruequeCreate(BaseModel):
    usuario_recibe_id: int | None = Field(
        None, description="ID del usuario receptor (opcional si se indican publicaciones)"
    )
    match_id: int | None = Field(None, description="ID del match asociado (opcional)")
    publicacion_origen_id: int | None = Field(
        None, gt=0, description="Publicación propia que se ofrece"
    )
    publicacion_destino_id: int | None = Field(
        None, gt=0, description="Publicación activa que se solicita"
    )


class TruequeAccion(BaseModel):
    accion: str = Field(..., description="Acción a ejecutar: confirmar, completar, rechazar")


class TruequeRead(BaseModel):
    id: int
    match_id: int | None = None
    usuario_propone_id: int
    usuario_recibe_id: int
    estado: str
    fecha_propuesta: datetime | None = None
    fecha_confirmacion: datetime | None = None
    fecha_completado: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CalificacionCreate(BaseModel):
    usuario_calificado_id: int = Field(..., description="ID del usuario que se va a calificar")
    estrellas: int = Field(..., ge=1, le=5, description="Calificación de 1 a 5 estrellas")
    resena: str | None = Field(None, max_length=500, description="Reseña opcional del intercambio")


class CalificacionRead(BaseModel):
    id: int
    trueque_id: int
    usuario_califica_id: int
    usuario_calificado_id: int
    estrellas: int
    resena: str | None = None
    fecha_calificacion: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ReputacionRead(BaseModel):
    usuario_id: int
    promedio_estrellas: float | None = None
    promedio_simple: float | None = None
    promedio_bayesiano: float | None = None
    nivel: str = "nuevo"
    total_calificaciones: int
    media_global: float | None = None
    calificaciones: list

    model_config = ConfigDict(from_attributes=True)

