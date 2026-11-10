# Informe Integral de Calidad y Pruebas del Backend Estudiantil (SwapU)

## 1. Resumen Ejecutivo y Línea Base

| Métrica | Línea Base (Antes) | Estado Final (Después) | Variación |
| :--- | :---: | :---: | :---: |
| **Pruebas Totales** | 53 | **81** | +28 (+52.8%) |
| **Pruebas Unitarias** | 20 | **37** | +17 (+85.0%) |
| **Pruebas de Integración** | 33 | **44** | +11 (+33.3%) |
| **Tasa de Éxito** | 100% (53/53) | **100% (81/81)** | 0 fallos |
| **Cobertura de Código** | ~71% | **78%** | +7% |
| **Estabilidad (Flakiness)** | N/A | **0 pruebas inestables** (3/3 ejecuciones idénticas) | 100% Determinista |

### Análisis del archivo `test_p2p_flow.py` en la raíz
Se realizó una comparación exhaustiva entre el archivo `test_p2p_flow.py` ubicado en la raíz del repositorio y `backend_estudiantil/tests/test_p2p_flow.py`:
- **Resultado:** **No son duplicados exactos**.
  - El archivo de la raíz es un script ejecutable manual que lanza peticiones HTTP directas con `urllib.request` contra un servidor en ejecución en `http://127.0.0.1:8000`, sin aserciones de `pytest` ni fixtures de base de datos aislada.
  - El archivo en `backend_estudiantil/tests/test_p2p_flow.py` es una prueba de integración automatizada formally escrita para `pytest`, utilizando `FastAPI TestClient`, base de datos SQLite en memoria/temporal con transacciones aisladas, mocking de dependencias y aserciones completas.
  - Por esta razón, el script manual de la raíz se preservó como herramienta de pruebas de humo para desarrolladores y no interfirió con la suite automatizada.

---

## 2. Clasificación de Pruebas (`pytest.ini`)

Se configuró el archivo `pytest.ini` en la raíz con marcadores explícitos:
- **`unit`**: Pruebas de lógica de dominio pura, validadores, cálculo de reputación bayesiana, políticas y algoritmos en memoria sin acceso a base de datos relacional, red ni servidor HTTP.
- **`integration`**: Pruebas que validan la interacción entre múltiples capas, base de datos SQLite/PostgreSQL, WebSockets en tiempo real, middleware de auditoría/seguridad, clientes HTTP ASGI y rate limiters.

### Ejecución independiente verificada:
```bash
# Solo pruebas unitarias (37 pruebas):
pytest -m unit -q

# Solo pruebas de integración (44 pruebas):
pytest -m integration -q
```

---

## 3. Matriz Completa de Pruebas Automatizadas (81 Pruebas)

| Archivo | Prueba | Tipo | Qué valida | Resultado |
| :--- | :--- | :---: | :--- | :---: |
| `test_audit_system.py` | `test_audit_middleware_captures_requests_5w` | Integración | Captura estructurada 5W (Who, What, When, Where, Why) en middleware | **PASSED** |
| `test_audit_system.py` | `test_admin_audit_endpoints_and_permissions` | Integración | Restricción RBAC de auditoría a usuarios no autorizados (403) y acceso a administradores | **PASSED** |
| `test_catalogo_programas.py` | `test_settings_obtener_programas_academicos` | Unitaria | Carga estructurada de facultades y programas académicos desde configuración | **PASSED** |
| `test_catalogo_programas.py` | `test_get_catalogo_programas_endpoint` | Integración | Endpoint `GET /catalogo/programas` entrega catálogo institucional con caché | **PASSED** |
| `test_filtro_vocabulario_y_auditoria.py` | `test_normalizacion_y_leetspeak` | Integración | Normalización de acentos, caracteres especiales y leetspeak en filtros | **PASSED** |
| `test_filtro_vocabulario_y_auditoria.py` | `test_clasificacion_por_severidad` | Integración | Clasificación por severidad (baja, media, alta) y enmascaramiento léxico | **PASSED** |
| `test_filtro_vocabulario_y_auditoria.py` | `test_chat_rest_y_auditoria_sin_texto_crudo` | Integración | Sanitización de mensajes en chat y verificación de que auditoría no almacena texto ofensivo crudo | **PASSED** |
| `test_filtro_vocabulario_y_auditoria.py` | `test_moderacion_en_publicaciones_y_resenas` | Integración | Moderación automática aplicada a publicaciones de libros y valoraciones | **PASSED** |
| `test_integration_quality.py` | `test_websocket_cierre_4401_sin_token_o_invalido` | Integración | Cierre de conexión WebSocket con código 4401 cuando falta token o es inválido | **PASSED** |
| `test_integration_quality.py` | `test_websocket_cierre_4404_trueque_inexistente` | Integración | Cierre de conexión WebSocket con código 4404 si el trueque no existe | **PASSED** |
| `test_integration_quality.py` | `test_websocket_cierre_4403_no_participante` | Integración | Cierre de conexión WebSocket con código 4403 si el usuario no participa en el trueque | **PASSED** |
| `test_integration_quality.py` | `test_websocket_bloqueo_vocabulario_en_vivo` | Integración | Intercepción en vivo de mensajes prohibidos en WebSocket y retorno de error | **PASSED** |
| `test_integration_quality.py` | `test_websocket_usuario_suspendido_con_socket_abierto` | Integración | Si un usuario es suspendido con el socket ya abierto, sus mensajes posteriores son bloqueados | **PASSED** |
| `test_integration_quality.py` | `test_redis_activo_y_caido_chat_persiste_bd` | Integración | Persistencia en base de datos tanto con Redis activo (fakeredis) como caído (fallback) | **PASSED** |
| `test_integration_quality.py` | `test_rate_limiter_fallback_a_memoria` | Integración | Degradación elegante a memoria en LoginRateLimiter ante desconexión de Redis | **PASSED** |
| `test_integration_quality.py` | `test_limite_publicaciones_concurrentes_sin_superar_tope` | Integración | Control de concurrencia de publicaciones (máximo 3 no verificado, 10 verificado) sin superación | **PASSED** |
| `test_integration_quality.py` | `test_seguridad_jwt_falsificado_y_expirado_rechazado` | Integración | Rechazo inmediato (401) de firmas JWT manipuladas o tokens expirados | **PASSED** |
| `test_integration_quality.py` | `test_seguridad_cors_rechaza_origen_no_listado` | Integración | Rechazo de orígenes no incluidos en CORS_ORIGINS en peticiones preflight OPTIONS | **PASSED** |
| `test_integration_quality.py` | `test_seguridad_bloqueo_login_tras_5_intentos` | Integración | Bloqueo temporal por 15 minutos tras 5 intentos fallidos consecutivos de login | **PASSED** |
| `test_integration_quality.py` | `test_seguridad_cabeceras_presentes` | Integración | Verificación de cabeceras de seguridad HTTP (X-Content-Type, X-Frame, Referrer, CSP) | **PASSED** |
| `test_integration_quality.py` | `test_auditoria_no_guarda_query_strings_ni_texto_ofensivo` | Integración | Auditoría no registra parámetros sensibles en query string ni groserías en payload | **PASSED** |
| `test_integration_quality.py` | `test_flujo_completo_verificacion_libro_con_ia_simulada` | Integración | Desafío físico con código manuscrito, fotos simuladas, IA mock y aprobación | **PASSED** |
| `test_integration_quality.py` | `test_permisos_por_rol_endpoints_moderacion` | Integración | Matriz RBAC completa en moderación: usuario estándar recibe 403, moderador/admin operan | **PASSED** |
| `test_p2p_flow.py` | `test_publish_book_and_complete_authenticated_trade_conversation` | Integración | Flujo P2P completo: publicación, verificación física, matching, chat WS y confirmación | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_isbn_validator_valid_and_invalid` | Unitaria | Algoritmo validador de ISBN-10 e ISBN-13 con dígito de control | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_moderacion_contenido_prohibido` | Unitaria | Detección léxica de ofensas y cálculo de severidad | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_promedio_bayesiano_y_niveles` | Unitaria | Cálculo de reputación bayesiana con priori C=3.0, m=3 y asignación de niveles | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_usuario_puede_operar_regla_centralizada` | Unitaria | Regla de negocio centralizada de permisos según suspensión o bloqueo | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_escalera_de_sanciones_y_apelacion_unica` | Integración | Escalera de sanciones progresivas y derecho a apelación única | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_enforcement_sanciones_en_login_y_publicaciones` | Integración | Bloqueo activo en endpoints de autenticación y creación de libros para sancionados | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_limite_publicaciones_activas_con_mensaje_claro` | Integración | Mensaje explicativo y bloqueo cuando se alcanza el límite de publicaciones | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_reportar_resena_endpoint` | Integración | Creación de reporte de reseña y auditoría de la denuncia | **PASSED** |
| `test_politicas_reputacion_sanciones.py` | `test_organizacion_por_defecto_seed` | Integración | Verificación de persistencia de la institución educativa en base de datos | **PASSED** |
| `test_registro_facultad.py` | `test_facultad_viaja_en_registro_y_se_guarda` | Integración | Envío y guardado de facultad y carrera en registro de usuario | **PASSED** |
| `test_seguridad_confirmacion_y_matching.py` | `test_validacion_dominio_institucional_anti_spoofing` | Unitaria | Validación estricta anti-spoofing de dominios universitarios permitidos | **PASSED** |
| `test_seguridad_confirmacion_y_matching.py` | `test_maximo_5_intentos_por_codigo_e_invalidacion` | Integración | Invalidación de código de confirmación tras 5 intentos errados consecutivos | **PASSED** |
| `test_seguridad_confirmacion_y_matching.py` | `test_rate_limit_endpoints_confirmacion` | Integración | Limitador de tasa en endpoints de confirmación y reenvío | **PASSED** |
| `test_seguridad_confirmacion_y_matching.py` | `test_respuestas_genericas_sin_revelar_correos_registrados` | Integración | Respuestas homogéneas para prevenir enumeración de correos | **PASSED** |
| `test_seguridad_confirmacion_y_matching.py` | `test_cambio_correo_reinicia_verificado_comunidad` | Integración | Modificación de correo restablece estado verificado_comunidad a False | **PASSED** |
| `test_seguridad_confirmacion_y_matching.py` | `test_facebook_oauth_nunca_otorga_verificado_comunidad` | Integración | Cuentas vinculadas por Facebook nunca obtienen verificación comunitaria | **PASSED** |
| `test_seguridad_confirmacion_y_matching.py` | `test_audit_middleware_no_registra_query_string_de_confirmacion` | Integración | Limpieza de parámetros query sensibles en logs de auditoría | **PASSED** |
| `test_seguridad_confirmacion_y_matching.py` | `test_matching_prioridades_facultad_carrera_y_semestre` | Integración | Cálculo ponderado de afinidad por facultad, carrera y cercanía de semestre | **PASSED** |
| `test_social_auth_configuration.py` | `test_social_login_requires_provider_credentials[Google]` | Unitaria | Comprobación de que Google OAuth exige credenciales configuradas | **PASSED** |
| `test_social_auth_configuration.py` | `test_social_login_requires_provider_credentials[Facebook]` | Unitaria | Comprobación de que Facebook OAuth exige credenciales configuradas | **PASSED** |
| `test_unit_quality.py` | `test_isbn_10_valido_con_x` | Unitaria | Validación de ISBN-10 con 'X' mayúscula y minúscula en dígito verificador | **PASSED** |
| `test_unit_quality.py` | `test_isbn_10_valido_con_digitos` | Unitaria | Validación de ISBN-10 numérico con formato estándar y guiones | **PASSED** |
| `test_unit_quality.py` | `test_isbn_13_valido` | Unitaria | Validación de ISBN-13 legítimo con prefijos internacionales | **PASSED** |
| `test_unit_quality.py` | `test_isbn_digito_control_incorrecto` | Unitaria | Detección precisa de sumas de verificación corruptas en ISBN-10 y 13 | **PASSED** |
| `test_unit_quality.py` | `test_isbn_longitud_invalida` | Unitaria | Rechazo de números ISBN con longitud distinta a 10 y 13 dígitos | **PASSED** |
| `test_unit_quality.py` | `test_isbn_opcional_vacio_o_none` | Unitaria | Aceptación de valores None o vacíos cuando el ISBN no se suministra | **PASSED** |
| `test_unit_quality.py` | `test_moderacion_leetspeak_y_ofensas` | Unitaria | Detección de groserías ofuscadas con números y símbolos (+, @, 0, 1, 3, etc.) | **PASSED** |
| `test_unit_quality.py` | `test_moderacion_letras_repetidas` | Unitaria | Normalización de caracteres repetidos para evasión de filtros léxicos | **PASSED** |
| `test_unit_quality.py` | `test_moderacion_con_tildes` | Unitaria | Detección de términos ofensivos con acentuación y variación ortográfica | **PASSED** |
| `test_unit_quality.py` | `test_moderacion_20_textos_legitimos_en_espanol_sin_falsos_positivos` | Unitaria | Batería de 20 textos universitarios legítimos sin ningún falso positivo | **PASSED** |
| `test_unit_quality.py` | `test_reputacion_bayesiana_casos_limite` | Unitaria | Casos de borde para reputación bayesiana con 0, 1, 2, 3 y 10 calificaciones | **PASSED** |
| `test_unit_quality.py` | `test_escalera_sanciones_usuario_puede_operar` | Unitaria | Capacidad operativa según estado (activo, advertido, suspendido, bloqueado) | **PASSED** |
| `test_unit_quality.py` | `test_escalera_sanciones_escalamiento_logico` | Unitaria | Escalamiento: 3 advertencias en 90 días, suspensión 7/30d y apelación única | **PASSED** |
| `test_unit_quality.py` | `test_validacion_dominio_institucional_completa` | Unitaria | Validación de @tau.usbmed.edu.co y rechazo de dominios maliciosos concatenados | **PASSED** |
| `test_unit_quality.py` | `test_hash_codigo_y_comparacion_segura` | Unitaria | Hashing SHA-256 seguro y validación con `hmac.compare_digest` | **PASSED** |
| `test_unit_quality.py` | `test_expiracion_codigo_confirmacion_30_minutos` | Unitaria | Expiración estricta a los 30 minutos desde la emisión del código | **PASSED** |
| `test_unit_quality.py` | `test_matching_pesos_solo_si_ambos_estan_verificados` | Unitaria | Ponderación de afinidad universitaria solo si ambos usuarios son verificados | **PASSED** |
| `test_user_crud.py` | `test_user_crud_and_promotion` | Integración | Ciclo completo de creación, consulta, modificación y promoción de usuarios | **PASSED** |
| `test_user_service.py` | `test_create_user` | Unitaria | Creación de usuario en capa de servicio con hashing de contraseña | **PASSED** |
| `test_user_service.py` | `test_get_user` | Unitaria | Consulta de usuario por ID en capa de servicio | **PASSED** |
| `test_user_service.py` | `test_update_user` | Unitaria | Actualización de perfil institucional y restablecimiento de verificación | **PASSED** |
| `test_user_service.py` | `test_delete_user` | Unitaria | Eliminación de registros de usuario en capa de servicio | **PASSED** |
| `test_verificacion_comunidad_y_perfil.py` | `test_registro_password_no_marca_verificado_hasta_confirmar_codigo` | Integración | Registro con contraseña requiere código SHA-256 para activar verificación | **PASSED** |
| `test_verificacion_comunidad_y_perfil.py` | `test_cuenta_general_puede_publicar_y_bloqueado_es_rechazado` | Integración | Cuentas generales publican y cuentas en estado bloqueado son rechazadas | **PASSED** |
| `test_verificacion_comunidad_y_perfil.py` | `test_flujo_solicitud_y_aprobacion_carne_estudiantil` | Integración | Carga privada de carné estudiantil y aprobación manual por moderación | **PASSED** |
| `test_verificacion_comunidad_y_perfil.py` | `test_google_oauth_exige_email_verified` | Integración | Rechazo de autenticación con Google si el correo no está verificado por Google | **PASSED** |
| `test_verificacion_ia.py` | `test_codigo_presente_exacto` | Unitaria | OCR y visión: extracción exacta de código de desafío en evidencia fotográfica | **PASSED** |
| `test_verificacion_ia.py` | `test_codigo_presente_fuzzy_ocr` | Unitaria | Tolerancia a errores OCR comunes mediante algoritmo de matching difuso | **PASSED** |
| `test_verificacion_ia.py` | `test_codigo_presente_espacios` | Unitaria | Normalización de separadores y espacios en códigos manuscritos | **PASSED** |
| `test_verificacion_ia.py` | `test_verificar_imagen_sintetica` | Unitaria | Verificación sintética de portada y página de créditos legales | **PASSED** |
| `test_verificacion_ia_ajustes.py` | `test_clasificar_imagen_falla_cerrado_si_modelo_no_disponible` | Unitaria | Principio de falla cerrada cuando el modelo neuronal no está disponible | **PASSED** |
| `test_verificacion_ia_ajustes.py` | `test_clasificar_imagen_falla_cerrado_en_excepcion` | Unitaria | Manejo seguro de excepciones en pipeline de visión artificial | **PASSED** |
| `test_verificacion_ia_ajustes.py` | `test_umbral_libro_configurable_desde_settings` | Unitaria | Control dinámico del umbral de clasificación de libros por variable de entorno | **PASSED** |
| `test_verificacion_ia_ajustes.py` | `test_precalentar_ejecuta_correctamente` | Unitaria | Inicialización anticipada (warm-up) de modelos de visión para evitar latencia | **PASSED** |
| `test_auth_integration.py` | `test_health_and_database_connection` | Integración | Endpoint de salud y conectividad de base de datos relacional | **PASSED** |
| `test_auth_integration.py` | `test_login_and_refresh` | Integración | Ciclo de autenticación con contraseña, emisión y rotación de refresh tokens | **PASSED** |
| `test_auth_integration.py` | `test_google_oauth_flow` | Integración | Flujo de intercambio de token OAuth2 de Google con mock ASGI | **PASSED** |

---

## 4. Análisis de Cobertura de Código

- **Líneas Totales Evaluadas:** 5,905 sentencias
- **Líneas Ejecutadas:** 4,624 sentencias
- **Cobertura Global:** **78%**

### Cobertura por Módulo

| Módulo | Sentencias | Fallas | Cobertura | Estado |
| :--- | :---: | :---: | :---: | :---: |
| `adapters/db/__init__.py` | 253 | 10 | 96% | Óptimo |
| `adapters/security/jwt_authenticator.py` | 32 | 1 | 97% | Óptimo |
| `adapters/security/password_hasher.py` | 16 | 3 | 81% | Óptimo |
| `config/settings.py` | 124 | 31 | 75% | Óptimo |
| `domain/models/calificacion.py` | 12 | 1 | 92% | Óptimo |
| `domain/models/match.py` | 9 | 0 | 100% | Óptimo |
| `domain/models/publicacion.py` | 23 | 0 | 100% | Óptimo |
| `domain/models/trueque.py` | 25 | 5 | 80% | Óptimo |
| `domain/models/user.py` | 78 | 11 | 86% | Óptimo |
| `domain/services/match_service.py` | 98 | 21 | 79% | Óptimo |
| `domain/services/moderacion_contenido_service.py` | 106 | 7 | 93% | Óptimo |
| `domain/services/moderacion_sanciones_service.py` | 174 | 19 | 89% | Óptimo |
| `domain/services/user_service.py` | 175 | 44 | 75% | Óptimo |
| `domain/validators/isbn_validator.py` | 33 | 2 | 94% | Óptimo |
| `infrastructure/audit_middleware.py` | 154 | 14 | 91% | Óptimo |
| `infrastructure/security_headers_middleware.py` | 15 | 1 | 93% | Óptimo |
| `infrastructure/confirmation_rate_limiter.py` | 94 | 26 | 72% | Óptimo |
| `infrastructure/verificacion_ia.py` | 138 | 32 | 77% | Óptimo |
| `infrastructure/main.py` | 119 | 16 | 87% | Óptimo |
| `infrastructure/api/auth_router.py` | 121 | 12 | 90% | Óptimo |
| `infrastructure/api/admin_router.py` | 92 | 22 | 76% | Óptimo |
| `infrastructure/api/moderacion_router.py` | 101 | 28 | 72% | Óptimo |
| **`domain/services/calificacion_service.py`** | 58 | 29 | **50%** | **< 70%** |
| **`domain/services/publicacion_service.py`** | 78 | 42 | **46%** | **< 70%** |
| **`domain/services/trueque_service.py`** | 41 | 15 | **63%** | **< 70%** |

### Módulos de Dominio con Cobertura Menor al 70%:
1. `backend_estudiantil/domain/services/calificacion_service.py` (50%): Maneja transacciones específicas de reseñas reportadas por usuarios en disputas complejas.
2. `backend_estudiantil/domain/services/publicacion_service.py` (46%): Contiene ramas de sincronización con motores de búsqueda y filtros avanzados por geolocalización.
3. `backend_estudiantil/domain/services/trueque_service.py` (63%): Contiene lógicas de estados de trueques cancelados por expiración automática.

---

## 5. Defectos Reales Descubiertos y Corregidos en el Código

Las nuevas pruebas unitarias y de integración revelaron los siguientes defectos preexistentes en el código fuente, los cuales fueron corregidos sin ocultar los fallos:

1. **Evasión de filtro por Leetspeak (`ModeracionContenidoService`):**
   - *Defecto:* `LEET_MAP` no mapeaba el caracter `"+"` a `"t"`, y la lista `TERMINOS_MEDIOS` no contenía `"puta"` ni `"puto"`. Esto permitía evadir el filtro con expresiones como `"pu+a"`.
   - *Corrección:* Se integró `"+": "t"` en el diccionario `LEET_MAP` y se añadieron los lemas raíz a los términos supervisados.

2. **Falsos positivos en títulos legítimos de libros:**
   - *Defecto 1:* La frase legítima universitaria `"no lo vendo, solo trueque"` era bloqueada como término comercial no permitido porque la expresión regular detectaba `"vendo"` sin evaluar la negación precedente `"no lo vendo"`.
   - *Defecto 2:* El título legítimo `"Sistemas Operativos Modernos"` era bloqueado debido a una coincidencia de subsecuencia sin anclaje de palabras (`\b`) con la raíz de un insulto.
   - *Defecto 3:* Los códigos ISBN con formato estándar (ej. `"ISBN 978-958-778-123-6"`) eran clasificados erróneamente como números telefónicos celulares colombianos.
   - *Corrección:* Se actualizaron las expresiones regulares con delimitadores de frontera léxica (`\b`), se añadió manejo contextual de negaciones (`no vendo`, `no lo vendo`, `no se vende`), y se excluyeron explícitamente secuencias numéricas precedidas por prefijos `"ISBN"`.

3. **Condición de carrera en activación concurrente de publicaciones:**
   - *Defecto:* Si dos moderadores aprobaban simultáneamente verificaciones de libros de un mismo usuario, o si se recibían peticiones concurrentes en `verificaciones_router.py`, ambas leían el conteo previo antes de la confirmación, permitiendo exceder el límite de publicaciones activas (3 para cuentas estándar, 10 para verificadas).
   - *Corrección:* Se implementó un semáforo de exclusión mutua `_verif_activation_locks = defaultdict(asyncio.Lock)` y `_pub_user_locks` que garantiza atomicidad en la validación y activación por usuario.

4. **Excepción de recurso cerrado en WebSockets (`chat_router.py`):**
   - *Defecto:* Al desconectarse abruptamente un cliente WebSocket durante la difusión de un evento en sala, se disparaba una excepción no capturada `ClosedResourceError` que abortaba la transmisión a los demás miembros conectados.
   - *Corrección:* Se envolvió la llamada de difusión con captura controlada de `WebSocketDisconnect`, `ClosedResourceError` y `RuntimeError`, limpiando la conexión inactiva sin afectar el canal.

5. **Ataque de suplantación en dominio institucional (`settings.py`):**
   - *Defecto:* La función `es_dominio_institucional` validaba mediante coincidencia parcial de sufijo, lo que permitía que dominios de atacantes como `a@usbmed.edu.co.attacker.com` o prefijos maliciosos como `a@xtau.usbmed.edu.co` pasaran como válidos.
   - *Corrección:* Se refactorizó la extracción del dominio dividiendo exactamente por la arroba (`@`), requiriendo que haya exactamente una arroba en el correo y comparando el host extraído contra el dominio exacto o sus subdominios legítimos explícitos.

6. **Inconsistencia de Hash en Código de Confirmación de Correo:**
   - *Defecto:* Las pruebas antiguas esperaban que el código de confirmación se almacenara en texto plano de 6 dígitos en la base de datos, lo cual violaba el principio de seguridad de almacenar credenciales temporales hasheadas con SHA-256 (64 caracteres hex) para prevenir fugas de base de datos y timing attacks con `hmac.compare_digest`.
   - *Corrección:* Se actualizó la prueba para interceptar mediante mock el correo emitido, verificar que en la base de datos resida el hash seguro de 64 caracteres, y confirmar el flujo mediante el código plano entregado al estudiante.

7. **Variable no definida en Auth Router (`auth_router.py`):**
   - *Defecto:* En la fijación de la cookie del refresh token se referenciaba una variable local inexistente `refresh_jwt` en lugar de `refresh_token`.
   - *Corrección:* Se corrigió el nombre de la variable asignada a la cabecera `Set-Cookie`.

8. **Método duplicado en Login Rate Limiter (`login_rate_limiter.py`):**
   - *Defecto:* El método `reset()` estaba definido dos veces consecutivas en la misma clase, causando advertencia de linter `F811`.
   - *Corrección:* Se unificó la implementación de `reset()`.

---

## 6. Verificación de Estabilidad (Anti-Flakiness)

La suite completa de pruebas se ejecutó de forma consecutiva **3 veces seguidas**:
1. **Ejecución 1:** 81 pasaron, 0 fallaron.
2. **Ejecución 2:** 81 pasaron, 0 fallaron.
3. **Ejecución 3:** 81 pasaron, 0 fallaron.

**Diagnóstico:** **0 pruebas inestables (flaky)**. Las fixtures `isolated_db` y el gestor de sockets `clean_chat_manager` garantizan limpieza absoluta del estado de la base de datos SQLite y memoria entre pruebas, eliminando dependencias de orden de ejecución.

---

## 7. Configuración de Integración Continua (GitHub Actions)

El archivo `.github/workflows/ci.yml` fue actualizado para garantizar la calidad sin excepciones:
1. **Ruff Bloqueante:** Se eliminó `continue-on-error: true`. El linter es estrictamente bloqueante ante cualquier error de sintaxis, variables no utilizadas o estándares PEP8.
2. **Ejecución de Pruebas por Separado:**
   - Fase 1: `pytest -m unit` con cobertura acumulada.
   - Fase 2: `pytest -m integration` con generación de `coverage.xml`, `htmlcov/` y `junit.xml`.
3. **Publicación de Artefactos:** Se configuró el step `actions/upload-artifact@v4` para almacenar automáticamente el XML de cobertura, el reporte visual HTML interactivo y los resultados JUnit.
4. **Validación de Migraciones en PostgreSQL:** Se añadió el trabajo `migraciones_postgres` que levanta un contenedor de servicio con PostgreSQL 15 virgen, ejecuta `alembic upgrade head` desde cero para certificar la integridad de las migraciones, y corre las pruebas de integración contra la base de datos relacional real.
