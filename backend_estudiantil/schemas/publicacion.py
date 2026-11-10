from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicacionBase(BaseModel):
    titulo: str = Field(..., description="Título del libro o material académico")
    autor: str | None = Field(None, description="Autor del libro")
    isbn: str | None = Field(None, description="ISBN del libro (si aplica)")
    edicion: str | None = Field(None, description="Edición del libro")
    categoria_id: int | None = Field(None, description="ID de la categoría académica")
    estado_libro: str | None = Field(None, description="Estado físico del libro (Nuevo, Buen estado, Regular, etc.)")
    descripcion: str | None = Field(None, description="Descripción detallada de la publicación")
    libro_buscado: str | None = Field(None, description="Nombre del libro que se busca a cambio")
    tipo_transaccion: str | None = Field("trueque", description="Tipo de transacción: trueque, prestamo o donacion")
    fecha_devolucion: datetime | None = Field(None, description="Fecha máxima de devolución para préstamos")
    organizacion_id: int | None = Field(None, description="ID de la organización asociada")


class PublicacionCreate(PublicacionBase):
    pass


class PublicacionUpdate(BaseModel):
    titulo: str | None = None
    autor: str | None = None
    isbn: str | None = None
    edicion: str | None = None
    categoria_id: int | None = None
    estado_libro: str | None = None
    descripcion: str | None = None
    libro_buscado: str | None = None
    tipo_transaccion: str | None = None
    fecha_devolucion: datetime | None = None
    organizacion_id: int | None = None


class PublicacionRead(PublicacionBase):
    id: int
    usuario_id: int
    estado_publicacion: str
    fecha_publicacion: datetime | None = None
    usuario_nombre: str | None = None
    usuario_carrera: str | None = None
    usuario_universidad: str | None = None
    usuario_avatar: str | None = None
    categoria_nombre: str | None = None

    model_config = ConfigDict(from_attributes=True)


class CategoriaRead(BaseModel):
    id: int
    nombre: str

    model_config = ConfigDict(from_attributes=True)
