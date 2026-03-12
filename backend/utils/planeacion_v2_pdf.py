from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _as_paragraph_text(value: str) -> str:
    text = value or ""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace("\n", "<br/>")


def render_lesson_plan_v2_pdf(payload: dict) -> BytesIO:
    """Render deterministic PDF for Planeaciones V2.

    No AI calls. It renders exactly the activities/resources stored in DB.
    """

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        alignment=TA_LEFT,
        fontSize=18,
        leading=22,
    )
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, leading=14)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=13)

    elements = []

    elements.append(Paragraph(_as_paragraph_text(payload.get("titulo", "Planeacion")), title))
    elements.append(Spacer(1, 0.12 * inch))
    elements.append(Paragraph(_as_paragraph_text(f"Docente: {payload.get('docente', 'Docente')}"), body))
    elements.append(
        Paragraph(_as_paragraph_text(f"Escuela: {payload.get('escuela', 'Escuela por definir')}"), body)
    )
    elements.append(Paragraph(_as_paragraph_text(f"CCT: {payload.get('cct', 'N/A')}"), body))
    elements.append(
        Paragraph(
            _as_paragraph_text(f"Grado/Grupo: {payload.get('grado', '')} {payload.get('grupo', '')}".strip()),
            body,
        )
    )
    elements.append(Paragraph(_as_paragraph_text(f"Metodologia: {payload.get('metodologia', 'No definida')}"), body))
    elements.append(
        Paragraph(
            _as_paragraph_text(f"Fechas: {payload.get('fecha_inicio', '')} a {payload.get('fecha_fin', '')}"),
            body,
        )
    )
    elements.append(Spacer(1, 0.2 * inch))

    activities = payload.get("activities", [])
    if not activities:
        elements.append(Paragraph("No hay actividades registradas para esta planeacion.", body))
    else:
        for idx, activity in enumerate(activities, start=1):
            elements.append(
                Paragraph(
                    _as_paragraph_text(f"Actividad {idx}: {activity.get('activity_type', 'Sin tipo')}"),
                    h2,
                )
            )
            elements.append(Paragraph(_as_paragraph_text(f"Objetivo: {activity.get('objetivo', '')}"), body))
            if activity.get("descripcion"):
                elements.append(
                    Paragraph(_as_paragraph_text(f"Descripcion: {activity.get('descripcion')}"), body)
                )
            elements.append(Spacer(1, 0.05 * inch))

            resources = activity.get("resources", [])
            if resources:
                table_rows = [[Paragraph("Tipo", body), Paragraph("Titulo", body), Paragraph("Contenido", body)]]
                for resource in resources:
                    table_rows.append(
                        [
                            Paragraph(_as_paragraph_text(str(resource.get("resource_type", ""))), body),
                            Paragraph(_as_paragraph_text(str(resource.get("titulo") or "")), body),
                            Paragraph(_as_paragraph_text(str(resource.get("contenido", ""))), body),
                        ]
                    )

                table = Table(table_rows, colWidths=[1.0 * inch, 1.8 * inch, 3.9 * inch], repeatRows=1)
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("GRID", (0, 0), (-1, -1), 0.7, colors.grey),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 5),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                elements.append(table)
            else:
                elements.append(Paragraph("Recursos: Sin recursos capturados.", body))

            elements.append(Spacer(1, 0.18 * inch))

    doc.build(elements)
    buffer.seek(0)
    return buffer
