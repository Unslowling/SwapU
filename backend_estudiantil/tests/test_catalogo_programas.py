import pytest
from httpx import ASGITransport, AsyncClient

from backend_estudiantil.config.settings import settings
from backend_estudiantil.infrastructure.main import app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_catalogo_programas_endpoint():
    """Valida que GET /catalogo/programas retorne la estructura completa y configurable."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/catalogo/programas")

    assert response.status_code == 200
    data = response.json()
    assert "facultades" in data
    assert "carreras_por_facultad" in data
    assert "oferta" in data

    facultades_esperadas = [
        "Facultad de Ingenierías",
        "Facultad de Ciencias Empresariales",
        "Facultad de Arquitectura y Artes",
        "Facultad de Derecho y Ciencias Políticas",
        "Facultad de Psicología",
        "Facultad de Educación",
    ]
    assert set(data["facultades"]) == set(facultades_esperadas)

    oferta = data["carreras_por_facultad"]

    # 1. Cada facultad debe contener siempre la opción 'Otra'
    for fac in facultades_esperadas:
        assert fac in oferta
        assert "Otra" in oferta[fac], f"'Otra' no encontrada en {fac}"

    # 2. Inclusiones específicas de la nueva oferta
    ing = oferta["Facultad de Ingenierías"]
    assert "Ingeniería de Datos y Software" in ing
    assert "Ingeniería de Sistemas Cibernéticos" in ing
    assert "Ingeniería de Sistemas (plan anterior)" not in ing
    assert "Creación de Contenidos Digitales" in ing

    emp = oferta["Facultad de Ciencias Empresariales"]
    assert "Administración de Negocios" in emp
    assert "Contaduría Pública" in emp
    assert "Negocios Internacionales" in emp

    arqui = oferta["Facultad de Arquitectura y Artes"]
    assert "Arquitectura" in arqui
    assert "Diseño Industrial" in arqui

    der = oferta["Facultad de Derecho y Ciencias Políticas"]
    assert "Derecho" in der

    psi = oferta["Facultad de Psicología"]
    assert "Psicología" in psi

    edu = oferta["Facultad de Educación"]
    assert "Licenciatura en Educación Preescolar" in edu
    assert "Licenciatura en Educación Artística y Cultural" in edu
    assert "Licenciatura en Educación Física y Deportes" in edu
    assert "Licenciatura en Lengua Castellana" in edu
    assert "Tecnología en Entrenamiento Deportivo" in edu

    # 3. Exclusiones requeridas: Teología, Ciencias Políticas (como programa), Diseño Gráfico, Ingeniería de Sistemas genérica
    todas_carreras = [c for carrs in oferta.values() for c in carrs]
    assert "Teología" not in todas_carreras
    assert "Ciencias Políticas" not in todas_carreras
    assert "Diseño Gráfico" not in todas_carreras
    assert "Ingeniería de Sistemas" not in todas_carreras  # Sin especificar plan


@pytest.mark.unit
def test_settings_obtener_programas_academicos():
    """Verifica que el método en Settings lea el JSON y provea fallback consistente."""
    programas = settings.obtener_programas_academicos()
    assert isinstance(programas, dict)
    assert "Facultad de Ingenierías" in programas
    assert "Otra" in programas["Facultad de Ingenierías"]
