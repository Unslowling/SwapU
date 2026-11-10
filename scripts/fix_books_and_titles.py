"""
scripts/fix_books_and_titles.py
--------------------------------
Limpia publicaciones de prueba residuales (Libro 0, Libro 1, Libro P1, etc.),
sanea los títulos de las publicaciones sintéticas (removiendo 'Ref #...' y 'Vol. ...'),
y asegura que los 10 libros principales de la USBMED tengan fecha actual y máxima prioridad.
"""

import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath("."))

import asyncio
from backend_estudiantil.adapters.db import get_session_factory
from sqlalchemy import text


async def main():
    factory = get_session_factory()
    async with factory() as session:
        # 1. Inactivar o limpiar publicaciones residuales de pruebas automáticas
        print("[*] Limpiando publicaciones residuales de pruebas automáticas (Libro %, Test%)...")
        await session.execute(
            text("""
                UPDATE publicaciones 
                SET estado_publicacion = 'inactiva' 
                WHERE titulo LIKE 'Libro %' 
                   OR titulo LIKE 'Test%' 
                   OR titulo LIKE 'Libro A %' 
                   OR titulo LIKE 'Libro B %'
                   OR titulo LIKE 'Libro P%'
                   OR titulo LIKE 'Intento Concurrente%'
                   OR titulo = 'fisica ll'
                   OR id = 11
                   OR titulo LIKE 'Guía de física para b**o novato'
            """)
        )

        # 2. Sanear títulos sintéticos para que tengan nombres reales de libros
        print("[*] Saneando títulos de publicaciones sintéticas...")
        await session.execute(
            text("""
                UPDATE publicaciones 
                SET titulo = regexp_replace(titulo, ' \\(Vol\\. \\d+\\) - Ref #\\d+', ''),
                    descripcion = 'Ejemplar en excelente estado académico, hojas intactas y sin marcas. Disponible para intercambio en la USBMED.'
                WHERE titulo LIKE '%Ref #%'
            """)
        )

        # 3. Asegurar que los 10 libros canónicos de USBMED tengan fecha actual y estén activos
        print("[*] Actualizando los 10 libros canónicos de USBMED al tope del catálogo...")
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
        
        libros_canonicos = [
            (285, "Cálculo: Trascendentes Tempranas", "James Stewart", 3, "Libro de cálculo diferencial e integral, pasta dura, sin anotaciones. Entrega en Campus Salento (Bello) de la USBMED."),
            (286, "Clean Code: Manual de Desarrollo Ágil", "Robert C. Martin (Uncle Bob)", 1, "El clásico indiscutible sobre buenas prácticas de código limpio, refactorización y testing. USBMED Campus Salento."),
            (287, "Inteligencia Artificial: Un Enfoque Moderno", "Stuart Russell y Peter Norvig", 1, "Referencia fundamental en IA moderna, redes neuronales y heurísticas. USBMED Campus Salento."),
            (288, "Principios de Microeconomía", "N. Gregory Mankiw", 5, "Fundamentos de teoría del consumidor, estructuras de mercado y microeconomía. USBMED Campus San Benito."),
            (289, "Tratado de Fisiología Médica", "Arthur C. Guyton & John E. Hall", 2, "Texto insustituible sobre fisiología de sistemas y neurobiología. USBMED Campus San Benito."),
            (290, "Sapiens: De animales a dioses", "Yuval Noah Harari", 6, "Breve historia de la humanidad, desde la revolución cognitiva. USBMED Campus San Benito."),
            (291, "Cien Años de Soledad", "Gabriel García Márquez", 6, "Obra cumbre de la literatura en español y realismo mágico. USBMED Campus Salento."),
            (292, "1984", "George Orwell", 6, "Clásico distópico sobre vigilancia masiva y pensamiento crítico. USBMED Campus San Benito."),
            (293, "Física Universitaria con Física Moderna", "Sears, Zemansky, Young & Freedman", 3, "Fundamentos de mecánica, electromagnetismo y óptica. USBMED Campus Salento."),
            (294, "Teoría General del Derecho", "Norberto Bobbio", 4, "Filosofía y norma jurídica fundamental para estudiantes de Derecho de la USBMED."),
        ]

        for pub_id, titulo, autor, cat_id, desc in libros_canonicos:
            await session.execute(
                text("""
                    UPDATE publicaciones 
                    SET titulo = :titulo,
                        autor = :autor,
                        categoria_id = :cat_id,
                        descripcion = :desc,
                        estado_publicacion = 'activa',
                        fecha_publicacion = :fpub
                    WHERE id = :id
                """),
                {"id": pub_id, "titulo": titulo, "autor": autor, "cat_id": cat_id, "desc": desc, "fpub": now_dt}
            )

        # 4. Actualizar universidades de los usuarios 483..492 para que sean USBMED
        print("[*] Asegurando universidad USBMED para los usuarios titulares...")
        await session.execute(
            text("""
                UPDATE usuarios 
                SET universidad = 'Universidad de San Buenaventura Medellín (USBMED)'
                WHERE id BETWEEN 483 AND 492
            """)
        )

        await session.commit()
        print("[+] Base de datos saneada con éxito.")


if __name__ == "__main__":
    asyncio.run(main())
