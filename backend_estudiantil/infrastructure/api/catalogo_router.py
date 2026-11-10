"""
catalogo_router.py
------------------
Endpoints de catálogo académico e institucional para menús desplegables
configurables de facultades y carreras de la plataforma.
"""


from fastapi import APIRouter

from backend_estudiantil.config.settings import settings

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


@router.get("/programas")
def get_programas() -> dict[str, dict[str, list[str]] | list[str]]:
    """Retorna la oferta oficial configurable de facultades y carreras de la USB Medellín.
    
    Cada facultad incluye sus programas vigentes y la opción 'Otra' para evitar
    bloqueos a usuarios cuyos programas no figuren en el listado estándar.
    """
    programas = settings.obtener_programas_academicos()
    return {
        "facultades": list(programas.keys()),
        "carreras_por_facultad": programas,
        "oferta": programas,
    }
