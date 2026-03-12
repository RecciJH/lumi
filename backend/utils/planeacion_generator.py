"""Legacy planeación generator deprecated.

This module now provides deterministic helpers only.
No AI calls, no legacy chat/planeación flow logic.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from typing import Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def parse_momentos(metodologia: str) -> list[dict[str, Any]]:
    """Legacy helper kept for compatibility. Returns empty list."""
    _ = metodologia
    return []


def calcular_numero_sesiones(fecha_inicio_str: str, fecha_fin_str: str) -> int:
    """Count business days between two dates."""
    try:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio_str, "%Y-%m-%d")
            fecha_fin = datetime.strptime(fecha_fin_str, "%Y-%m-%d")
        except ValueError:
            fecha_inicio = datetime.strptime(fecha_inicio_str, "%d/%m/%Y")
            fecha_fin = datetime.strptime(fecha_fin_str, "%d/%m/%Y")
    except Exception:
        return 1

    if fecha_fin < fecha_inicio:
        return 1

    dias_habiles = 0
    fecha_actual = fecha_inicio
    while fecha_actual <= fecha_fin:
        if fecha_actual.weekday() < 5:
            dias_habiles += 1
        fecha_actual += timedelta(days=1)
    return max(1, dias_habiles)


def distribuir_momentos_en_sesiones(num_momentos: int, total_sesiones: int) -> dict[int, int]:
    """Compatibility helper. Assigns moments sequentially."""
    if num_momentos <= 0 or total_sesiones <= 0:
        return {}
    return {s: s % num_momentos for s in range(total_sesiones)}


def generate_planeacion_pdf(data: dict) -> BytesIO:
    """Minimal deterministic renderer kept for backward compatibility."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    elements = []

    titulo = str(data.get("titulo", "Planeación"))
    elements.append(Paragraph(titulo, styles["Title"]))
    elements.append(Spacer(1, 12))

    rows = [
        f"Docente: {data.get('nombre_completo', 'Docente')}",
        f"Escuela: {data.get('nombre_escuela', 'Escuela por definir')}",
        f"CCT: {data.get('cct', 'N/A')}",
        f"Grado/Grupo: {data.get('grado', '')} {data.get('grupo', '')}".strip(),
        f"Metodología: {data.get('metodologia', 'No definida')}",
        f"Fechas: {data.get('fecha_inicio', '')} a {data.get('fecha_fin', '')}",
    ]
    for row in rows:
        elements.append(Paragraph(row, styles["Normal"]))
        elements.append(Spacer(1, 6))

    activities = data.get("activities", [])
    if activities:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph("Actividades", styles["Heading2"]))
        for idx, a in enumerate(activities, start=1):
            elements.append(Paragraph(f"{idx}. {a.get('activity_type', 'Actividad')}", styles["Heading3"]))
            elements.append(Paragraph(f"Objetivo: {a.get('objetivo', '')}", styles["Normal"]))
            if a.get("descripcion"):
                elements.append(Paragraph(f"Descripción: {a.get('descripcion')}", styles["Normal"]))
            resources = a.get("resources", [])
            if resources:
                for r in resources:
                    elements.append(
                        Paragraph(
                            f"- [{r.get('resource_type', '')}] {r.get('titulo', '')}: {r.get('contenido', '')}",
                            styles["Normal"],
                        )
                    )
            elements.append(Spacer(1, 6))

    doc.build(elements)
    buffer.seek(0)
    return buffer

