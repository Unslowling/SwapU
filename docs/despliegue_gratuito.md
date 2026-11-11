# Despliegue gratuito de SWAPU (Render + Neon)

- **App (backend + frontend):** Render, plan gratuito, sin Docker. Configurado en `render.yaml`.
- **Base de datos:** Neon, PostgreSQL gratuito y sin vencimiento (la base gratuita de Render se borra a los 30 días).

Ninguna credencial va al repositorio: todas se pegan en los paneles de Neon y Render.

## 1. Crear la base en Neon

1. Crear cuenta en https://neon.tech y un proyecto con **PostgreSQL 17**. Región recomendada: `AWS São Paulo (sa-east-1)`.
2. En *Connection Details* copiar dos cadenas:
   - **Directa** (sin `-pooler` en el host): para restaurar la base.
   - **Pooled** (con `-pooler`): para la app en Render.

## 2. Copiar `swapu` local a Neon (esquema y datos)

Antes, comparar el esquema local con los modelos (solo lectura):

```powershell
cd C:\Users\jotma\Desktop\juliana\jojual
.\.venv\Scripts\python.exe scripts\comparar_esquema.py
```

Si faltan tablas que usa la app (tickets, sanciones, reportes, apelaciones, organizaciones…), resolverlo antes de publicar: esas funciones fallarían en producción.

Copia (no modifica la base local; usa las herramientas que trae PostgreSQL 17):

```powershell
$env:PATH += ";C:\Program Files\PostgreSQL\17\bin"
pg_dump --no-owner --no-privileges -Fc -h localhost -U postgres -d swapu -f swapu.dump
pg_restore --no-owner --no-privileges -d "CADENA_DIRECTA_DE_NEON" swapu.dump
```

Borrar `swapu.dump` al terminar: contiene datos personales.

## 3. Publicar en Render

1. Crear cuenta en https://render.com con el usuario de GitHub que tiene acceso a `Unslowling/jojual`.
2. *New → Blueprint* → elegir el repositorio. Render lee `render.yaml`.
3. Completar las variables marcadas como secretas:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | Cadena **pooled** de Neon, tal cual (la app adapta `postgresql://…?sslmode=require`) |
| `APP_BASE_URL` | URL pública que asigne Render, p. ej. `https://swapu.onrender.com` |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | Servidor de correo (ver abajo) |

`JWT_SECRET_KEY` lo genera Render automáticamente.

4. Comprobar: `https://<tu-app>.onrender.com/health` y `/health/db` deben responder `ok` y `conectado`.

### Correo (obligatorio para confirmar cuentas institucionales)

En producción el código **no** se escribe en los logs. Sin SMTP, los estudiantes institucionales no pueden confirmar su cuenta. Opciones gratuitas:

- **Brevo** (300 correos/día): `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`.
- **Gmail** con contraseña de aplicación: `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`.

Mientras no haya SMTP se puede poner `CONFIRMACION_CORREO_OBLIGATORIA=false` (temporal).

## 4. Crear el primer administrador

Registrarse en la app publicada y confirmar el correo. Después, desde el PC local:

```powershell
cd C:\Users\jotma\Desktop\juliana\jojual
$env:DATABASE_URL = "CADENA_DIRECTA_DE_NEON"
.\.venv\Scripts\python.exe scripts\crear_administrador.py tu-correo@usbmed.edu.co
Remove-Item Env:DATABASE_URL
```

## Limitaciones del plan gratuito

- **Se duerme** tras 15 minutos sin visitas; la primera petición tarda ~1 minuto.
- **Disco efímero:** las fotos de verificación de libros y los carnés se guardan en disco y **se pierden** en cada reinicio o despliegue. Para uso real hace falta almacenamiento de objetos (S3, Cloudinary, Supabase Storage).
- **Una sola instancia, sin Redis:** chat y límites de intentos funcionan en memoria.
- **Verificación con IA desactivada:** `torch` no se instala (supera la memoria gratuita). Las publicaciones pasan a revisión humana.
