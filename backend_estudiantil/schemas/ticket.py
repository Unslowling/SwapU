from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class TicketCreate(BaseModel):
    publicacion_id: int = Field(..., description="ID de la publicación/libro asociado al ticket")
    asunto: str = Field(..., min_length=3, max_length=200, description="Asunto o motivo de la revisión")
    mensaje_inicial: str = Field(..., min_length=3, max_length=2000, description="Primer mensaje para el estudiante o revisor")
    prioridad: Literal["baja", "media", "alta"] = Field("media", description="Prioridad del ticket")


class TicketMensajeCreate(BaseModel):
    contenido: str = Field(..., min_length=1, max_length=2000, description="Contenido de la respuesta")


class TicketEstadoUpdate(BaseModel):
    estado: Literal["abierto", "en_revision", "esperando_estudiante", "resuelto", "cerrado"] = Field(
        ..., description="Nuevo estado del ticket"
    )


class TicketMensajeRead(BaseModel):
    id: int
    ticket_id: int
    remitente_id: int
    remitente_nombre: str | None = None
    remitente_rol: str | None = None
    contenido: str
    es_del_sistema: bool = False
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class TicketRead(BaseModel):
    id: int
    publicacion_id: int
    publicacion_titulo: str | None = None
    usuario_id: int
    usuario_nombre: str | None = None
    usuario_email: str | None = None
    moderador_id: int | None = None
    moderador_nombre: str | None = None
    asunto: str
    estado: str
    prioridad: str
    creado_en: datetime
    actualizado_en: datetime
    mensajes_count: int = 0
    ultimo_mensaje: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TicketDetalleRead(TicketRead):
    mensajes: list[TicketMensajeRead] = []

