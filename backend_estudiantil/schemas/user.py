
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="Correo electrónico del usuario")
    name: str | None = Field(None, description="Nombre completo del estudiante")
    telefono: str | None = Field(None, description="Número de teléfono o WhatsApp de contacto")
    carrera: str | None = Field(None, description="Carrera o programa académico")
    facultad: str | None = Field(None, description="Facultad académica del estudiante")
    universidad: str | None = Field(None, description="Universidad o campus del estudiante")
    semestre: int | None = Field(None, description="Semestre académico actual")
    foto_url: str | None = Field(None, description="URL pública del avatar o foto de perfil")

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Contraseña de acceso (mínimo 6 caracteres)")
    role: str | None = Field(default="user", description="Rol del usuario ('admin', 'moderador', 'user')")

class UserUpdate(BaseModel):
    email: EmailStr | None = None
    name: str | None = None
    password: str | None = Field(None, min_length=6)
    telefono: str | None = None
    carrera: str | None = None
    facultad: str | None = None
    universidad: str | None = None
    semestre: int | None = None
    foto_url: str | None = None
    perfil_completo: bool | None = None

class RechazoCarnetRequest(BaseModel):
    motivo: str | None = Field(
        default="Documento no legible o no coincide con los datos del usuario",
        description="Motivo del rechazo de la solicitud de carné"
    )

class UserRead(UserBase):
    id: str
    role: str = Field(default="user", description="Rol asignado al usuario")
    is_active: bool = Field(default=True, description="Estado de la cuenta")
    verificado_comunidad: bool = Field(default=False, description="Verificación institucional del estudiante")
    insignia_estudiante_verificado: bool = Field(default=False, description="Distintivo de Estudiante Verificado")
    carnet_estado: str | None = Field(default=None, description="Estado del carné: sin_verificar, en_revision, rechazado, verificado")
    carnet_rechazo_motivo: str | None = Field(default=None, description="Motivo de rechazo de carné si aplica")
    perfil_completo: bool = Field(default=False, description="Indica si el usuario completó su información de perfil")
    reputacion_nivel: str | None = Field(default="nuevo", description="Nivel de reputación: nuevo, confiable o destacado")
    reputacion_promedio: float | None = Field(default=None, description="Promedio bayesiano de estrellas")
    organizacion_id: int | None = Field(default=None, description="ID de la organización/universidad asignada")
    estado_cuenta: str | None = Field(default="activo", description="Estado de la cuenta: activo, suspendido, bloqueado")
    fin_suspension: str | None = Field(default=None, description="Fecha de fin de suspensión ISO 8601")
    motivo_sancion: str | None = Field(default=None, description="Motivo de la sanción activa si aplica")
    created_at: str = Field(..., description="Fecha de creación ISO 8601")
    updated_at: str = Field(..., description="Fecha de última actualización ISO 8601")

    model_config = ConfigDict(from_attributes=True)
