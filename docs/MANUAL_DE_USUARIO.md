# SWAPU — Manual de Usuario

SWAPU es la plataforma para **intercambiar libros y material académico** con otros estudiantes de tu universidad, sin dinero.

---

## 1. Primeros pasos

### 1.1 Entrar a la aplicación
Abre la dirección de SWAPU en tu navegador (por ejemplo `http://localhost:8000` en el equipo del proyecto). Sin iniciar sesión puedes ver el **catálogo** de libros disponibles.

### 1.2 Crear una cuenta
1. Pulsa **Iniciar sesión** y elige **Registrarse**.
2. Completa: nombre completo, correo, contraseña (**mínimo 8 caracteres**), y si quieres teléfono, facultad, carrera, semestre y universidad.
3. Pulsa **Crear cuenta**.

> Usa tu **correo institucional** (por ejemplo `@usbmed.edu.co`) para obtener la insignia de *Estudiante verificado* y mejores coincidencias con compañeros de tu universidad.

### 1.3 Confirmar tu correo institucional
1. Al registrarte con correo institucional recibirás un **código de 6 dígitos** en tu correo.
2. La aplicación te lo pedirá en una ventana: escríbelo y acepta.
3. Si no lo recibiste, deja la ventana vacía y acepta **reenviar el código**.

El código vence a los **30 minutos** y admite **5 intentos**. Hasta confirmarlo no podrás publicar ni intercambiar.

### 1.4 Iniciar y cerrar sesión
- **Iniciar sesión:** correo y contraseña. Si tu correo aún no está confirmado, se te pedirá el código.
- **Cerrar sesión:** botón de salida en la barra superior.
- Tras 5 intentos fallidos seguidos, la cuenta se bloquea temporalmente 15 minutos.

## 2. Tu perfil

En **Perfil** puedes:
- Ver y **editar** tus datos (nombre, teléfono, facultad, carrera, semestre).
- Consultar tus **publicaciones**, tu **reputación** y el estado de tu verificación.
- **Subir tu carné estudiantil** para solicitar la verificación manual de comunidad. Un moderador la aprueba o rechaza e indica el motivo.

## 3. Publicar un libro

1. Pulsa **Publicar libro**.
2. Completa:
   - **Título** y **libro que buscas a cambio** (obligatorios).
   - Autor, categoría, estado físico, ISBN (10 o 13 dígitos), edición y descripción.
3. Pulsa **Publicar**.

### Verificación del libro
Para que tu libro aparezca en el catálogo debes demostrar que lo tienes:
1. La aplicación te muestra un **código de verificación**.
2. Escríbelo en un papel y toma **dos fotos**: la **portada** y la **página del ISBN**, con el papel visible.
3. Sube las fotos (JPG o PNG).
4. Un moderador revisa las fotos y **aprueba** o **rechaza** la publicación. Al aprobarse, tu libro aparece en el catálogo.

> Si un moderador necesita aclaraciones, abrirá un **ticket** que verás en la sección **Tickets**.

## 4. Buscar libros

En **Catálogo**:
- Usa la **búsqueda** por título, autor o libro buscado.
- **Filtra** por categoría.
- Abre una publicación para ver el estado del libro, su dueño y su reputación.

## 5. Coincidencias (matches)

En **Matches**, SWAPU te muestra estudiantes que **tienen el libro que buscas y buscan uno que tú tienes**. Cada coincidencia indica si es **exacta** o **similar** y su puntuación. Las coincidencias mejoran si ambos están verificados y son de la misma universidad, facultad o semestres cercanos.

## 6. Intercambiar (trueques)

1. Desde una publicación o una coincidencia, pulsa **Proponer trueque** y elige el libro que ofreces.
2. El otro estudiante ve la propuesta en **Trueques** y puede **Confirmar** o **Rechazar**.
3. Una vez confirmado, acuerden por **chat** el lugar y la hora de entrega.
4. Después del intercambio, cualquiera de los dos pulsa **Completar**.

| Estado | Significado |
|---|---|
| Propuesto | Esperando respuesta del otro estudiante |
| Confirmado | Aceptado; coordinen la entrega |
| Completado | Intercambio realizado |
| Rechazado | Propuesta descartada |

> Un trueque no puede completarse si no fue confirmado.

## 7. Chat

- Abre el chat desde la tarjeta del trueque (**Chat**).
- Los mensajes llegan **en tiempo real**.
- El chat está disponible mientras el trueque esté *propuesto* o *confirmado*; se cierra al completarlo o rechazarlo.
- El lenguaje ofensivo se bloquea automáticamente. Solo los dos participantes pueden ver la conversación.

## 8. Calificaciones y reputación

- Al completar un trueque, pulsa **Calificar** y asigna de **1 a 5 estrellas** con una reseña opcional.
- Solo se puede calificar **una vez** por trueque.
- Tu reputación se calcula con un promedio ponderado y se muestra en tu perfil público: *nuevo*, *confiable* o *destacado*.
- Puedes **reportar** una reseña inapropiada para que la revise un moderador.

## 9. Tickets de soporte

En **Tickets** puedes ver las solicitudes de revisión sobre tus publicaciones, responder mensajes y seguir su estado.

## 10. Para moderadores y administradores

| Función | Rol |
|---|---|
| Revisar verificaciones de libros (ver fotos, aprobar o rechazar con nota) | Moderador, Administrador |
| Revisar carnés estudiantiles | Moderador, Administrador |
| Gestionar tickets | Moderador, Administrador |
| Reportes, advertencias, sanciones y apelaciones | Moderador, Administrador |
| Promover usuarios a moderador | Administrador |
| Consultar auditoría y estadísticas | Administrador |

El panel aparece en **Admin** al iniciar sesión con una cuenta autorizada.

## 11. Preguntas frecuentes

| Problema | Solución |
|---|---|
| No me llegó el código | Revisa spam; inicia sesión y elige **reenviar el código** |
| “Debes confirmar tu correo institucional” | Ingresa el código enviado a tu correo |
| “Has superado el límite de intentos” | Espera unos minutos e inténtalo de nuevo |
| Mi libro no aparece en el catálogo | Completa la verificación con fotos y espera la aprobación |
| No puedo enviar mensajes | El trueque ya fue completado o rechazado |
| “No se pudo cargar el catálogo” | El servidor no está disponible; intenta más tarde |
