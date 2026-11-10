from datetime import datetime, timezone


class Publicacion:
    """Entidad de dominio que representa un libro o material ofertado o buscado."""

    def __init__(
        self,
        id: int | None = None,
        usuario_id: int = 0,
        titulo: str = "",
        autor: str | None = None,
        isbn: str | None = None,
        edicion: str | None = None,
        categoria_id: int | None = None,
        estado_libro: str | None = None,
        descripcion: str | None = None,
        libro_buscado: str | None = None,
        estado_publicacion: str = "activa",
        fecha_publicacion: datetime | None = None,
        tipo_transaccion: str = "trueque",
        fecha_devolucion: datetime | None = None,
        organizacion_id: int | None = None,
        usuario_nombre: str | None = None,
        usuario_carrera: str | None = None,
        usuario_universidad: str | None = None,
        usuario_avatar: str | None = None,
        categoria_nombre: str | None = None,
    ):
        self.id = id
        self.usuario_id = usuario_id
        self.titulo = titulo
        self.autor = autor
        self.isbn = isbn
        self.edicion = edicion
        self.categoria_id = categoria_id
        self.estado_libro = estado_libro or "Buen estado"
        self.descripcion = descripcion
        self.libro_buscado = libro_buscado
        self.estado_publicacion = estado_publicacion
        self.fecha_publicacion = fecha_publicacion or datetime.now(timezone.utc)
        self.tipo_transaccion = tipo_transaccion or "trueque"
        self.fecha_devolucion = fecha_devolucion
        self.organizacion_id = organizacion_id
        self.usuario_nombre = usuario_nombre
        self.usuario_carrera = usuario_carrera
        self.usuario_universidad = usuario_universidad
        self.usuario_avatar = usuario_avatar
        self.categoria_nombre = categoria_nombre
