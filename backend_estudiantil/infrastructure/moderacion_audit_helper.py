"""
moderacion_audit_helper.py
--------------------------
Funciones auxiliares para registrar eventos de auditoría por infracciones de contenido
y moderación en la base de datos (AuditoriaLogORM), cumpliendo la regla de las 5W
y protegiendo la privacidad al NO almacenar el texto completo del mensaje.
"""


from backend_estudiantil.adapters.db import AuditoriaLogORM, get_session_factory


async def registrar_auditoria_infraccion(
    usuario_id: int | None,
    recurso: str,
    accion: str,
    severidad: str,
    categoria: str = "vocabulario",
    ip_origen: str = "127.0.0.1",
    metodo_http: str = "POST",
    endpoint: str = "",
    estado_http: int = 400,
    usuario_email: str | None = None,
    usuario_rol: str | None = None,
    terminos_count: int = 1,
) -> None:
    """
    Persiste en AuditoriaLogORM un registro con la acción específica
    (INFRACCION_VOCABULARIO, INFRACCION_CONTENIDO_PROHIBIDO, ADVERTENCIA_APLICADA, SANCION_APLICADA).
    
    CRÍTICO: No guarda el texto completo del mensaje, únicamente la categoría, severidad y conteo.
    """
    factory = get_session_factory()
    async with factory() as session:
        audit = AuditoriaLogORM(
            usuario_id=usuario_id,
            usuario_email=usuario_email,
            usuario_rol=usuario_rol,
            ip_origen=ip_origen,
            accion=accion,
            recurso=recurso,
            metodo_http=metodo_http,
            endpoint=endpoint,
            estado_http=estado_http,
            exito=False if estado_http >= 400 else True,
            detalle=f"categoria={categoria}, severidad={severidad}, terminos_detectados={terminos_count}",
        )
        session.add(audit)
        await session.commit()
