"""
pdf_renderer.py

Renderer base (bonito, limpio y consistente) para la planeación de Lumi usando ReportLab (Platypus).

Objetivo:
- Visual agradable (tipografía, jerarquía, tablas y espaciado)
- Sin imágenes, sin temas "decorativos" y sin dependencias de internet
- Fácil de extender: el documento se construye por bloques (sections)
"""

from __future__ import annotations

import json
import ast
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
from utils.preescolar.saberes_catalog import normalize_text
from xml.sax.saxutils import escape as _xml_escape


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _safe_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _bullets(items: Iterable[Any]) -> str:
    parts = [_safe_text(x) for x in items]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    # Usamos bullet numérico para evitar problemas de codificación en algunos entornos.
    return "<br/>".join([f"&#8226; {_xml_escape(p)}" for p in parts])


def _grado_a_ordinal(grado: str) -> str:
    """
    Convierte "2" / "2°" / "Segundo" -> "SEGUNDO GRADO" (como en el ejemplo).
    Si no se puede inferir, regresa el texto en mayúsculas.
    """
    g = _safe_text(grado)
    if not g:
        return ""
    g_upper = g.upper()
    if "PRIM" in g_upper or g_upper.strip() == "1":
        return "PRIMER GRADO"
    if "SEG" in g_upper or g_upper.strip() == "2":
        return "SEGUNDO GRADO"
    if "TERC" in g_upper or g_upper.strip() == "3":
        return "TERCER GRADO"
    digits = "".join([c for c in g_upper if c.isdigit()])
    if digits == "1":
        return "PRIMER GRADO"
    if digits == "2":
        return "SEGUNDO GRADO"
    if digits == "3":
        return "TERCER GRADO"
    return g_upper


def _short_temporalidad(value: Any, *, sesiones: int | None = None) -> str:
    """
    Normaliza TEMPORALIDAD para portada al estilo SEP (ej. "1 SEMANA"), evitando listas largas.
    """
    text = _safe_text(value)
    if text and not (text.startswith("{") or text.startswith("[")):
        # Si es corto (ej. "1 SEMANA") lo dejamos; si no, lo convertimos a un resumen.
        if len(text) <= 24 and "\n" not in text:
            return text
    if sesiones is not None and sesiones > 0:
        if sesiones <= 5:
            return "1 SEMANA"
        if sesiones <= 10:
            return "2 SEMANAS"
        return f"{sesiones} SESIONES"
    return "1 SEMANA"


def _ensure_theme_fonts(theme: "PdfTheme") -> "PdfTheme":
    """
    Intenta registrar Calibri (Windows) para parecerse al PDF de ejemplo.
    Si no está disponible, usa Helvetica.
    """
    candidates = [
        ("Calibri", r"C:\\Windows\\Fonts\\calibri.ttf"),
        ("Calibri-Bold", r"C:\\Windows\\Fonts\\calibrib.ttf"),
    ]
    registered = set(pdfmetrics.getRegisteredFontNames())
    for name, path in candidates:
        if name in registered:
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, path))
        except Exception:
            pass

    registered = set(pdfmetrics.getRegisteredFontNames())
    regular = theme.font_regular if theme.font_regular in registered else "Helvetica"
    bold = theme.font_bold if theme.font_bold in registered else "Helvetica-Bold"
    return replace(theme, font_regular=regular, font_bold=bold)


def _maybe_json_to_bullets(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, (dict, list)):
        parsed = value
    else:
        text = _safe_text(value)
        if not text:
            return ""
        if not (text.startswith("{") or text.startswith("[")):
            return _xml_escape(text)
        try:
            parsed = json.loads(text)
        except Exception:
            # A veces el modelo devuelve representaciones tipo dict de Python (comillas simples).
            try:
                parsed = ast.literal_eval(text)  # noqa: S307 (solo literales)
            except Exception:
                return _xml_escape(text)

    if isinstance(parsed, dict):
        items = [f"{k}: {_safe_text(v)}" for k, v in parsed.items()]
        return _bullets(items) or _xml_escape(_safe_text(value))
    if isinstance(parsed, list):
        return _bullets(parsed) or _xml_escape(_safe_text(value))
    return _xml_escape(_safe_text(value))


def _body_markup(value: Any) -> str:
    """
    Convierte texto con saltos de línea, dict/list o JSON-like a markup de Paragraph.
    """
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _maybe_json_to_bullets(value)
    text = _safe_text(value)
    if not text:
        return ""
    if text.startswith("{") or text.startswith("["):
        return _maybe_json_to_bullets(text)
    return _xml_escape(text).replace("\n", "<br/>")


@dataclass(frozen=True)
class PdfTheme:
    # Tipografía (intentamos Calibri para parecerse al formato SEP de ejemplo).
    font_regular: str = "Calibri"
    font_bold: str = "Calibri-Bold"

    # Colores sobrios (sin “diseños”).
    primary: colors.Color = colors.black
    secondary: colors.Color = colors.black
    text: colors.Color = colors.black
    muted: colors.Color = colors.HexColor("#4a4a4a")
    table_header_bg: colors.Color = colors.HexColor("#f2f2f2")
    table_grid: colors.Color = colors.black
    table_zebra: colors.Color = colors.white


@dataclass(frozen=True)
class PdfRenderOptions:
    pagesize: tuple = LETTER
    title: str = "Lumi — Planeación didáctica"
    include_raw_master_json: bool = False
    footer_text: str = ""
    include_page_numbers: bool = False
    include_evaluacion: bool = False
    include_firmas: bool = True


StylesFactory = Callable[[PdfTheme], Dict[str, ParagraphStyle]]


def default_styles(theme: PdfTheme) -> Dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()

    base = sample["Normal"]
    base.fontName = theme.font_regular
    base.fontSize = 11
    base.leading = 14
    base.textColor = theme.text

    return {
        "title": ParagraphStyle(
            "LumiTitle",
            parent=sample["Title"],
            fontName=theme.font_bold,
            fontSize=12,
            leading=14,
            textColor=theme.text,
            alignment=1,  # CENTER
            spaceAfter=6,
        ),
        "subtitle": ParagraphStyle(
            "LumiSubtitle",
            parent=base,
            fontName=theme.font_regular,
            fontSize=11,
            leading=14,
            textColor=theme.muted,
            spaceAfter=6,
        ),
        "h1": ParagraphStyle(
            "LumiH1",
            parent=sample["Heading1"],
            fontName=theme.font_bold,
            fontSize=11.5,
            leading=14,
            textColor=theme.text,
            alignment=1,  # CENTER
            spaceBefore=8,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "LumiH2",
            parent=sample["Heading2"],
            fontName=theme.font_bold,
            fontSize=11,
            leading=14,
            textColor=theme.text,
            spaceBefore=6,
            spaceAfter=4,
        ),
        "normal": ParagraphStyle("LumiNormal", parent=base),
        "muted": ParagraphStyle(
            "LumiMuted",
            parent=base,
            fontSize=10,
            leading=12,
            textColor=theme.muted,
        ),
        "small": ParagraphStyle(
            "LumiSmall",
            parent=base,
            fontSize=10,
            leading=12,
            textColor=theme.text,
        ),
        "code": ParagraphStyle(
            "LumiCode",
            parent=base,
            fontName="Courier",
            fontSize=8,
            leading=10,
            textColor=theme.muted,
        ),
    }


class PdfBlock:
    id: str
    title: Optional[str]

    def __init__(self, block_id: str, title: Optional[str] = None):
        self.id = block_id
        self.title = title

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        raise NotImplementedError


class CoverBlock(PdfBlock):
    def __init__(self):
        super().__init__("cover", None)

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        planeacion = master_json.get("planeacion") or {}
        datos = planeacion.get("datos_generales") or {}
        proyecto = planeacion.get("proyecto") or {}
        sesiones = planeacion.get("sesiones") or []

        escuela = _safe_text(datos.get("escuela"))
        cct = _safe_text((master_json.get("input") or {}).get("cct") or datos.get("cct"))
        docente = _safe_text(datos.get("docente"))
        grado_grupo = _safe_text(datos.get("grado_y_grupo")) or f"{_safe_text(datos.get('grado'))} {_safe_text(datos.get('grupo'))}".strip()
        fecha = _safe_text((master_json.get("input") or {}).get("fecha") or datos.get("fecha") or "")

        nombre_proy = _safe_text(proyecto.get("nombre_proyecto"))
        temporalidad = _short_temporalidad(
            proyecto.get("temporalidad"),
            sesiones=len(sesiones) if isinstance(sesiones, list) else None,
        )

        # Ejes articuladores / Campos formativos (checklist)
        ejes = planeacion.get("ejes_articuladores") or []
        campos = planeacion.get("campos_formativos") or []

        # Tabla grande de portada (un solo cuadro desde "Jardín de niños" hasta "Temporalidad")
        cover_center = ParagraphStyle("CoverCenter", parent=styles["normal"], alignment=1, fontName=theme.font_bold)
        nombre_row = Paragraph(
            f"<b>NOMBRE DEL PROYECTO:</b> “{_xml_escape(nombre_proy)}”" if nombre_proy else "<b>NOMBRE DEL PROYECTO:</b>",
            styles["normal"],
        )
        proyecto_title = Paragraph("PROYECTO", cover_center)
        problematica = Paragraph(f"<b>PROBLEMÁTICA :</b> {_body_markup(proyecto.get('problematica'))}", styles["normal"])
        justificacion = Paragraph(f"<b>JUSTIFICACION:</b> {_body_markup(proyecto.get('justificacion'))}", styles["normal"])
        proposito = Paragraph(f"<b>PROPOSITO:</b> {_body_markup(proyecto.get('proposito'))}", styles["normal"])
        temporalidad_row = Paragraph(f"<b>TEMPORALIDAD:</b> {_xml_escape(temporalidad)}", styles["normal"])

        cover_data: list[list[Any]] = [
            ["Jardín de niños:", escuela, "CCT:", cct],
            ["Educadora:", docente, "Grado y grupo:", grado_grupo],
            ["FECHA:", fecha, "", ""],
            [nombre_row, "", "", ""],
            [proyecto_title, "", "", ""],
            [problematica, "", "", ""],
            [justificacion, "", "", ""],
            [proposito, "", "", ""],
            [temporalidad_row, "", "", ""],
        ]

        cover_tbl = Table(
            cover_data,
            colWidths=[1.35 * inch, 3.05 * inch, 0.75 * inch, 2.15 * inch],
        )
        cover_tbl.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.9, theme.table_grid),
                    ("BACKGROUND", (0, 4), (3, 4), theme.table_header_bg),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.7, theme.table_grid),
                    ("LINEBELOW", (0, 1), (-1, 1), 0.7, theme.table_grid),
                    ("LINEBELOW", (0, 2), (-1, 2), 0.7, theme.table_grid),
                    ("LINEBELOW", (0, 3), (-1, 3), 0.7, theme.table_grid),
                    ("LINEBELOW", (0, 4), (-1, 4), 0.7, theme.table_grid),
                    ("LINEBELOW", (0, 5), (-1, 5), 0.7, theme.table_grid),
                    ("LINEBELOW", (0, 6), (-1, 6), 0.7, theme.table_grid),
                    ("LINEBELOW", (0, 7), (-1, 7), 0.7, theme.table_grid),
                    # spans para filas de una sola columna visual
                    ("SPAN", (2, 2), (3, 2)),
                    ("SPAN", (0, 3), (3, 3)),
                    ("SPAN", (0, 4), (3, 4)),
                    ("SPAN", (0, 5), (3, 5)),
                    ("SPAN", (0, 6), (3, 6)),
                    ("SPAN", (0, 7), (3, 7)),
                    ("SPAN", (0, 8), (3, 8)),
                    ("FONTNAME", (0, 0), (0, 2), theme.font_bold),
                    ("FONTNAME", (2, 0), (2, 2), theme.font_bold),
                    ("FONTNAME", (1, 0), (1, 2), theme.font_regular),
                    ("FONTNAME", (3, 0), (3, 2), theme.font_regular),
                    ("FONTSIZE", (0, 0), (-1, -1), 11),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    # líneas para “llenar” campos del encabezado
                    ("LINEBELOW", (1, 0), (1, 0), 0.7, theme.table_grid),
                    ("LINEBELOW", (3, 0), (3, 0), 0.7, theme.table_grid),
                    ("LINEBELOW", (1, 1), (1, 1), 0.7, theme.table_grid),
                    ("LINEBELOW", (3, 1), (3, 1), 0.7, theme.table_grid),
                    ("LINEBELOW", (1, 2), (1, 2), 0.7, theme.table_grid),
                ]
            )
        )
        story.append(cover_tbl)

        # Tablas lado a lado: Ejes (izq) y Campos (der)
        def checklist_table(title: str, items: list[dict]) -> Table:
            rows = [[Paragraph(f"<b>{_xml_escape(title)}</b>", styles["normal"]), ""]]
            for item in items:
                if not isinstance(item, dict):
                    continue
                nombre = _safe_text(item.get("nombre"))
                if not nombre:
                    continue
                rows.append([Paragraph(_xml_escape(nombre), styles["normal"]), "X" if item.get("seleccionado") else ""])
            tbl = Table(rows, colWidths=[3.10 * inch, 0.45 * inch])
            tbl.setStyle(
                TableStyle(
                    [
                        ("SPAN", (0, 0), (1, 0)),
                        ("BACKGROUND", (0, 0), (1, 0), theme.table_header_bg),
                        ("BOX", (0, 0), (-1, -1), 0.7, theme.table_grid),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.7, theme.table_grid),
                        ("LINEBEFORE", (1, 1), (1, -1), 0.7, theme.table_grid),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (1, 1), (1, -1), "CENTER"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            return tbl

        ejes_tbl = checklist_table("Ejes articuladores", ejes if isinstance(ejes, list) else [])
        campos_tbl = checklist_table("Campos Formativos", campos if isinstance(campos, list) else [])

        story.append(Spacer(1, 0.12 * inch))
        side = Table([[ejes_tbl, campos_tbl]], colWidths=[3.55 * inch, 3.55 * inch])
        side.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (0, 0), 6),
                    ("LEFTPADDING", (1, 0), (1, 0), 6),
                ]
            )
        )
        story.append(side)


class SectionBlock(PdfBlock):
    def __init__(self, block_id: str, title: str):
        super().__init__(block_id, title)

    def _header(self, story: list, styles: dict) -> None:
        story.append(Paragraph(_xml_escape(_safe_text(self.title)), styles["h1"]))


class ProyectoBlock(SectionBlock):
    def __init__(self):
        super().__init__("proyecto", "Proyecto educativo")

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        self._header(story, styles)
        proyecto = (master_json.get("planeacion") or {}).get("proyecto") or {}

        rows = [
            ("Nombre", proyecto.get("nombre_proyecto")),
            ("Problemática", proyecto.get("problematica")),
            ("Justificación", proyecto.get("justificacion")),
            ("Propósito", proyecto.get("proposito")),
            ("Producto final", proyecto.get("producto_final")),
            ("Temporalidad", proyecto.get("temporalidad")),
        ]

        for label, value in rows:
            if not _safe_text(value):
                continue
            if label == "Temporalidad":
                story.append(Paragraph(f"<b>{_xml_escape(label)}:</b> {_maybe_json_to_bullets(value)}", styles["normal"]))
            else:
                story.append(Paragraph(f"<b>{_xml_escape(label)}:</b> {_xml_escape(_safe_text(value))}", styles["normal"]))
            story.append(Spacer(1, 0.06 * inch))


class SecuenciaBlock(SectionBlock):
    def __init__(self):
        super().__init__("secuencia", "Secuencia didáctica (NEM)")

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        self._header(story, styles)
        sec = (master_json.get("planeacion") or {}).get("secuencia_didactica") or {}

        def add_sub(title: str, text: Any) -> None:
            body = _safe_text(text)
            if not body:
                return
            story.append(Paragraph(_xml_escape(title), styles["h2"]))
            story.append(Paragraph(_xml_escape(body).replace("\n", "<br/>"), styles["normal"]))

        add_sub("Inicio", sec.get("inicio"))
        add_sub("Desarrollo", sec.get("desarrollo"))
        add_sub("Cierre", sec.get("cierre"))
        add_sub("Evaluación (momento)", sec.get("evaluacion"))

        evidencias = _safe_list(sec.get("evidencias"))
        materiales = _safe_list(sec.get("materiales"))
        if evidencias:
            story.append(Paragraph("Evidencias", styles["h2"]))
            story.append(Paragraph(_bullets(evidencias), styles["normal"]))
        if materiales:
            story.append(Paragraph("Materiales", styles["h2"]))
            story.append(Paragraph(_bullets(materiales), styles["normal"]))


class ActividadesBlock(SectionBlock):
    def __init__(self):
        super().__init__("actividades", "Actividades por día")

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        self._header(story, styles)
        actividades = (master_json.get("planeacion") or {}).get("actividades") or []
        if not actividades:
            story.append(Paragraph("No hay actividades generadas.", styles["muted"]))
            return

        for item in actividades:
            if not isinstance(item, dict):
                continue
            dia = _safe_text(item.get("dia"))
            momento = _safe_text(item.get("momento"))
            actividad = item.get("actividad") or {}

            story.append(Paragraph(_xml_escape(f"Día {dia} — {momento}"), styles["h2"]))
            story.append(Paragraph(f"<b>Actividad:</b> {_xml_escape(_safe_text(actividad.get('actividad')))}", styles["normal"]))

            pasos = _safe_list(actividad.get("pasos"))
            if pasos:
                story.append(Paragraph("<b>Pasos:</b>", styles["normal"]))
                story.append(Paragraph(_bullets(pasos), styles["normal"]))

            materiales = _safe_list(actividad.get("materiales"))
            if materiales:
                mats = ", ".join([_safe_text(m) for m in materiales if _safe_text(m)])
                story.append(Paragraph(f"<b>Materiales:</b> {_xml_escape(mats)}", styles["small"]))

            story.append(Spacer(1, 0.1 * inch))


class EvaluacionBlock(SectionBlock):
    def __init__(self):
        super().__init__("evaluacion", "Evaluación (rúbrica analítica)")

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        self._header(story, styles)
        evaluacion = (master_json.get("planeacion") or {}).get("evaluacion") or {}
        criterios = evaluacion.get("criterios") or []

        if not criterios:
            story.append(Paragraph("No hay evaluación generada.", styles["muted"]))
            return

        indicadores = evaluacion.get("indicadores") or []
        if indicadores:
            story.append(Paragraph("Indicadores generales", styles["h2"]))
            story.append(Paragraph(_bullets(indicadores), styles["normal"]))
            story.append(Spacer(1, 0.06 * inch))

        levels = ["Insuficiente", "Básico", "Satisfactorio", "Destacado"]

        for idx, c in enumerate(criterios, start=1):
            if not isinstance(c, dict):
                continue
            criterio = _safe_text(c.get("criterio"))
            if not criterio:
                continue

            story.append(Paragraph(f"Criterio {idx}: {_xml_escape(criterio)}", styles["h2"]))

            evidencia = _safe_text(c.get("evidencia"))
            if evidencia:
                story.append(Paragraph(f"<b>Evidencia:</b> {_xml_escape(evidencia)}", styles["normal"]))

            inds = c.get("indicadores") or []
            if inds:
                story.append(Paragraph("<b>Indicadores observables:</b>", styles["normal"]))
                story.append(Paragraph(_bullets(inds), styles["normal"]))

            niveles = c.get("niveles") or {}
            rubric_rows = [["Nivel", "Descriptor"]]
            for lvl in levels:
                rubric_rows.append([lvl, _safe_text(niveles.get(lvl))])

            tbl = Table(rubric_rows, colWidths=[1.35 * inch, 5.9 * inch])
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), theme.table_header_bg),
                        ("FONTNAME", (0, 0), (-1, 0), theme.font_bold),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.5, theme.table_grid),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, theme.table_zebra]),
                    ]
                )
            )
            story.append(Spacer(1, 0.08 * inch))
            story.append(tbl)
            story.append(Spacer(1, 0.12 * inch))


class RawMasterBlock(SectionBlock):
    def __init__(self):
        super().__init__("raw_master", "Anexo: JSON maestro (recortado)")

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        self._header(story, styles)
        raw = json.dumps(master_json, ensure_ascii=False, indent=2)
        story.append(Paragraph(_xml_escape(_safe_text(raw)).replace("\n", "<br/>"), styles["code"]))


class FirmasBlock(SectionBlock):
    def __init__(self):
        super().__init__("firmas", "FIRMAS")

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        story.append(PageBreak())
        planeacion = master_json.get("planeacion") or {}
        datos = planeacion.get("datos_generales") or {}

        from reportlab.lib.styles import ParagraphStyle  # import local para mantener módulo compacto

        center = ParagraphStyle("LumiCenter", parent=styles["normal"], alignment=1)

        firmas = [
            ("Docente", _safe_text(datos.get("docente"))),
            ("Subdirectora Académica", _safe_text(datos.get("subdirectora_academica"))),
            ("Directora Vo.Bo", _safe_text(datos.get("directora_vobo"))),
        ]

        story.append(Spacer(1, 0.35 * inch))
        for idx, (cargo, nombre) in enumerate(firmas):
            if idx > 0:
                story.append(Spacer(1, 0.35 * inch))
            story.append(Paragraph(_xml_escape(cargo), styles["normal"]))
            story.append(Spacer(1, 0.22 * inch))
            story.append(Paragraph("_______________________________", center))
            if nombre:
                story.append(Paragraph(_xml_escape(nombre), center))

class ContenidosPdaBlock(SectionBlock):
    def __init__(self):
        super().__init__("contenidos_pda", "CONTENIDOS Y PDA")

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        story.append(PageBreak())
        # Hoja 2: tabla con 3 columnas (Campos formativos / Contenidos / PDA).

        planeacion = master_json.get("planeacion") or {}
        contenidos = planeacion.get("contenidos_pda") or {}
        grado = _safe_text(contenidos.get("grado") or (planeacion.get("datos_generales") or {}).get("grado"))
        campos = contenidos.get("campos") or []
        if not isinstance(campos, list) or not campos:
            story.append(Paragraph("No hay contenidos/PDA generados.", styles["muted"]))
            return

        fixed_order = [
            "LENGUAJES",
            "SABERES Y PENSAMIENTO CIENTÍFICO",
            "ÉTICA, NATURALEZA Y SOCIEDADES",
            "DE LO HUMANO Y LO COMUNITARIO",
        ]

        def norm(s: str) -> str:
            return normalize_text(s)

        # index por campo
        by_field: dict[str, dict] = {}
        for item in campos:
            if not isinstance(item, dict):
                continue
            campo = _safe_text(item.get("campo_formativo"))
            if campo:
                by_field[norm(campo)] = item

        def pda_for(item: dict) -> str:
            pda = _safe_text(item.get("pda"))
            if pda:
                return pda
            procesos = item.get("procesos")
            if not isinstance(procesos, dict) or not procesos:
                return ""
            # intenta clave de grado
            g = _safe_text(grado)
            g_digits = "".join([c for c in g if c.isdigit()])
            if g_digits:
                for key in (f"{g_digits}°", f"{g_digits}º", f"{g_digits}Â°"):
                    for k, v in procesos.items():
                        if key in str(k):
                            return _safe_text(v)
            return _safe_text(procesos.get("actual") or procesos.get("Actual") or next(iter(procesos.values())))

        # tabla principal
        rows: list[list[Any]] = []
        rows.append([Paragraph("<b>CONTENIDOS Y PDA</b>", styles["normal"]), "", ""])
        rows.append([Paragraph(f"<b>{_xml_escape(_grado_a_ordinal(grado))}</b>" if grado else "", styles["normal"]), "", ""])
        rows.append(
            [
                Paragraph("<b>Campos Formativos</b>", styles["normal"]),
                Paragraph("<b>Contenidos</b>", styles["normal"]),
                Paragraph("<b>Procesos de desarrollo de aprendizaje (PDA)</b>", styles["normal"]),
            ]
        )

        display_to_key = {
            "LENGUAJES": "Lenguajes",
            "SABERES Y PENSAMIENTO CIENTÍFICO": "Saberes y pensamiento científico",
            "ÉTICA, NATURALEZA Y SOCIEDADES": "Ética, naturaleza y sociedades",
            "DE LO HUMANO Y LO COMUNITARIO": "De lo humano y lo comunitario",
        }

        for display in fixed_order:
            key = display_to_key.get(display, display)
            item = by_field.get(norm(key)) or {}
            contenido_txt = _safe_text(item.get("contenido"))
            pda_txt = pda_for(item) if isinstance(item, dict) else ""
            rows.append(
                [
                    Paragraph(f"<b>{_xml_escape(display)}</b>", styles["normal"]),
                    Paragraph(_xml_escape(contenido_txt), styles["normal"]),
                    Paragraph(_xml_escape(pda_txt), styles["normal"]),
                ]
            )

        tbl = Table(rows, colWidths=[2.2 * inch, 3.05 * inch, 2.0 * inch])
        tbl.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.9, theme.table_grid),
                    ("GRID", (0, 2), (-1, -1), 0.7, theme.table_grid),
                    ("SPAN", (0, 0), (-1, 0)),
                    ("SPAN", (0, 1), (-1, 1)),
                    ("BACKGROUND", (0, 0), (-1, 0), theme.table_header_bg),
                    ("BACKGROUND", (0, 2), (-1, 2), theme.table_header_bg),
                    ("ALIGN", (0, 0), (-1, 1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(tbl)


class SesionesBlock(SectionBlock):
    def __init__(self):
        super().__init__("sesiones", "PLANEACIÓN POR SESIÓN")

    def render(self, story: list, master_json: dict, styles: dict, theme: PdfTheme) -> None:
        story.append(PageBreak())
        # En el PDF de ejemplo la sección arranca directo con la tabla de sesión (sin título extra).

        planeacion = master_json.get("planeacion") or {}
        sesiones = planeacion.get("sesiones") or []
        if not isinstance(sesiones, list) or not sesiones:
            story.append(Paragraph("No hay sesiones generadas.", styles["muted"]))
            return

        for idx, s in enumerate(sesiones, start=1):
            if not isinstance(s, dict):
                continue
            if idx > 1:
                story.append(Spacer(1, 0.18 * inch))

            etapa = _safe_text(s.get("etapa"))
            sesion = _safe_text(s.get("sesion") or idx)
            fecha = _safe_text(s.get("fecha"))

            header = Table(
                [
                    ["ETAPA", etapa, "SESIÓN", str(sesion), "FECHA:", fecha or ""],
                ],
                colWidths=[0.75 * inch, 3.2 * inch, 0.75 * inch, 0.7 * inch, 0.75 * inch, 1.1 * inch],
            )
            header.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.7, theme.table_grid),
                        ("FONTNAME", (0, 0), (-1, -1), theme.font_bold),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("FONTSIZE", (0, 0), (-1, -1), 11),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )

            inicio = _safe_text(s.get("inicio"))
            desarrollo = _safe_text(s.get("desarrollo"))
            cierre = _safe_text(s.get("cierre"))

            def section_row(title: str, body: str) -> list:
                return [
                    Paragraph(f"<b>{_xml_escape(title)}</b>", styles["normal"]),
                    Paragraph(_body_markup(body), styles["normal"]),
                ]

            main_rows = []
            main_rows.append(section_row("INICIO", inicio))
            main_rows.append(section_row("DESARROLLO", desarrollo))
            main_rows.append(section_row("CIERRE", cierre))
            main_tbl = Table(main_rows, colWidths=[1.25 * inch, 6.0 * inch])
            main_tbl.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.7, theme.table_grid),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("FONTNAME", (0, 0), (0, -1), theme.font_bold),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )

            pausa = _safe_text(s.get("pausa_activa"))
            recursos = _safe_list(s.get("recursos"))
            indicadores = _safe_list(s.get("indicadores"))

            bottom_tbl = Table(
                [
                    [
                        Paragraph(f"<b>PAUSA ACTIVA:</b><br/>{_xml_escape(pausa)}", styles["small"]),
                        Paragraph(f"<b>Recursos:</b><br/>{_bullets(recursos) or ''}", styles["small"]),
                    ]
                ],
                colWidths=[3.6 * inch, 3.65 * inch],
            )
            bottom_tbl.setStyle(
                TableStyle(
                    [
                        ("GRID", (0, 0), (-1, -1), 0.7, theme.table_grid),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            # Mantiene el "cuerpo" (encabezado + inicio/desarrollo/cierre + pausa/recursos) junto,
            # pero deja INDICADORES libre para que se desborde como en el ejemplo.
            story.append(KeepTogether([header, Spacer(1, 0.12 * inch), main_tbl, Spacer(1, 0.12 * inch), bottom_tbl]))

            if indicadores:
                story.append(Spacer(1, 0.10 * inch))
                story.append(Paragraph("<b>INDICADORES</b>", styles["normal"]))
                story.append(Paragraph(_bullets(indicadores), styles["normal"]))


def _on_page(canvas, doc, *, theme: PdfTheme, options: PdfRenderOptions) -> None:
    if not (options.footer_text or options.include_page_numbers):
        return
    canvas.saveState()
    canvas.setFont(theme.font_regular, 8)
    canvas.setFillColor(theme.muted)
    if options.footer_text:
        canvas.drawString(0.6 * inch, 0.45 * inch, options.footer_text[:120])
    if options.include_page_numbers:
        canvas.drawRightString(doc.pagesize[0] - 0.6 * inch, 0.45 * inch, f"Página {doc.page}")
    canvas.restoreState()


def render_planeacion_pdf(
    master_json: Dict[str, Any],
    output_path: str,
    *,
    options: Optional[PdfRenderOptions] = None,
    theme: Optional[PdfTheme] = None,
    styles_factory: StylesFactory = default_styles,
    blocks: Optional[List[PdfBlock]] = None,
) -> str:
    """
    Renderiza el JSON maestro (salida del coordinador) a PDF.
    """
    options = options or PdfRenderOptions()
    theme = _ensure_theme_fonts(theme or PdfTheme())
    styles = styles_factory(theme)

    if blocks is None:
        blocks = [
            CoverBlock(),
            ContenidosPdaBlock(),
            SesionesBlock(),
        ]
        if options.include_evaluacion:
            blocks.append(EvaluacionBlock())
        if options.include_firmas:
            blocks.append(FirmasBlock())
        if options.include_raw_master_json:
            blocks.append(RawMasterBlock())

    doc = BaseDocTemplate(
        output_path,
        pagesize=options.pagesize,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=options.title,
        author="Lumi",
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    template = PageTemplate(id="main", frames=[frame], onPage=lambda c, d: _on_page(c, d, theme=theme, options=options))
    doc.addPageTemplates([template])

    story: List[Any] = []
    for b in blocks:
        b.render(story, master_json, styles, theme)
        if story and not isinstance(story[-1], PageBreak):
            story.append(Spacer(1, 0.12 * inch))

    doc.build(story)
    return output_path
