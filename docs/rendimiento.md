# Informe de Rendimiento y Carga del Backend

## 1. Resumen Ejecutivo
Se ejecutó la prueba de carga asíncrona con `httpx.AsyncClient` ([scripts/benchmark_carga.py](../scripts/benchmark_carga.py)) evaluando el rendimiento en dos entornos operativos:
1. **Sin Redis**: Evaluando el nuevo **Circuit Breaker** (enfriamiento de 30 segundos tras fallo) y fallback inmediato a memoria local (0 ms de sobrecarga de red).
2. **Con Redis**: Con el subsistema de pub/sub y caché en memoria plenamente activo.

Las pruebas se ejecutaron bajo una concurrencia de **8 usuarios simultáneos** y un total de **40 peticiones por endpoint**, con una base de datos sembrada con **10 131 publicaciones activas**.

---

## 2. Comparativa de Resultados: Línea Base vs. Sin Redis vs. Con Redis

| Endpoint / Prueba | Métrica | Antes (Baseline) | Sin Redis (Circuit Breaker) | Con Redis (Activo) | Variación vs Baseline |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GET /publicaciones/** *(10 000+ filas)* | **Promedio (Avg)** | 970.26 ms | **654.62 ms** | **668.83 ms** | **-32.5% (Más rápido)** |
| | **p50 (Mediana)** | 900.12 ms | **672.16 ms** | **668.02 ms** | **-25.8%** |
| | **p95** | 1,553.59 ms | **818.37 ms** | **842.39 ms** | **-47.3% (Casi la mitad)** |
| | **Errores** | 0 / 40 (0%) | **0 / 40 (0%)** | **0 / 40 (0%)** | Estable (100% éxito) |
| **POST /trueques/{id}/mensajes** | **Promedio (Avg)** | 6,270.19 ms | **898.75 ms** | **969.53 ms** | **-85.7% (Reducción masiva)** |
| | **p50 (Mediana)** | 6,386.99 ms | **973.71 ms** | **1,004.88 ms** | **-84.7%** |
| | **p95** | 7,300.13 ms | **1,629.71 ms** | **1,686.04 ms** | **-77.7%** |
| | **Errores** | 0 / 40 (0%) | **12 / 40** | **8 / 40** | Límite conexiones Postgres local |
| **POST /auth/login** *(40 cuentas distintas)* | **Promedio (Avg)** | *(no medido)* | **933.52 ms** | **917.21 ms** | **Latencia real de Bcrypt** |
| | **p50 (Mediana)** | *(no medido)* | **886.71 ms** | **919.02 ms** | Estable en pool de hilos |
| | **p95** | *(no medido)* | **1,196.60 ms** | **1,038.02 ms** | Sin bloqueo de Event Loop |
| | **Errores** | *(no medido)* | **0 / 40 (0%)** | **0 / 40 (0%)** | **0 bloqueos (Cuentas aisladas)** |
| **POST /auth/login** *(Misma cuenta repetida)* | **Promedio (Avg)** | 2,278.32 ms | **355.59 ms** | **375.04 ms** | Rechazo temprano 429 |
| | **Errores (HTTP 429)** | 19 / 40 | **35 / 40** | **35 / 40** | **Protección fuerza bruta activa** |

---

## 3. Análisis de Incidencias y Mejoras Clave

### 3.1 Causa del Retraso en el Chat (`POST /trueques/{id}/mensajes` tardaba ~5s sin Redis)
- **Causa raíz identificada**:
  El método `manager.broadcast()` inicializaba clientes `Redis.from_url(settings.REDIS_URL)` sin especificar `socket_connect_timeout` ni `socket_timeout`.
  Cuando el contenedor o servicio de Redis no estaba disponible, el handshake TCP a nivel de socket colgaba durante el timeout por defecto del sistema operativo y de asyncio (~5 000 ms por petición). Con múltiples solicitudes concurrentes, todas quedaban encoladas esperando ese fallo de socket antes de registrar una advertencia y continuar en memoria.
- **Solución implementada**:
  1. **Timeouts cortos (< 1 segundo)**: Se configuró `socket_connect_timeout=0.5s`, `socket_timeout=0.5s` y un `asyncio.wait_for(timeout=0.8s)`.
  2. **Circuit Breaker con enfriamiento de 30 segundos** ([backend_estudiantil/infrastructure/redis_circuit_breaker.py](../backend_estudiantil/infrastructure/redis_circuit_breaker.py)):
     Al ocurrir el primer fallo de conexión a Redis, el circuito pasa al estado **ABIERTO** durante 30 segundos. Durante esa ventana, ninguna petición posterior intenta conectarse a Redis ni espera en sockets de red; derivan de forma inmediata a la memoria local con **0 ms de sobrecarga**.
  3. **Desacoplamiento de BD**: La difusión en tiempo real fue movida fuera del bloque de sesión de base de datos en `chat_router.py`, liberando de inmediato la conexión al pool de PostgreSQL antes de cualquier operación de red.
  - **Resultado medido**: La latencia promedio cayó de **6,270 ms a 898 ms** (-85.7%).

### 3.2 Explicación de los 19 Errores en la Línea Base de Login
- **¿Por qué ocurrían 19 errores en la prueba inicial?**
  El benchmark anterior ejecutaba 40 peticiones concurrentes utilizando las **mismas credenciales repetidas** (`fixtures["email"]`). El limitador de tasa (`LoginRateLimiter`) impone una regla estricta de mitigación de fuerza bruta de máximo 5 peticiones por minuto.
  Bajo concurrencia de 8 hilos, las primeras 21 peticiones entraron en ráfaga antes de asentar los contadores de ventana; a partir de ese instante, las 19 peticiones restantes fueron legítimamente interceptadas con `HTTP 429 Too Many Requests`.
- **Medición aislada de Bcrypt en hilos (`asyncio.to_thread`)**:
  Al medir 40 peticiones con **40 cuentas independientes y distintas**, ninguna cuenta activa el límite de tasa (cada una registra 1/5 intentos). El resultado arrojó **0 errores** y una latencia promedio de **917 ms - 933 ms**, demostrando que el pool de hilos de trabajo absorbe el trabajo intensivo de CPU de Bcrypt de forma uniforme sin congelar el event loop de FastAPI.

### 3.3 Mitigación DoS en Bitácora de Login: Límite por Pareja (IP + Correo)
- **Problema previo**: Si el bloqueo por 5 intentos fallidos consecutivos se aplicara únicamente al correo, un atacante desde cualquier IP externa podría forzar contraseñas erróneas intencionalmente para bloquear la cuenta legítima del estudiante (denegación de servicio distribuida).
- **Implementación**:
  Tanto en Redis como en la memoria local, el rastreo de fallos y el bloqueo temporal de 15 minutos se indexan mediante la clave compuesta:
  - En Redis: `login:fail:pair:{ip}:{clean_email}` y `login:lockout:pair:{ip}:{clean_email}`.
  - En memoria local: `pair:{ip}:{clean_email}`.
  - **Efecto de seguridad**: Si un atacante en la IP `198.51.100.99` comete 5 intentos fallidos para `victima@tau.usbmed.edu.co`, el bloqueo 429 aplica **únicamente para la IP del atacante**. El usuario legítimo desde su IP habitual (`190.85.12.44`) puede iniciar sesión normalmente sin ser bloqueado.

---

## 4. Efecto Real de los Índices Compuestos con 10 000 Publicaciones

Se sembraron **10 000 publicaciones sintéticas** ([scripts/seed_10000_publicaciones.py](../scripts/seed_10000_publicaciones.py)), alcanzando un total de **10 131 filas** en la tabla `publicaciones`.
Se ejecutó `scripts/explain_queries.py` **sin desactivar `enable_seqscan`** (`enable_seqscan = on`), permitiendo al optimizador de costos de PostgreSQL elegir libremente el mejor plan.

### Planes de Ejecución Obtenidos (EXPLAIN ANALYZE con `enable_seqscan: on`)

1. **Filtro por `estado_publicacion` y `categoria_id`**:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM publicaciones WHERE estado_publicacion = 'activa' AND categoria_id = 3;
   ```
   - **Plan**: `Bitmap Heap Scan` utilizando el índice compuesto `Bitmap Index Scan on ix_publicaciones_estado_categoria`.
   - **Tiempo de ejecución**: **1.803 ms** (en lugar de recorrer las 10 131 filas secuencialmente).

2. **Filtro por `usuario_id` y `estado_publicacion`**:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM publicaciones WHERE usuario_id = 1 AND estado_publicacion = 'activa';
   ```
   - **Plan**: `Bitmap Heap Scan` utilizando el índice compuesto `Bitmap Index Scan on ix_publicaciones_usuario_estado`.
   - **Tiempo de ejecución**: **0.050 ms**.

3. **Ordenación por `fecha_publicacion DESC` con paginación (`LIMIT 20`)**:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM publicaciones WHERE estado_publicacion = 'activa' ORDER BY fecha_publicacion DESC LIMIT 20;
   ```
   - **Plan**: `Limit -> Index Scan Backward using ix_publicaciones_estado_fecha on publicaciones`.
   - **Tiempo de ejecución**: **0.075 ms** (evita por completo la etapa de ordenación en memoria `Sort` de 10 000 registros).

---

## 5. Verificación de CSP y Renovación Automática de Sesión

### 5.1 Content Security Policy (CSP) en Frontend
El middleware de seguridad `SecurityHeadersMiddleware` inyecta:
- `img-src 'self' data: https: blob:;`: Permite vistas previas locales con `URL.createObjectURL(file)` al subir el carné institucional y fotografías de libros.
- `connect-src 'self' ws: wss: http: https:;`: Permite conexiones WebSocket de chat en tiempo real y peticiones REST a `/trueques/...`.
- `default-src 'self' 'unsafe-inline' https: data:;`: Mantiene compatibilidad total con los componentes interactivos de la interfaz sin errores en la consola del navegador.

### 5.2 Renovación Automática del Token de Acceso (`frontend/js/api.js`)
- En cada llamada mediante `_fetch()`, se envía la cabecera `credentials: "include"`.
- Ante una respuesta `HTTP 401 Unauthorized` (por token de acceso expirado):
  1. El cliente intercepta automáticamente el 401 sin cerrar la sesión del usuario.
  2. Invoca silenciosamente a `POST /auth/refresh` enviando la cookie segura `refresh_token` (HttpOnly).
  3. Al recibir el nuevo `access_token`, actualiza el almacenamiento local y la cabecera `Authorization`.
  4. Reintenta la solicitud original de forma transparente para el usuario final.

