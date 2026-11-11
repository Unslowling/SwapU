# SWAPU — Documentación Técnica Final

**Proyecto:** SWAPU — Plataforma de intercambio de libros y material académico entre estudiantes universitarios
**Entrega:** Semana 8 — Proyecto demo final
**Repositorio:** https://github.com/Unslowling/jojual (rama `main`)

---

## 1. Descripción general

SWAPU permite a estudiantes universitarios publicar libros que ya no usan, encontrar los que necesitan, recibir coincidencias automáticas de intercambio, acordar el trueque por chat en tiempo real y calificar la experiencia. Incluye verificación de comunidad (correo institucional y carné), verificación de libros con evidencia fotográfica, moderación, tickets de soporte y auditoría.

## 2. Arquitectura

Arquitectura **hexagonal (puertos y adaptadores)**:

```
frontend/ (HTML + JS + CSS)  ──HTTP/WebSocket──►  FastAPI (infrastructure/api)
                                                     │
                                         domain/ (modelos y servicios de negocio)
                                                     │
                              ports/ (interfaces) ◄── adapters/ (SQLAlchemy, SMTP, JWT, OAuth)
                                                     │
                                         PostgreSQL 17 (producción) / SQLite (pruebas)
```

| Capa | Carpeta | Responsabilidad |
|---|---|---|
| Presentación | `frontend/` | Interfaz web (SPA en JavaScript), servida por el mismo FastAPI |
| API | `backend_estudiantil/infrastructure/api/` | Routers REST y WebSocket |
| Dominio | `backend_estudiantil/domain/` | Reglas de negocio: trueques, matching, reputación, sanciones |
| Puertos | `backend_estudiantil/ports/` | Interfaces de repositorios, correo y autenticación |
| Adaptadores | `backend_estudiantil/adapters/` | ORM SQLAlchemy, SMTP, JWT, bcrypt, Google/Facebook OAuth |
| Transversal | `backend_estudiantil/infrastructure/` | Auditoría 5W, cabeceras de seguridad, límites de intentos, IA |

## 3. Tecnologías

| Componente | Tecnología |
|---|---|
| Backend | Python 3.11, FastAPI 0.110, Pydantic 2.7, SQLAlchemy 2.0 asíncrono |
| Base de datos | PostgreSQL 17 (`asyncpg`); SQLite (`aiosqlite`) solo para pruebas |
| Migraciones | Alembic |
| Seguridad | JWT (PyJWT), bcrypt, SlowAPI, cabeceras CSP/HSTS |
| Tiempo real | WebSocket nativo de FastAPI; Redis opcional con respaldo en memoria |
| Frontend | HTML5, JavaScript, CSS |
| Métricas | Prometheus (`/metrics`) |
| Pruebas | Pytest, pytest-asyncio, HTTPX, Ruff |

## 4. Módulos funcionales

| Módulo | Funcionalidad | Router |
|---|---|---|
| Autenticación | Registro, login, refresh, logout, confirmación de correo por código | `auth_router.py` |
| OAuth | Google y Facebook (se activan con variables de entorno) | `google_oauth_router.py`, `facebook_oauth_router.py` |
| Usuarios y perfil | Perfil propio, perfil público, verificación de carné | `users_router.py` |
| Publicaciones | Crear, editar, eliminar, catálogo con búsqueda y filtros | `publicaciones_router.py` |
| Verificación de libros | Desafío con código, evidencias fotográficas, revisión humana, IA opcional | `verificaciones_router.py` |
| Matching | Coincidencias exactas y similares con ponderación | `matches_router.py` |
| Trueques | Proponer, confirmar, rechazar, completar | `trueques_router.py` |
| Chat | Mensajes en tiempo real (WebSocket) e historial (REST) | `chat_router.py` |
| Calificaciones | Calificar trueques completados, reportar reseñas, reputación bayesiana | `calificaciones_router.py` |
| Tickets | Soporte y revisión asociada a publicaciones | `tickets_router.py` |
| Moderación | Reportes, advertencias, sanciones, apelaciones | `moderacion_router.py` |
| Administración | Promoción de roles, auditoría y estadísticas | `admin_router.py` |
| Catálogo académico | Facultades y programas | `catalogo_router.py` |
| Salud | `/health`, `/health/db`, `/metrics` | `main.py` |

La documentación interactiva de todos los endpoints está en **`/docs`** (Swagger) con el servidor en ejecución.

## 5. Reglas de negocio principales

- **Ciclo del trueque:** `propuesto → confirmado → completado`, o `propuesto/confirmado → rechazado`. Solo el receptor confirma; un trueque no puede completarse sin confirmación ni después de rechazado.
- **Chat:** abierto durante `propuesto` y `confirmado`; cerrado al rechazar o completar. Solo los participantes acceden.
- **Calificación:** solo sobre trueques completados y una sola vez por participante.
- **Publicaciones:** nacen `inactiva` y aparecen en el catálogo tras aprobarse la verificación del libro. Límite de publicaciones activas según el nivel de verificación del estudiante.
- **Verificación de libros:** el estudiante fotografía el libro con un código de desafío. Si la IA no está disponible o no es concluyente, la publicación pasa a **revisión humana**; la IA nunca aprueba sin evidencia.
- **Cuentas institucionales:** deben confirmar el correo con un código de 6 dígitos (vigencia 30 min, máximo 5 intentos) antes de operar. Las cuentas con correo general pueden operar sin verificación de comunidad.
- **Roles:** `usuario`, `moderador`, `administrador`. El registro público siempre crea `usuario`.
- **Sanciones:** advertencias acumuladas en una ventana de 90 días escalan a suspensión; las suspensiones pueden apelarse una vez.

## 6. Modelo de datos

16 tablas definidas en `backend_estudiantil/adapters/db/__init__.py`:

| Grupo | Tablas |
|---|---|
| Núcleo | `usuarios`, `categorias`, `publicaciones`, `verificaciones_publicacion` |
| Intercambio | `matches`, `trueques`, `mensajes`, `calificaciones` |
| Gobierno | `auditorias`, `reportes`, `advertencias`, `sanciones`, `apelaciones`, `organizaciones` |
| Soporte | `tickets_revision`, `ticket_mensajes` |

Tipos ENUM: `rol_enum`, `estado_cuenta_enum`, `estado_publicacion_enum`, `tipo_match_enum`, `estado_trueque_enum`, `tipo_usuario_enum`.

Para comparar la base real con los modelos (solo lectura): `python scripts/comparar_esquema.py`.

## 7. Seguridad

| Control | Implementación |
|---|---|
| Contraseñas | bcrypt; mínimo 8 caracteres |
| Sesión | JWT de acceso (30 min) + refresh en cookie HttpOnly (7 días) |
| Control de acceso | Roles por endpoint; verificación de participante en trueques, chat y tickets (prevención de IDOR) |
| Escalada de privilegios | El registro no acepta roles; los administradores se crean con `scripts/crear_administrador.py` |
| Fuerza bruta | 5 intentos/min por IP+correo, bloqueo de 15 min tras 5 fallos, 30 intentos/min por IP |
| Códigos de confirmación | Guardados como hash SHA-256; nunca se escriben en logs de producción |
| Archivos | Validación por tamaño, *magic bytes* e inspección PIL; nombres aleatorios y rutas seguras |
| Cabeceras | CSP, HSTS, X-Frame-Options, X-Content-Type-Options |
| CORS | Lista explícita de orígenes; nunca `*` con credenciales |
| Auditoría | Middleware 5W (quién, qué, cuándo, dónde, por qué) sin guardar contenido sensible |
| Configuración | Secretos solo en variables de entorno; en producción se rechaza la clave JWT por defecto |

## 8. Configuración (variables de entorno)

Archivo `jojual/.env` (nunca se sube al repositorio). Plantilla: `backend_estudiantil/.env.example`.

| Variable | Uso |
|---|---|
| `ENV` | `dev`, `test` o `prod` |
| `DATABASE_URL` | `postgresql+asyncpg://usuario:contraseña@localhost:5432/swapu` |
| `JWT_SECRET_KEY` | Clave aleatoria de al menos 32 caracteres |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | Envío de códigos de confirmación |
| `APP_BASE_URL` | URL pública de la aplicación |
| `CONFIRMACION_CORREO_OBLIGATORIA` | `true` por defecto |
| `LOGIN_MAX_POR_IP_MINUTO` | `30` por defecto |
| `GOOGLE_CLIENT_ID/SECRET`, `FACEBOOK_CLIENT_ID/SECRET` | OAuth (opcional) |
| `REDIS_URL` | Opcional; vacío usa memoria local |
| `COOKIE_SECURE` | `true` en producción con HTTPS |

## 9. Ejecución local (Windows, sin Docker)

```powershell
cd C:\Users\jotma\Desktop\juliana\jojual
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend_estudiantil\requirements-deploy.txt
# Crear .env con DATABASE_URL y JWT_SECRET_KEY
.\.venv\Scripts\python.exe -m uvicorn backend_estudiantil.infrastructure.main:app --port 8000
```

- Aplicación: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Salud: http://localhost:8000/health y http://localhost:8000/health/db

Crear el primer administrador (el usuario debe estar registrado y confirmado):

```powershell
.\.venv\Scripts\python.exe scripts\crear_administrador.py correo@usbmed.edu.co
```

## 10. Pruebas y control de calidad

```powershell
$env:ENV="dev"; $env:JWT_SECRET_KEY="clave_de_prueba_local_12345678901234567890"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

Las pruebas usan SQLite temporal aislado; `conftest.py` bloquea cualquier conexión a PostgreSQL.

| Verificación | Resultado |
|---|---|
| Pruebas automatizadas (unitarias + integración) | **99 aprobadas** |
| Análisis estático (Ruff) | Sin errores |
| Recorrido end-to-end por HTTP (registro, confirmación, verificación, catálogo, trueque, chat, calificación, permisos) | 35 comprobaciones aprobadas |
| Recorrido en navegador real (Chrome) | Registro, confirmación, publicación, propuesta, confirmación, chat WebSocket, cierre y calificación aprobados, sin errores de JavaScript |

Pruebas de seguridad incluidas: escalada de privilegios en registro, acceso a recursos ajenos (chat, trueques), tokens inválidos, transiciones inválidas, cuentas sin confirmar, ISBN inválidos y límites de intentos.

## 11. Correcciones de la fase final

| Hallazgo | Corrección |
|---|---|
| Cualquier persona podía registrarse como administrador | El registro siempre crea `usuario` |
| Un trueque podía completarse sin confirmación | Transición restringida a `confirmado → completado` |
| Código incorrecto aceptado en cuentas ya confirmadas | Validación obligatoria del código |
| Cuentas institucionales sin confirmar podían operar | Bloqueo hasta confirmar; confirmación integrada en login y registro |
| Códigos de confirmación en logs de producción | Solo en desarrollo |
| Frontend con datos simulados y guardado local falso | Todos los datos provienen del backend |
| URL de la API fija en `localhost:8000` | Se usa el mismo origen que sirve la página |
| Pool de conexiones nuevo en cada petición con PostgreSQL | Reutilización del motor |
| Límite de 5 logins por minuto por IP (bloqueaba campus con NAT) | 30 por IP; 5 por IP+correo |

## 12. Despliegue

Configuración lista para **Render** (plan gratuito, sin Docker) con PostgreSQL en **Neon**: ver `render.yaml` y `docs/despliegue_gratuito.md`.

## 13. Limitaciones conocidas y trabajo futuro

- **Verificación con IA:** requiere `torch`/`torchvision` y `easyocr` (no incluidos por tamaño). Sin ellos, toda verificación pasa a revisión humana.
- **Almacenamiento de fotos:** en disco local. En servidores con disco efímero se recomienda almacenamiento de objetos (S3, Cloudinary).
- **Correo:** sin SMTP configurado, los códigos de confirmación no llegan en producción.
- **OAuth:** Google y Facebook requieren credenciales de cada proveedor.
- **Redis:** sin él, el chat funciona en una sola instancia.
