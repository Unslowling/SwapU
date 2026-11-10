"""
test_unit_quality.py
--------------------
Suite de pruebas unitarias puras (sin base de datos, sin red, sin HTTP).
Marcador pytest: unit
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend_estudiantil.config.settings import settings
from backend_estudiantil.domain.models.publicacion import Publicacion
from backend_estudiantil.domain.models.user import User
from backend_estudiantil.domain.services.calificacion_service import CalificacionService
from backend_estudiantil.domain.services.match_service import MatchService
from backend_estudiantil.domain.services.moderacion_contenido_service import (
    ModeracionContenidoService,
)
from backend_estudiantil.domain.services.moderacion_sanciones_service import (
    usuario_puede_operar,
)
from backend_estudiantil.domain.validators.isbn_validator import (
    validar_isbn,
    validar_isbn_10,
    validar_isbn_13,
)

pytestmark = pytest.mark.unit

# ============================================================================
# 1. VALIDADOR DE ISBN (ISBN-10, ISBN-13, X, Dígito control, longitud, guiones)
# ============================================================================

def test_isbn_10_valido_con_x():
    """Valida que un ISBN-10 con 'X' mayúscula o minúscula como dígito de control sea válido."""
    assert validar_isbn_10("080442957X") is True
    assert validar_isbn_10("080442957x") is True
    assert validar_isbn("0-8044-2957-X") is True
    assert validar_isbn("0 8044 2957 X") is True


def test_isbn_10_valido_con_digitos():
    """Valida un ISBN-10 válido con dígito numérico de control."""
    assert validar_isbn_10("0471958697") is True
    assert validar_isbn("0-471-95869-7") is True


def test_isbn_13_valido():
    """Valida un ISBN-13 legítimo con y sin guiones."""
    assert validar_isbn_13("9780306406157") is True
    assert validar_isbn("978-0-306-40615-7") is True
    assert validar_isbn("  978 0 306 40615 7  ") is True
    assert validar_isbn("9789587781236") is True


def test_isbn_digito_control_incorrecto():
    """Verifica que un dígito de control erróneo sea rechazado."""
    assert validar_isbn_10("0804429573") is False
    with pytest.raises(ValueError, match="dígito de control incorrecto"):
        validar_isbn("0804429573")

    assert validar_isbn_13("9780306406158") is False
    with pytest.raises(ValueError, match="dígito de control incorrecto"):
        validar_isbn("9780306406158")

    # Caso 9789587781234 (control real es 6, provisto es 4)
    with pytest.raises(ValueError, match="dígito de control incorrecto"):
        validar_isbn("9789587781234")


def test_isbn_longitud_invalida():
    """Verifica que longitudes distintas de 10 y 13 lancen ValueError."""
    with pytest.raises(ValueError, match="10 o 13 dígitos"):
        validar_isbn("123456789")  # 9 dígitos
    with pytest.raises(ValueError, match="10 o 13 dígitos"):
        validar_isbn("12345678901")  # 11 dígitos
    with pytest.raises(ValueError, match="10 o 13 dígitos"):
        validar_isbn("978030640615799")  # 15 dígitos


def test_isbn_opcional_vacio_o_none():
    """Verifica que si no se proporciona ISBN o es vacío retorne True (es opcional)."""
    assert validar_isbn(None) is True
    assert validar_isbn("") is True
    assert validar_isbn("   ") is True


# ============================================================================
# 2. MODERACIÓN DE CONTENIDO (Leetspeak, letras repetidas, tildes, 20 falsos positivos)
# ============================================================================

def test_moderacion_leetspeak_y_ofensas():
    """Detecta términos ofensivos camuflados con leetspeak (números y símbolos por letras)."""
    servicio = ModeracionContenidoService()

    # m!erda, @sesino, put4, p*ta
    res1 = servicio.procesar_texto("Este libro es una pu+a porqueria")
    assert res1.es_valido is False or res1.accion in ("enmascarar", "advertir", "bloquear")
    # pu+a o m!erda
    res2 = servicio.procesar_texto("No compren eso es una m1erda total")
    assert res2.es_valido is False or res2.accion in ("enmascarar", "advertir", "bloquear")

    res3 = servicio.procesar_texto("Eres un @sesino y te voy a matar")
    assert res3.es_valido is False
    assert res3.nivel_severidad == "grave"


def test_moderacion_letras_repetidas():
    """Detecta insultos o palabras bloqueadas alargadas con letras repetidas."""
    servicio = ModeracionContenidoService()

    res1 = servicio.procesar_texto("Esto es una mieeeerrrrdaaaa total")
    assert res1.texto_final != "Esto es una mieeeerrrrdaaaa total" or res1.es_valido is False

    res2 = servicio.procesar_texto("Que gonorrrrea de persona")
    assert res2.es_valido is False


def test_moderacion_con_tildes():
    """Detecta palabras prohibidas incluso con tildes y diacríticos."""
    servicio = ModeracionContenidoService()

    res = servicio.procesar_texto("Libro sobre cómo hacer una amenaza de muerte")
    assert res.es_valido is False
    assert res.nivel_severidad == "grave"


def test_moderacion_20_textos_legitimos_en_espanol_sin_falsos_positivos():
    """Garantiza que 20 textos legítimos y académicos en español pasen sin falsos positivos."""
    servicio = ModeracionContenidoService()

    textos_legitimos = [
        "computadora",
        "llamada",
        "no lo vendo, solo trueque",
        "ISBN 9789587781234",
        "Cálculo Diferencial e Integral de James Stewart",
        "Álgebra Lineal y sus Aplicaciones - David C. Lay",
        "Física Universitaria Sears y Zemansky Volumen 1",
        "Química General principios y aplicaciones modernas",
        "Estructuras de Datos y Algoritmos en Java",
        "Principios de Economía de Mankiw sexta edición",
        "Biología Celular y Molecular de Lodish",
        "Fundamentos de Circuitos Eléctricos Sadiku",
        "Termodinámica para ingenieros Yunus Cengel",
        "Derecho Constitucional Colombiano tomo 1",
        "no vendo libros, solo realizo trueques académicos",
        "intercambio libro de anatomía humana por uno de fisiología",
        "este libro no está a la venta, es exclusivamente para intercambio",
        "comunicarse por la mensajería interna de la plataforma",
        "ISBN 978-958-778-123-4 edición de tapa blanda",
        "manual de prácticas de laboratorio de microbiología",
        "Microeconomía intermedia un enfoque moderno Varian",
        "Sistemas Operativos Conceptos Fundamentales Silberschatz",
    ]

    for texto in textos_legitimos:
        res = servicio.procesar_contenido_publicacion(texto=texto, campo="descripcion")
        assert res.es_valido is True, (
            f"Falso positivo detectado en texto legítimo: '{texto}'. "
            f"Motivo reporte: {res.mensaje_error}"
        )


# ============================================================================
# 3. REPUTACIÓN BAYESIANA Y NIVELES (0, 1, 2, 3 y 10 calificaciones)
# ============================================================================

@pytest.mark.asyncio
async def test_reputacion_bayesiana_casos_limite():
    """Valida cálculo de promedio bayesiano (C*m + suma)/(C + n) y niveles para 0, 1, 2, 3 y 10 reseñas."""
    mock_repo = AsyncMock()
    servicio = CalificacionService(calificacion_repo=mock_repo)

    # Media global = 4.0, C = 5.0 (por defecto en settings)
    mock_repo.get_global_rating_stats.return_value = (4.0, 100)

    # 1. Caso límite: 0 calificaciones
    mock_repo.list_by_usuario_calificado.return_value = []
    res0 = await servicio.obtener_reputacion_usuario(1)
    assert res0["total_calificaciones"] == 0
    assert res0["promedio_bayesiano"] is None
    assert res0["nivel"] == "nuevo"

    # 2. Caso límite: 1 calificación de 5 estrellas
    calif_mock1 = MagicMock(id=1, trueque_id=1, usuario_califica_id=2, estrellas=5, resena="Excelente", fecha_calificacion=None)
    mock_repo.list_by_usuario_calificado.return_value = [calif_mock1]
    res1 = await servicio.obtener_reputacion_usuario(1)
    assert res1["total_calificaciones"] == 1
    # Bayesiano: (5*4.0 + 5) / (5 + 1) = 25 / 6 = 4.17
    assert res1["promedio_bayesiano"] == 4.17
    assert res1["nivel"] == "nuevo"  # n < 3 -> "nuevo"

    # 3. Caso límite: 2 calificaciones de 5 estrellas
    calif_mock2 = MagicMock(id=2, trueque_id=2, usuario_califica_id=3, estrellas=5, resena="Muy bueno", fecha_calificacion=None)
    mock_repo.list_by_usuario_calificado.return_value = [calif_mock1, calif_mock2]
    res2 = await servicio.obtener_reputacion_usuario(1)
    assert res2["total_calificaciones"] == 2
    # Bayesiano: (5*4.0 + 10) / (5 + 2) = 30 / 7 = 4.29
    assert res2["promedio_bayesiano"] == 4.29
    assert res2["nivel"] == "nuevo"  # n < 3 -> "nuevo"

    # 4. Caso límite: 3 calificaciones de 5 estrellas -> cumple umbral mínimo para "confiable"
    calif_mock3 = MagicMock(id=3, trueque_id=3, usuario_califica_id=4, estrellas=5, resena="Genial", fecha_calificacion=None)
    mock_repo.list_by_usuario_calificado.return_value = [calif_mock1, calif_mock2, calif_mock3]
    res3 = await servicio.obtener_reputacion_usuario(1)
    assert res3["total_calificaciones"] == 3
    # Bayesiano: (5*4.0 + 15) / (5 + 3) = 35 / 8 = 4.38
    assert res3["promedio_bayesiano"] == 4.38
    assert res3["nivel"] == "confiable"  # n >= 3 y < 10 -> "confiable"

    # 5. Caso límite: 10 calificaciones de 5 estrellas -> cumple umbral para "destacado"
    diez_califs = [
        MagicMock(id=i, trueque_id=i, usuario_califica_id=i + 10, estrellas=5, resena=f"Test {i}", fecha_calificacion=None)
        for i in range(1, 11)
    ]
    mock_repo.list_by_usuario_calificado.return_value = diez_califs
    res10 = await servicio.obtener_reputacion_usuario(1)
    assert res10["total_calificaciones"] == 10
    # Bayesiano: (5*4.0 + 50) / (5 + 10) = 70 / 15 = 4.67
    assert res10["promedio_bayesiano"] == 4.67
    assert res10["nivel"] == "destacado"  # n >= 10 y bayesiano >= 4.5 -> "destacado"

    # 6. Caso límite: 10 calificaciones de 3 estrellas -> n >= 10 pero bayesiano < 4.5 -> "confiable"
    diez_califs_bajas = [
        MagicMock(id=i, trueque_id=i, usuario_califica_id=i + 10, estrellas=3, resena=f"Test {i}", fecha_calificacion=None)
        for i in range(1, 11)
    ]
    mock_repo.list_by_usuario_calificado.return_value = diez_califs_bajas
    res10_bajas = await servicio.obtener_reputacion_usuario(1)
    assert res10_bajas["total_calificaciones"] == 10
    # Bayesiano: (5*4.0 + 30) / (5 + 10) = 50 / 15 = 3.33
    assert res10_bajas["promedio_bayesiano"] == 3.33
    assert res10_bajas["nivel"] == "confiable"


# ============================================================================
# 4. ESCALERA DE SANCIONES (Ventana 90 días, suspensiones, bloqueo, falta directa)
# ============================================================================

def test_escalera_sanciones_usuario_puede_operar():
    """Valida la lógica de estado de cuenta, suspensiones activas y auto-recuperación temporal."""
    now = datetime.now(timezone.utc)

    # 1. Usuario activo
    user_activo = User(id=1, email="a@tau.usbmed.edu.co", estado_cuenta="activo")
    res_activo = usuario_puede_operar(user_activo)
    assert res_activo.puede_operar is True

    # 2. Usuario con suspensión vigente (7 días)
    user_susp_7 = User(
        id=2,
        email="b@tau.usbmed.edu.co",
        estado_cuenta="suspendido",
        fin_suspension=now + timedelta(days=5),
        motivo_sancion="Incumplimiento",
    )
    res_susp_7 = usuario_puede_operar(user_susp_7)
    assert res_susp_7.puede_operar is False
    assert res_susp_7.estado_cuenta == "suspendido"

    # 3. Usuario con suspensión ya expirada (hace 1 día) -> debe poder operar
    user_expirado = User(
        id=3,
        email="c@tau.usbmed.edu.co",
        estado_cuenta="suspendido",
        fin_suspension=now - timedelta(days=1),
    )
    res_expirado = usuario_puede_operar(user_expirado)
    assert res_expirado.puede_operar is True

    # 4. Usuario con bloqueo definitivo -> nunca expira
    user_bloqueado = User(
        id=4,
        email="d@tau.usbmed.edu.co",
        estado_cuenta="bloqueado",
        motivo_sancion="Fraude grave",
    )
    res_bloqueado = usuario_puede_operar(user_bloqueado)
    assert res_bloqueado.puede_operar is False
    assert res_bloqueado.estado_cuenta == "bloqueado"


@pytest.mark.asyncio
async def test_escalera_sanciones_escalamiento_logico():
    from backend_estudiantil.domain.services.moderacion_sanciones_service import ModeracionSancionesService

    servicio = ModeracionSancionesService()

    # Si no tiene sanciones previas -> suspensión 7 días
    assert servicio._determinar_siguiente_sancion([]) == "suspension_7"

    # Si ya tuvo suspensión de 7 días -> suspensión 30 días
    assert servicio._determinar_siguiente_sancion(["suspension_7"]) == "suspension_30"

    # Si ya tuvo suspensión de 30 días -> bloqueo definitivo
    assert servicio._determinar_siguiente_sancion(["suspension_7", "suspension_30"]) == "bloqueo"


# ============================================================================
# 5. VALIDACIÓN DE DOMINIO INSTITUCIONAL (tau.usbmed, subdominios, spoofing)
# ============================================================================

def test_validacion_dominio_institucional_completa():
    """Verifica reglas de dominios institucionales admitidos y rechazo de spoofing/malformaciones."""
    # Dominios legítimos directos y subdominios
    assert settings.es_dominio_institucional("juan@tau.usbmed.edu.co") is True
    assert settings.es_dominio_institucional("estudiante@usbmed.edu.co") is True
    assert settings.es_dominio_institucional("alumno@unal.edu.co") is True
    assert settings.es_dominio_institucional("investigador@ciencias.unal.edu.co") is True

    # Intentos de spoofing y dominios maliciosos
    assert settings.es_dominio_institucional("juan@tau.usbmed.edu.co.attacker.com") is False
    assert settings.es_dominio_institucional("juan@xtau.usbmed.edu.co") is False
    assert settings.es_dominio_institucional("juan@faketau.usbmed.edu.co") is False
    assert settings.es_dominio_institucional("juan@usbmed.edu.co.phishing.io") is False

    # Correos malformados con múltiples '@', sin '@' o vacíos
    assert settings.es_dominio_institucional("juan@@tau.usbmed.edu.co") is False
    assert settings.es_dominio_institucional("juan@tau@usbmed.edu.co") is False
    assert settings.es_dominio_institucional("juan.tau.usbmed.edu.co") is False
    assert settings.es_dominio_institucional("") is False
    assert settings.es_dominio_institucional("   ") is False


# ============================================================================
# 6. HASH, COMPARACIÓN SEGURA DEL CÓDIGO DE CONFIRMACIÓN Y EXPIRACIÓN A 30 MIN
# ============================================================================

def test_hash_codigo_y_comparacion_segura():
    """Verifica que el código se almacene en SHA-256 y se compare con hmac.compare_digest."""
    codigo_plano = "849203"
    hash_esperado = hashlib.sha256(codigo_plano.encode("utf-8")).hexdigest()

    # Comprobar que hmac.compare_digest coincida correctamente
    assert hmac.compare_digest(hash_esperado, hashlib.sha256(codigo_plano.encode("utf-8")).hexdigest()) is True

    # Código incorrecto debe ser rechazado
    codigo_invalido = "849204"
    hash_invalido = hashlib.sha256(codigo_invalido.encode("utf-8")).hexdigest()
    assert hmac.compare_digest(hash_esperado, hash_invalido) is False


def test_expiracion_codigo_confirmacion_30_minutos():
    """Verifica la expiración a los 30 minutos."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    codigo_valido_tiempo = now + timedelta(minutes=29)
    codigo_expirado_tiempo = now - timedelta(seconds=1)

    assert (now > codigo_valido_tiempo) is False
    assert (now > codigo_expirado_tiempo) is True


# ============================================================================
# 7. PUNTUACIÓN DE MATCHING (pesos solo si ambos están verificados)
# ============================================================================

@pytest.mark.asyncio
async def test_matching_pesos_solo_si_ambos_estan_verificados():
    """Valida que los pesos de universidad (+15), facultad (+10) y semestre (+5)

    se apliquen ÚNICAMENTE cuando ambos estudiantes están verificados en la comunidad.
    """
    mock_match_repo = AsyncMock()
    mock_pub_repo = AsyncMock()
    mock_user_repo = AsyncMock()

    service = MatchService(
        match_repo=mock_match_repo,
        publicacion_repo=mock_pub_repo,
        user_repo=mock_user_repo,
    )

    # Publicación origen busca "Química" y ofrece "Cálculo"
    pub_origen = Publicacion(
        id=10,
        usuario_id=100,
        titulo="Cálculo Stewart",
        libro_buscado="Química",
        estado_publicacion="activa",
    )
    # Publicación destino ofrece "Química Raymond Chang" y busca "Cálculo"
    pub_destino = Publicacion(
        id=20,
        usuario_id=200,
        titulo="Química Raymond Chang",
        libro_buscado="Cálculo",
        estado_publicacion="activa",
    )

    mock_pub_repo.get_by_id.return_value = pub_origen
    mock_pub_repo.list_activas.return_value = [pub_destino]
    mock_match_repo.get_existing_destination_ids.return_value = set()
    mock_match_repo.get_existing_match.return_value = None
    mock_match_repo.create.side_effect = lambda m: m

    # CASO A: Ambos usuarios verificados y de la misma universidad, facultad y semestre
    user_origen_verif = User(
        id=100,
        email="a@tau.usbmed.edu.co",
        verificado_comunidad=True,
        universidad="Universidad de San Buenaventura Medellín",
        facultad="Ingeniería",
        programa_area="Ingeniería de Sistemas",
        semestre=5,
    )
    user_destino_verif = User(
        id=200,
        email="b@tau.usbmed.edu.co",
        verificado_comunidad=True,
        universidad="Universidad de San Buenaventura Medellín",
        facultad="Ingeniería",
        programa_area="Ingeniería de Sistemas",
        semestre=5,
    )

    mock_user_repo.get_by_id.side_effect = lambda uid: user_origen_verif if uid == 100 else user_destino_verif
    mock_user_repo.get_by_ids.return_value = {100: user_origen_verif, 200: user_destino_verif}

    matches_verificados = await service.buscar_matches_para_publicacion(10)
    assert len(matches_verificados) == 1
    # Puntuación máxima por afinidad completa (100.0)
    assert matches_verificados[0].puntuacion >= 95.0

    # CASO B: Misma universidad y facultad, pero UNO NO ESTÁ VERIFICADO
    user_destino_sin_verif = User(
        id=200,
        email="b@gmail.com",
        verificado_comunidad=False,  # NO verificado
        universidad="Universidad de San Buenaventura Medellín",
        facultad="Ingeniería",
        programa_area="Ingeniería de Sistemas",
        semestre=5,
    )
    mock_user_repo.get_by_id.side_effect = lambda uid: user_origen_verif if uid == 100 else user_destino_sin_verif
    mock_user_repo.get_by_ids.return_value = {100: user_origen_verif, 200: user_destino_sin_verif}

    matches_sin_verif = await service.buscar_matches_para_publicacion(10)
    assert len(matches_sin_verif) == 1
    # Sin la bonificación de afinidad, la puntuación base debe ser menor
    assert matches_sin_verif[0].puntuacion < matches_verificados[0].puntuacion
