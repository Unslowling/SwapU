"""
verificacion_ia.py
------------------
Módulo de Inteligencia Artificial para verificar publicaciones de libros.

Proceso de doble verificación:
  1. Red Neuronal (MobileNetV3-Large pre-entrenado en ImageNet):
     - Clasifica la imagen y detecta si pertenece a categorías de libro/papel.
     - Umbral de confianza configurable.

  2. OCR (EasyOCR):
     - Lee todo el texto visible en la imagen.
     - Busca el código de desafío generado aleatoriamente.

Resultado: dict con campos:
  - es_libro (bool)
  - confianza_libro (float 0-1)
  - codigo_encontrado (bool)
  - texto_detectado (list[str])
  - aprobado (bool)  <- True si ambas verificaciones pasan
  - detalle (str)    <- mensaje legible para el usuario
"""

import io
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ImageNet labels que se asocian a LIBRO / PAPEL / DOCUMENTO
# ---------------------------------------------------------------------------
CLASES_LIBRO = {
    "book",
    "comic book",
    "menu",
    "magazine",
    "newspaper",
    "diary",
    "notebook",
    "envelope",
    "paper towel",
    "jigsaw puzzle",
}

CLASES_EXCLUIDAS = {
    "laptop",
    "screen",
    "monitor",
    "television",
    "remote control",
}


@lru_cache(maxsize=1)
def _cargar_modelo():
    """Carga MobileNetV3-Large con pesos pre-entrenados (se descarga una sola vez ~20 MB)."""
    try:
        import torch
        from torchvision import models, transforms

        modelo = models.mobilenet_v3_large(
            weights=models.MobileNet_V3_Large_Weights.IMAGENET1K_V1
        )
        modelo.eval()

        transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            ),
        ])

        pesos = models.MobileNet_V3_Large_Weights.IMAGENET1K_V1
        clases = pesos.meta["categories"]

        logger.info("MobileNetV3-Large cargado correctamente (%d clases)", len(clases))
        return modelo, transform, clases, torch
    except Exception as exc:
        logger.error("No se pudo cargar el modelo de IA: %s", exc)
        return None, None, None, None


@lru_cache(maxsize=1)
def _cargar_ocr():
    """Carga EasyOCR con soporte para español e inglés."""
    try:
        import easyocr
        reader = easyocr.Reader(["es", "en"], gpu=False, verbose=False)
        logger.info("EasyOCR cargado correctamente")
        return reader
    except Exception as exc:
        logger.warning("EasyOCR no disponible: %s", exc)
        return None


def _clasificar_imagen(imagen_bytes: bytes) -> tuple[bool, float, str]:
    """
    Clasifica la imagen y retorna (es_libro, confianza, nombre_clase).
    Usa MobileNetV3-Large con ImageNet weights.
    Si el modelo no carga o falla, falla cerrado retornando False (pendiente revisión humana).
    """
    try:
        modelo, transform, clases, torch = _cargar_modelo()
        if modelo is None:
            logger.warning("Modelo no disponible - fallando cerrado para revisión manual")
            return False, 0.0, "modelo_no_disponible"

        from PIL import Image
        imagen = Image.open(io.BytesIO(imagen_bytes)).convert("RGB")
        tensor = transform(imagen).unsqueeze(0)

        with torch.no_grad():
            salida = modelo(tensor)
            probabilidades = torch.nn.functional.softmax(salida[0], dim=0)

        # Top-5 predicciones
        top5_probs, top5_indices = torch.topk(probabilidades, 5)
        top5 = [(clases[idx], prob.item()) for idx, prob in zip(top5_indices, top5_probs)]

        logger.info("Top-5 predicciones: %s", top5)

        for nombre_clase, confianza in top5:
            nombre_lower = nombre_clase.lower()
            if nombre_lower in CLASES_LIBRO:
                return True, confianza, nombre_clase
            if any(p in nombre_lower for p in ["book", "text", "page", "paper", "cover"]):
                return True, confianza, nombre_clase

        mejor_clase, mejor_prob = top5[0]
        return False, mejor_prob, mejor_clase

    except Exception as exc:
        logger.error("Error en clasificacion: %s", exc)
        return False, 0.0, "error_clasificacion"


def _extraer_texto_ocr(imagen_bytes: bytes) -> list[str]:
    """
    Extrae todo el texto visible de la imagen usando EasyOCR.
    """
    lector = _cargar_ocr()
    if lector is None:
        return []

    try:
        import numpy as np
        from PIL import Image
        imagen = Image.open(io.BytesIO(imagen_bytes)).convert("RGB")
        arr = np.array(imagen)
        resultados = lector.readtext(arr, detail=0, paragraph=False)
        logger.info("OCR detecto %d fragmentos de texto", len(resultados))
        return [str(r).strip().upper() for r in resultados if str(r).strip()]
    except Exception as exc:
        logger.error("Error en OCR: %s", exc)
        return []


def _codigo_presente(codigo: str, textos: list[str]) -> bool:
    """
    Busca el código de desafío en los textos detectados por OCR.
    Tolera errores típicos de OCR y caligrafía con normalización y similitud difusa.
    """
    if not textos or not codigo:
        return False

    import difflib

    codigo = codigo.upper().strip()
    textos_limpios = [t.upper().strip() for t in textos if t.strip()]
    texto_completo = " ".join(textos_limpios)

    # 1. Coincidencia exacta
    if codigo in texto_completo:
        return True

    def normalizar(s: str) -> str:
        # Errores comunes de confusión visual en OCR
        return (
            s.upper()
            .replace("O", "0")
            .replace("Q", "0")
            .replace("D", "0")
            .replace("I", "1")
            .replace("L", "1")
            .replace("Z", "2")
            .replace("S", "5")
            .replace("B", "8")
            .replace("G", "6")
            .replace(" ", "")
            .replace("-", "")
            .replace("_", "")
        )

    norm_cod = normalizar(codigo)
    norm_txt = normalizar(texto_completo)

    if norm_cod in norm_txt:
        return True

    # 2. Similitud en cada fragmento de texto
    for fragmento in textos_limpios:
        norm_frag = normalizar(fragmento)
        if difflib.SequenceMatcher(None, norm_cod, norm_frag).ratio() >= 0.65:
            return True
        if len(norm_frag) > len(norm_cod):
            for i in range(len(norm_frag) - len(norm_cod) + 1):
                sub = norm_frag[i : i + len(norm_cod)]
                if difflib.SequenceMatcher(None, norm_cod, sub).ratio() >= 0.70:
                    return True

    # 3. Ventana deslizante sobre todo el texto normalizado
    for i in range(max(0, len(norm_txt) - len(norm_cod) + 1)):
        sub = norm_txt[i : i + len(norm_cod)]
        if difflib.SequenceMatcher(None, norm_cod, sub).ratio() >= 0.70:
            return True

    # 4. Mitades del código
    if len(codigo) >= 6:
        m1, m2 = codigo[: len(codigo) // 2], codigo[len(codigo) // 2 :]
        if (m1 in texto_completo or normalizar(m1) in norm_txt) and (
            m2 in texto_completo or normalizar(m2) in norm_txt
        ):
            return True

    return False





def verificar_imagen(
    imagen_bytes: bytes,
    codigo_desafio: str,
    umbral_libro: float | None = None,
) -> dict:
    """
    Punto de entrada principal del módulo de IA.

    Parámetros:
        imagen_bytes   : bytes de la imagen (JPEG/PNG/WebP)
        codigo_desafio : código aleatorio de 8 chars que debe aparecer en la foto
        umbral_libro   : confianza mínima para considerar que es un libro (0-1), si None se toma de settings

    Retorna dict con:
        es_libro         : bool
        confianza_libro  : float
        clase_detectada  : str (nombre de clase ImageNet)
        codigo_encontrado: bool
        texto_detectado  : list[str]
        aprobado         : bool
        detalle          : str
    """
    if umbral_libro is None:
        try:
            from backend_estudiantil.config.settings import settings
            umbral_libro = getattr(settings, "IA_UMBRAL_LIBRO", 0.10)
        except Exception:
            umbral_libro = 0.10

    logger.info("Iniciando verificacion IA para codigo: %s (umbral: %.2f)", codigo_desafio, umbral_libro)

    # Paso 1: ¿Es un libro?
    es_libro, confianza, clase = _clasificar_imagen(imagen_bytes)

    # Paso 2: ¿Está el código en la imagen?
    textos = _extraer_texto_ocr(imagen_bytes)
    codigo_encontrado = _codigo_presente(codigo_desafio, textos)

    # Veredicto
    clase_lower = clase.lower()
    es_pantalla = any(
        excl in clase_lower
        for excl in ["laptop", "screen", "monitor", "television", "remote"]
    )

    es_valido_como_libro = es_libro or (confianza >= umbral_libro and clase not in ("modelo_no_disponible", "error_clasificacion"))

    aprobado = (
        not es_pantalla
        and es_valido_como_libro
        and codigo_encontrado
    )

    # Mensaje legible
    partes = []
    if es_pantalla:
        partes.append(f"La imagen parece ser una pantalla ({clase}), no un libro fisico")
    elif es_libro:
        partes.append(f"Libro detectado: {clase} ({confianza:.0%} confianza)")
    else:
        partes.append(f"Clase detectada: {clase} ({confianza:.0%})")

    if codigo_encontrado:
        partes.append(f"Codigo '{codigo_desafio}' encontrado en la imagen")
    else:
        muestra = ", ".join(textos[:5]) if textos else "ninguno"
        partes.append(
            f"Codigo '{codigo_desafio}' NO encontrado. Texto detectado: {muestra}"
        )

    resultado = {
        "es_libro": es_libro,
        "confianza_libro": round(confianza, 4),
        "clase_detectada": clase,
        "codigo_encontrado": codigo_encontrado,
        "texto_detectado": textos[:10],
        "aprobado": aprobado,
        "detalle": " | ".join(partes),
    }

    logger.info("Resultado IA: %s", resultado)
    return resultado


def precalentar():
    """
    Precarga los modelos en memoria al iniciar el servidor.
    Llamar desde el lifespan de FastAPI para evitar latencia en la primera petición.
    """
    logger.info("Precalentando modelos de IA...")
    _cargar_modelo()
    _cargar_ocr()
    logger.info("Modelos de IA listos")
