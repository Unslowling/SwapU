"""
isbn_validator.py
-----------------
Validador de formato y dígito de control para códigos ISBN-10 e ISBN-13
conforme a la norma ISO 2108.
"""

import re


def validar_isbn_10(isbn: str) -> bool:
    """Valida un ISBN-10 con algoritmo de suma ponderada módulo 11."""
    if len(isbn) != 10:
        return False
    if not re.match(r"^\d{9}[\dX]$", isbn, re.IGNORECASE):
        return False

    total = 0
    for i in range(9):
        total += int(isbn[i]) * (10 - i)

    ultimo = isbn[9].upper()
    total += 10 if ultimo == "X" else int(ultimo)

    return total % 11 == 0


def validar_isbn_13(isbn: str) -> bool:
    """Valida un ISBN-13 con algoritmo EAN módulo 10."""
    if len(isbn) != 13 or not isbn.isdigit():
        return False

    total = 0
    for i in range(13):
        factor = 1 if (i % 2 == 0) else 3
        total += int(isbn[i]) * factor

    return total % 10 == 0


def validar_isbn(isbn_candidato: str | None) -> bool:
    """Valida un ISBN si es provisto. Retorna True si es válido o si es None/vacío.
    
    Lanza ValueError si el valor provisto no cumple el formato o dígito de control.
    """
    if not isbn_candidato or not str(isbn_candidato).strip():
        return True

    # Remover guiones y espacios en blanco comunes en la notación de ISBN
    limpio = re.sub(r"[\s\-]+", "", str(isbn_candidato).strip())

    if len(limpio) == 10:
        if not validar_isbn_10(limpio):
            raise ValueError(
                f"El ISBN '{isbn_candidato}' no es un ISBN-10 válido (dígito de control incorrecto)."
            )
        return True
    elif len(limpio) == 13:
        if not validar_isbn_13(limpio):
            raise ValueError(
                f"El ISBN '{isbn_candidato}' no es un ISBN-13 válido (dígito de control incorrecto)."
            )
        return True
    else:
        raise ValueError(
            f"El ISBN '{isbn_candidato}' debe tener 10 o 13 dígitos numéricos válidos."
        )
