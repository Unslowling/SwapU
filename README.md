# Plataforma de Trueque Estudiantil – Backend

Este repositorio contiene la API backend de la **Plataforma de Trueque Estudiantil**, desarrollada con **FastAPI**, **SQLAlchemy Async**, **PostgreSQL** (con soporte para SQLite local) bajo una **Arquitectura Hexagonal**.

Permite el registro e inicio de sesión de estudiantes universitarios, gestión de perfiles, autenticación robusta mediante tokens JWT y refresh tokens en cookies HttpOnly seguras, y hashing criptográfico con **bcrypt**.

---

## 🛠️ Características Principales

- **Arquitectura Hexagonal**: Separación limpia entre Dominio, Puertos, Adaptadores e Infraestructura.
- **Base de Datos Visible y Flexible**: Configuración directa mediante la variable de entorno `DATABASE_URL` (PostgreSQL asíncrono vía `asyncpg` o SQLite vía `aiosqlite`).
- **Nomenclatura en Español**: Tabla `usuarios` con campos académicos y de contacto (`carrera`, `universidad`, `telefono`, `is_active`, `created_at`, `updated_at`).
- **Autenticación y Seguridad**:
  - Hashing seguro de contraseñas con **bcrypt**.
  - Emisión de **Access Token JWT** con identificador único RFC 7519 (`jti`).
  - **Refresh Token** almacenado en cookies `HttpOnly` y `SameSite`.
  - Endpoint para cierre seguro de sesión (`/auth/logout`).
  - Soporte integrado para **Google OAuth2**.
- **Gestión de Perfiles y Usuarios**:
  - `GET /usuarios/me` y `PUT /usuarios/me` para consulta y edición de perfil propio.
  - CRUD administrativo con control de roles (`admin`, `moderador`, `user`).
  - Endpoint para verificación de salud de la base de datos (`GET /health/db`).
- **Migraciones con Alembic**: Migraciones `1975ea83b712_crear_tabla_usuarios.py` y `3c4d92f18a70_agregar_rol_moderador.py`.
- **Suite de Pruebas Automatizadas**: 100% en verde con `pytest` y `httpx`.

---

## 📋 Requisitos

- Python 3.12 o superior
- PostgreSQL 14+ (o SQLite local para pruebas rápidas)
- Docker y Docker Compose (opcional)

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el repositorio y configurar variables de entorno
```bash
# Copiar archivo de variables de entorno
cp backend_estudiantil/.env.example .env
```

Edita `.env` con la cadena de conexión de tu base de datos:
```env
# Conexión a PostgreSQL:
DATABASE_URL=postgresql+asyncpg://<usuario>:<contraseña>@localhost:5432/swapu

# O si deseas usar SQLite local para desarrollo sin levantar Postgres:
# DATABASE_URL=sqlite+aiosqlite:///./trueque_estudiantil.db

COOKIE_SECURE=False
JWT_SECRET_KEY=MySuperSecretKey1234567890!@#$%^&*()_+

# Acceso social opcional: deja vacíos estos valores si no habilitarás el proveedor
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
TWITTER_CLIENT_ID=
TWITTER_CLIENT_SECRET=
TWITTER_REDIRECT_URI=http://localhost:8000/auth/twitter/callback
```

Para habilitar Google o X, crea una aplicación OAuth en la consola del proveedor, configura el callback exactamente igual a la URL `*_REDIRECT_URI` y copia el ID/secret al archivo `.env` del backend (no al frontend ni al repositorio). En Google, agrega las cuentas que probarán el login como usuarios de prueba mientras la pantalla de consentimiento esté en modo de pruebas. Si faltan credenciales, el backend responderá explícitamente que ese proveedor no está configurado.

### 2. Instalar dependencias
```bash
pip install -r backend_estudiantil/requirements.txt
```

### 3. Ejecutar la API
```bash
uvicorn backend_estudiantil.infrastructure.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📖 Documentación Interactiva

- **Swagger UI**: <http://localhost:8000/docs>
- **ReDoc**: <http://localhost:8000/redoc>
- **Health Check General**: <http://localhost:8000/health>
- **Health Check Base de Datos**: <http://localhost:8000/health/db>

---

## 📌 Catálogo de Endpoints

### 🔐 Autenticación (`/auth`)
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/auth/register` | Registro de nuevo estudiante |
| `POST` | `/auth/login` | Login con credenciales (emite JWT y cookie HttpOnly) |
| `POST` | `/auth/refresh` | Renovación de Access Token mediante cookie |
| `POST` | `/auth/logout` | Cierre de sesión y revocación de cookie |
| `GET` | `/auth/google/login` | URL para inicio de sesión federado con Google |
| `GET` | `/auth/google/callback` | Callback de Google OAuth2 |

### 👤 Usuarios y Perfiles (`/usuarios`)
| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/usuarios/me` | Consulta del perfil del estudiante autenticado |
| `PUT` | `/usuarios/me` | Actualización de perfil propio (nombre, carrera, teléfono) |
| `GET` | `/usuarios/` | Listado paginado de usuarios (requiere autenticación) |
| `GET` | `/usuarios/{user_id}` | Detalle de un usuario específico |
| `POST` | `/usuarios/` | Creación de usuario (rol admin) |
| `PUT` | `/usuarios/{user_id}` | Actualización de usuario (propio o admin) |
| `DELETE` | `/usuarios/{user_id}` | Eliminación de usuario (rol admin) |

### 🛡️ Administración (`/admin`)
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/admin/users/{user_id}/promote` | Promover usuario a rol moderador |

### 📚 Publicaciones, trueques y conversaciones
| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/publicaciones/` | Registrar un libro pendiente de verificación (requiere sesión y categoría válida) |
| `GET` | `/publicaciones/mis-publicaciones` | Listar los libros del usuario autenticado |
| `POST` | `/publicaciones/{id}/verificacion/desafios` | Generar el código temporal para fotografiar portada y página ISBN |
| `POST` | `/publicaciones/{id}/verificacion/evidencias` | Subir evidencia fotográfica privada |
| `GET` | `/publicaciones/verificaciones/pendientes` | Consultar la cola de revisión (admin/moderador) |
| `POST` | `/publicaciones/verificaciones/{id}/revision` | Aprobar o rechazar evidencia (admin/moderador) |
| `POST` | `/trueques/` o `/trueques/proponer` | Proponer un trueque entre dos publicaciones activas; la publicación ofrecida debe pertenecer al usuario |
| `GET` | `/trueques/mis-trueques` | Listar trueques propios con participantes y libros asociados |
| `GET` | `/trueques/{id}/mensajes` | Consultar el historial privado de la conversación |
| `POST` | `/trueques/{id}/mensajes` | Enviar un mensaje (máximo 2.000 caracteres) |
| `WS` | `/trueques/{id}/ws` | Recibir mensajes en tiempo real como participante autenticado |
| `POST` | `/trueques/{id}/confirmar`, `/completar`, `/rechazar` | Avanzar o cerrar el ciclo del intercambio |

Las categorías iniciales de libros se crean al iniciar la API. Cada libro nuevo queda oculto hasta que el dueño suba fotos de portada y de la página del ISBN con un código temporal visible. Al enviar la evidencia, un pipeline de IA automático (MobileNetV3 + EasyOCR) clasifica la imagen y busca el código de desafío; si ambas capas aprueban, la publicación se activa de inmediato. Si la IA rechaza, la evidencia queda en cola para revisión manual por admins o moderadores. Cuando las librerías de IA no están instaladas, torch y easyocr se importan de forma diferida y fallan silenciosamente: el módulo carga con normalidad pero la IA siempre rechaza (no puede leer el código), derivando toda verificación a revisión humana de forma transparente. En la primera ejecución con IA habilitada se descargan automáticamente los pesos del modelo (~20 MB) y los modelos de idioma de EasyOCR, por lo que se requiere conexión a internet esa primera vez. Las fotos se guardan privadas, se eliminan sus metadatos EXIF y no se usa biometría. El código de desafío ayuda a evitar fotos recicladas, pero no demuestra por sí solo que un libro sea genuino.

La conversación queda disponible durante la propuesta y confirmación; se cierra al rechazar o completar el trueque. El historial se consulta en páginas de hasta 100 mensajes. Redis distribuye los mensajes entre réplicas; `docker compose up --build` levanta Redis y persiste las evidencias fotográficas junto a PostgreSQL. Para varias máquinas, sustituye el almacenamiento local por almacenamiento de objetos privado compartido.

---

## 🧪 Ejecución de Pruebas Automatizadas

Para ejecutar todas las pruebas unitarias y de integración:
```bash
pytest -v
```

---

## 🐳 Despliegue con Docker

```bash
docker compose up --build
```
Esto levantará el contenedor de la API en el puerto `8000` junto con una instancia de PostgreSQL en el puerto `5432`.
