from datetime import datetime, timezone


class User:
    """Entidad de dominio que representa a un usuario / estudiante en la plataforma de trueque."""

    def __init__(
        self,
        id: int | None = None,
        nombre: str = "",
        apellido: str | None = None,
        correo_institucional: str = "",
        password_hash: str = "",
        tipo_usuario: str = "estudiante",
        programa_area: str | None = None,
        rol: str = "usuario",
        verificado_comunidad: bool = False,
        estado_cuenta: str = "activo",
        fecha_registro: datetime | None = None,
        # Campos de perfil de usuario
        telefono: str | None = None,
        universidad: str | None = None,
        semestre: int | None = None,
        foto_url: str | None = None,
        carnet_path: str | None = None,
        carnet_estado: str | None = None,
        carnet_rechazo_motivo: str | None = None,
        perfil_completo: bool = False,
        codigo_confirmacion: str | None = None,
        codigo_confirmacion_expira: datetime | None = None,
        codigo_confirmacion_intentos: int = 0,
        correo_confirmado: bool = False,
        facultad: str | None = None,
        organizacion_id: int | None = None,
        fin_suspension: datetime | None = None,
        motivo_sancion: str | None = None,
        # Argumentos compatibles con llamadas anteriores
        email: str | None = None,
        hashed_password: str | None = None,
        name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        carrera: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.correo_institucional = correo_institucional or email or ""
        self.password_hash = password_hash or hashed_password or ""
        
        # Mapeo de nombre
        if name and not nombre:
            partes = name.split(" ", 1)
            self.nombre = partes[0]
            self.apellido = partes[1] if len(partes) > 1 else (apellido or "")
        else:
            self.nombre = nombre
            self.apellido = apellido or ""

        self.tipo_usuario = tipo_usuario
        self.programa_area = programa_area or carrera
        self.rol = rol if rol != "usuario" else (role or "usuario")
        self.verificado_comunidad = verificado_comunidad
        self.estado_cuenta = estado_cuenta if is_active is None else ("activo" if is_active else "bloqueado")
        self.fecha_registro = fecha_registro or created_at or datetime.now(timezone.utc)
        self.telefono = telefono
        self.universidad = universidad
        self.semestre = semestre
        self.foto_url = foto_url
        self.carnet_path = carnet_path
        self.carnet_estado = carnet_estado
        self.carnet_rechazo_motivo = carnet_rechazo_motivo
        self.perfil_completo = perfil_completo
        self.codigo_confirmacion = codigo_confirmacion
        self.codigo_confirmacion_expira = codigo_confirmacion_expira
        self.codigo_confirmacion_intentos = codigo_confirmacion_intentos
        self.correo_confirmado = correo_confirmado
        self.facultad = facultad
        self.organizacion_id = organizacion_id
        self.fin_suspension = fin_suspension
        self.motivo_sancion = motivo_sancion

    # Propiedades de compatibilidad
    @property
    def email(self) -> str:
        return self.correo_institucional

    @email.setter
    def email(self, value: str):
        self.correo_institucional = value

    @property
    def name(self) -> str:
        return f"{self.nombre} {self.apellido}".strip() if self.apellido else self.nombre

    @name.setter
    def name(self, value: str):
        partes = (value or "").split(" ", 1)
        self.nombre = partes[0]
        self.apellido = partes[1] if len(partes) > 1 else ""

    @property
    def hashed_password(self) -> str:
        return self.password_hash

    @hashed_password.setter
    def hashed_password(self, value: str):
        self.password_hash = value

    @property
    def role(self) -> str:
        return self.rol

    @role.setter
    def role(self, value: str):
        self.rol = value

    @property
    def is_active(self) -> bool:
        return self.estado_cuenta == "activo"

    @is_active.setter
    def is_active(self, value: bool):
        self.estado_cuenta = "activo" if value else "bloqueado"

    @property
    def carrera(self) -> str | None:
        return self.programa_area

    @carrera.setter
    def carrera(self, value: str | None):
        self.programa_area = value

    @property
    def created_at(self) -> datetime:
        return self.fecha_registro

    @property
    def updated_at(self) -> datetime:
        return self.fecha_registro
