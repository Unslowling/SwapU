import json
from pathlib import Path

# pyrefly: ignore [missing-import]
from pydantic import ConfigDict, Field, model_validator

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings

ROOT_DIR = Path(__file__).resolve().parents[2]
ROOT_ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Configuración global de la aplicación Trueque Estudiantil."""

    ENV: str = Field(
        default="dev",
        validation_alias="ENV",
        description="Entorno de ejecución: dev, test, staging, prod",
    )

    # Configuración de Base de Datos (credenciales leídas exclusivamente de .env)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://localhost:5432/swapu",
        validation_alias="DATABASE_URL",
        description="Cadena de conexión para SQLAlchemy Async (PostgreSQL o SQLite)",
    )

    CORS_ORIGINS: list[str] | str = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:5500",
            "http://127.0.0.1:5500",
        ],
        validation_alias="CORS_ORIGINS",
        description="Lista de orígenes permitidos para CORS",
    )

    BOOK_VERIFICATION_STORAGE_PATH: str = Field(
        default="./storage/book-verification",
        validation_alias="BOOK_VERIFICATION_STORAGE_PATH",
        description="Directorio privado para fotos de verificación de publicaciones",
    )

    def get_database_url(self) -> str:
        """Obtiene la URL activa de conexión a base de datos."""
        return self.DATABASE_URL

    def get_cors_origins(self) -> list[str]:
        """Parsea y retorna la lista limpia de orígenes CORS permitidos."""
        if isinstance(self.CORS_ORIGINS, str):
            try:
                parsed = json.loads(self.CORS_ORIGINS)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                return [item.strip() for item in self.CORS_ORIGINS.split(",") if item.strip()]
        elif isinstance(self.CORS_ORIGINS, list):
            return [str(item).strip() for item in self.CORS_ORIGINS if str(item).strip()]
        return ["http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:8000"]

    # JWT settings
    JWT_SECRET_KEY: str = Field(default="MySuperSecretKey1234567890!@#$%^&*()_+", validation_alias="JWT_SECRET_KEY")
    JWT_ALGORITHM: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, validation_alias="REFRESH_TOKEN_EXPIRE_DAYS")

    # Cookie settings
    COOKIE_SECURE: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    COOKIE_HTTPONLY: bool = Field(default=True, validation_alias="COOKIE_HTTPONLY")
    COOKIE_SAMESITE: str = Field(default="lax", validation_alias="COOKIE_SAMESITE")

    # Google OAuth2 settings
    GOOGLE_CLIENT_ID: str = Field(default="", validation_alias="GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = Field(default="", validation_alias="GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/google/callback",
        validation_alias="GOOGLE_REDIRECT_URI",
    )
    GOOGLE_SCOPES: str = Field(default="openid email profile", validation_alias="GOOGLE_SCOPES")

    # Facebook OAuth2 settings
    FACEBOOK_CLIENT_ID: str = Field(default="", validation_alias="FACEBOOK_CLIENT_ID")
    FACEBOOK_CLIENT_SECRET: str = Field(default="", validation_alias="FACEBOOK_CLIENT_SECRET")
    FACEBOOK_REDIRECT_URI: str = Field(
        default="http://localhost:8000/auth/facebook/callback",
        validation_alias="FACEBOOK_REDIRECT_URI",
    )
    FACEBOOK_SCOPES: str = Field(default="email,public_profile", validation_alias="FACEBOOK_SCOPES")


    # Verificación de comunidad y dominios institucionales
    DOMINIOS_INSTITUCIONALES: dict[str, str] = Field(
        default={
            "tau.usbmed.edu.co": "Universidad de San Buenaventura Medellín",
            "usbmed.edu.co": "Universidad de San Buenaventura Medellín",
            "sanbuenaventura.edu.co": "Universidad de San Buenaventura",
            "unal.edu.co": "Universidad Nacional de Colombia",
            "udea.edu.co": "Universidad de Antioquia",
            "uniandes.edu.co": "Universidad de los Andes",
            "javeriana.edu.co": "Pontificia Universidad Javeriana",
            "univalle.edu.co": "Universidad del Valle",
            "udistrital.edu.co": "Universidad Distrital Francisco José de Caldas",
            "uis.edu.co": "Universidad Industrial de Santander",
            "uninpahu.edu.co": "UNINPAHU",
        },
        validation_alias="DOMINIOS_INSTITUCIONALES",
        description="Mapeo de dominios de correos institucionales a nombres de universidad",
    )

    # Límites de publicaciones activas por nivel de verificación
    LIMITE_PUBLICACIONES_SIN_VERIFICAR: int = Field(
        default=3,
        validation_alias="LIMITE_PUBLICACIONES_SIN_VERIFICAR",
        description="Límite máximo de publicaciones activas para estudiantes sin verificar",
    )
    LIMITE_PUBLICACIONES_VERIFICADOS: int = Field(
        default=10,
        validation_alias="LIMITE_PUBLICACIONES_VERIFICADOS",
        description="Límite máximo de publicaciones activas para estudiantes verificados",
    )

    # Confirmación obligatoria del correo institucional antes de operar.
    # Poner en false solo durante una transición (cuentas heredadas sin confirmar).
    CONFIRMACION_CORREO_OBLIGATORIA: bool = Field(
        default=True,
        validation_alias="CONFIRMACION_CORREO_OBLIGATORIA",
        description="Bloquea operaciones de cuentas con correo institucional no confirmado",
    )

    # Límite global de intentos de login por IP y minuto (los campus comparten IP pública).
    LOGIN_MAX_POR_IP_MINUTO: int = Field(
        default=30,
        validation_alias="LOGIN_MAX_POR_IP_MINUTO",
        description="Máximo de intentos de inicio de sesión por IP en un minuto",
    )

    # Configuración de Verificación con IA
    IA_UMBRAL_LIBRO: float = Field(
        default=0.10,
        validation_alias="IA_UMBRAL_LIBRO",
        description="Umbral de confianza mínima (0-1) para considerar una imagen como libro",
    )

    # Configuración de Servidor de Correo SMTP para confirmación
    SMTP_HOST: str = Field(default="", validation_alias="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, validation_alias="SMTP_PORT")
    SMTP_USER: str = Field(default="", validation_alias="SMTP_USER")
    SMTP_PASSWORD: str = Field(default="", validation_alias="SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = Field(default="", validation_alias="SMTP_FROM_EMAIL")
    APP_BASE_URL: str = Field(default="http://localhost:8000", validation_alias="APP_BASE_URL")

    # Pesos de matching para estudiantes verificados
    MATCHING_PESO_MISMA_UNIVERSIDAD: float = Field(
        default=15.0,
        validation_alias="MATCHING_PESO_MISMA_UNIVERSIDAD",
        description="Puntos extra de matching para estudiantes de la misma universidad (ambos verificados)",
    )
    MATCHING_PESO_MISMA_FACULTAD_CARRERA: float = Field(
        default=10.0,
        validation_alias="MATCHING_PESO_MISMA_FACULTAD_CARRERA",
        description="Puntos extra de matching para estudiantes de la misma facultad o carrera (ambos verificados)",
    )
    MATCHING_PESO_SEMESTRE_CERCANO: float = Field(
        default=5.0,
        validation_alias="MATCHING_PESO_SEMESTRE_CERCANO",
        description="Puntos extra de matching para estudiantes con semestre cercano (<= 2 de diferencia, ambos verificados)",
    )

    # Configuración de Reputación Bayesiana
    BAYESIAN_C: float = Field(
        default=5.0,
        validation_alias="BAYESIAN_C",
        description="Constante C de confianza mínima para el cálculo del promedio bayesiano",
    )
    REPUTACION_UMBRAL_DESTACADO: float = Field(
        default=4.5,
        validation_alias="REPUTACION_UMBRAL_DESTACADO",
        description="Umbral mínimo de reputación bayesiana para nivel destacado",
    )
    REPUTACION_MIN_RESENAS_DESTACADO: int = Field(
        default=10,
        validation_alias="REPUTACION_MIN_RESENAS_DESTACADO",
        description="Número mínimo de calificaciones para calificar a nivel destacado",
    )
    REPUTACION_MIN_RESENAS_CONFIABLE: int = Field(
        default=3,
        validation_alias="REPUTACION_MIN_RESENAS_CONFIABLE",
        description="Número mínimo de calificaciones para pasar de nivel nuevo a confiable",
    )

    # Configuración de Sanciones y Moderación
    SANCIONES_VENTANA_DIAS_ADVERTENCIAS: int = Field(
        default=90,
        validation_alias="SANCIONES_VENTANA_DIAS_ADVERTENCIAS",
        description="Ventana en días para contar advertencias activas en la escalera de sanciones",
    )
    SANCIONES_NUM_ADVERTENCIAS_SUSPENSION: int = Field(
        default=3,
        validation_alias="SANCIONES_NUM_ADVERTENCIAS_SUSPENSION",
        description="Cantidad de advertencias acumuladas que desencadenan suspensión",
    )

    # Almacenamiento Redis para rate limit y cache
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
        description="URL de conexión a Redis con respaldo en memoria si no está disponible",
    )

    def es_dominio_institucional(self, email: str) -> bool:
        """Determina si un correo electrónico pertenece a un dominio universitario institucional.
        Divide estrictamente en el '@' y compara dominio exacto o subdominio permitido,
        bloqueando subdominios no registrados cuando la institución tiene dominios específicos.
        """
        if not email or "@" not in email:
            return False
        partes = email.split("@")
        if len(partes) != 2:
            return False
        usuario, dominio = partes[0].strip(), partes[1].strip().lower()
        if not usuario or not dominio:
            return False
        dominios_permitidos = {d.strip().lower() for d in self.DOMINIOS_INSTITUCIONALES.keys()}
        if dominio in dominios_permitidos:
            return True

        for d in dominios_permitidos:
            if dominio.endswith(f".{d}"):
                subdominios_especificos = {sd for sd in dominios_permitidos if sd != d and sd.endswith(f".{d}")}
                if subdominios_especificos:
                    if any(dominio == sd or dominio.endswith(f".{sd}") for sd in subdominios_especificos):
                        return True
                    continue
                return True
        return False

    def obtener_universidad_por_dominio(self, email: str) -> str | None:
        """Retorna el nombre oficial de la universidad asociada al dominio del correo."""
        if not email or "@" not in email:
            return None
        partes = email.split("@")
        if len(partes) != 2:
            return None
        usuario, dominio = partes[0].strip(), partes[1].strip().lower()
        if not usuario or not dominio:
            return None

        # 1. Coincidencia exacta directa
        for d, u in self.DOMINIOS_INSTITUCIONALES.items():
            if dominio == d.strip().lower():
                return u

        # 2. Coincidencia por subdominio autorizado
        for d, u in self.DOMINIOS_INSTITUCIONALES.items():
            d_lower = d.strip().lower()
            if dominio.endswith(f".{d_lower}"):
                subdominios_especificos = {sd for sd in self.DOMINIOS_INSTITUCIONALES if sd != d and sd.endswith(f".{d_lower}")}
                if subdominios_especificos:
                    if any(dominio == sd or dominio.endswith(f".{sd}") for sd in subdominios_especificos):
                        return u
                    continue
                return u
        return None

    def obtener_programas_academicos(self) -> dict[str, list[str]]:
        """Carga la oferta de facultades y programas académicos configurables.
        Por defecto lee backend_estudiantil/config/programas_academicos.json.
        """
        import json
        from pathlib import Path

        json_path = Path(__file__).parent / "programas_academicos.json"
        if json_path.exists():
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "Facultad de Ingenierías": [
                "Ingeniería de Datos y Software",
                "Ingeniería de Sistemas Cibernéticos",
                "Ingeniería de Sonido",
                "Ingeniería Industrial",
                "Ingeniería Ambiental",
                "Ingeniería Electrónica",
                "Ingeniería Multimedia",
                "Creación de Contenidos Digitales",
                "Otra",
            ],
            "Facultad de Ciencias Empresariales": [
                "Administración de Negocios",
                "Contaduría Pública",
                "Negocios Internacionales",
                "Otra",
            ],
            "Facultad de Arquitectura y Artes": [
                "Arquitectura",
                "Diseño Industrial",
                "Otra",
            ],
            "Facultad de Derecho y Ciencias Políticas": [
                "Derecho",
                "Otra",
            ],
            "Facultad de Psicología": [
                "Psicología",
                "Otra",
            ],
            "Facultad de Educación": [
                "Licenciatura en Educación Preescolar",
                "Licenciatura en Educación Artística y Cultural",
                "Licenciatura en Educación Física y Deportes",
                "Licenciatura en Lengua Castellana",
                "Tecnología en Entrenamiento Deportivo",
                "Otra",
            ],
        }

    @model_validator(mode="after")
    def validar_seguridad_entorno(self) -> "Settings":
        entorno = (self.ENV or "dev").strip().lower()
        # Regla 1: si JWT_SECRET_KEY es el valor por defecto o tiene menos de 32 caracteres y ENV != "dev", negarse a arrancar
        if entorno != "dev":
            es_default = self.JWT_SECRET_KEY == "MySuperSecretKey1234567890!@#$%^&*()_+"
            es_corta = len(self.JWT_SECRET_KEY) < 32
            if es_default or es_corta:
                raise ValueError(
                    f"Configuración de seguridad rechazada: En entorno '{self.ENV}', "
                    "JWT_SECRET_KEY no puede ser la clave por defecto y debe tener al menos 32 caracteres."
                )
        # Regla 5: COOKIE_SECURE=true cuando ENV=prod
        if entorno in ("prod", "production"):
            self.COOKIE_SECURE = True

        return self

    model_config = ConfigDict(
        env_file=str(ROOT_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()
