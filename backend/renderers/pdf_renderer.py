"""
pdf_renderer.py

Renderer "bonito" para la planeación de Lumi usando ReportLab (Platypus).
Diseño escalable:
- El documento se construye por bloques registrables (sections).
- El estilo/tema se define por un DesignTheme (tokens + ilustraciones determinísticas).
- No mezcla lógica de generación (IA) con presentación (PDF).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterable, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image as RLImage,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from xml.sax.saxutils import escape as _xml_escape

from design.theme_system import DesignTheme, get_design_theme, pick_theme_id


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


def _join_lines(items: Iterable[Any]) -> str:
    parts = [_safe_text(x) for x in items]
    parts = [p for p in parts if p]
    return "\n".join(parts)


def _bullets(items: Iterable[Any]) -> str:
    parts = [_safe_text(x) for x in items]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    # Bullet list as simple paragraphs (ReportLab bulletText is limited in nested cases).
    return "<br/>".join([f"• {_xml_escape(p)}" for p in parts])


def _maybe_json_to_bullets(value: Any) -> str:
    """
    Si el valor es un string con JSON (dict/list), lo formatea en bullets.
    Si no, regresa texto normal.
    """
    text = _safe_text(value)
    if not text:
        return ""
    if not (text.startswith("{") or text.startswith("[")):
        return text
    try:
        parsed = json.loads(text)
    except Exception:
        return text
    if isinstance(parsed, dict):
        items = [f"{k}: {_safe_text(v)}" for k, v in parsed.items()]
        return _bullets(items) or text
    if isinstance(parsed, list):
        items = [_safe_text(x) for x in parsed]
        return _bullets(items) or text
    return text


def _design_variant(master_json: Dict[str, Any]) -> int:
    seed = (master_json.get("meta") or {}).get("design_seed")
    try:
        return int(seed) % 3
    except Exception:
        return 0


@dataclass(frozen=True)
class PdfTheme:
    # Deprecated: kept for backward compatibility if someone passes tokens directly.
    primary: colors.Color
    secondary: colors.Color
    text: colors.Color
    muted: colors.Color
    table_header_bg: colors.Color
    table_grid: colors.Color


@dataclass(frozen=True)
class PdfRenderOptions:
    pagesize: tuple = LETTER
    title: str = "Lumi — Planeación didáctica"
    include_raw_master_json: bool = False
    max_raw_json_chars: int = 5000
    footer_text: str = "Generado por Lumi (revisar y ajustar antes de imprimir)."


StylesFactory = Callable[[PdfTheme], Dict[str, ParagraphStyle]]


def default_styles(theme: PdfTheme) -> Dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()

    base = sample["Normal"]
    base.fontName = "Helvetica"
    base.fontSize = 10
    base.leading = 13
    base.textColor = theme.text

    styles: Dict[str, ParagraphStyle] = {
        "title": ParagraphStyle(
            "LumiTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=theme.primary,
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "LumiH1",
            parent=sample["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=theme.primary,
            spaceBefore=12,
            spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "LumiH2",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=theme.secondary,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "normal": ParagraphStyle("LumiNormal", parent=base),
        "muted": ParagraphStyle(
            "LumiMuted",
            parent=base,
            fontSize=9,
            leading=12,
            textColor=theme.muted,
        ),
        "small": ParagraphStyle(
            "LumiSmall",
            parent=base,
            fontSize=8.5,
            leading=11,
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
    return styles


class PdfBlock:
    """
    Bloque renderizable del PDF. Para crecer: agrega un bloque nuevo y regístralo.
    """

    id: str
    title: Optional[str]

    def __init__(self, block_id: str, title: Optional[str] = None):
        self.id = block_id
        self.title = title

    def render(self, story: list, master_json: dict, styles: dict, design: DesignTheme) -> None:  # noqa: D401
        """Añade flowables a `story`."""
        raise NotImplementedError


class CoverBlock(PdfBlock):
    def __init__(self):
        super().__init__("cover", None)

    def render(self, story: list, master_json: dict, styles: dict, design: DesignTheme) -> None:
        planeacion = master_json.get("planeacion") or {}
        datos = planeacion.get("datos_generales") or {}
        curriculum = planeacion.get("curriculum") or {}
        proyecto = planeacion.get("proyecto") or {}

        # Cover illustration:
        # - Prefer remote licensed image if provided in meta.assets.cover
        # - Fallback to deterministic vector illustration
        cover_asset = ((master_json.get("meta") or {}).get("assets") or {}).get("cover") or {}
        cover_path = _safe_text(cover_asset.get("downloaded_path") or cover_asset.get("path"))
        design_seed = (master_json.get("meta") or {}).get("design_seed")
        try:
            design_seed = int(design_seed) if design_seed is not None else None
        except Exception:
            design_seed = None
        if cover_path:
            story.append(RLImage(cover_path, width=7.2 * inch, height=1.25 * inch))
        else:
            story.append(design.cover_drawing(width=520, height=90, seed=design_seed))
        story.append(Spacer(1, 0.12 * inch))

        story.append(
            Paragraph(
                _safe_text(master_json.get("meta", {}).get("title") or "Lumi — Planeación didáctica"),
                styles["title"],
            )
        )

        subtitle = "Nueva Escuela Mexicana (NEM) — Planeación generada automáticamente"
        story.append(Paragraph(subtitle, styles["muted"]))
        story.append(Spacer(1, 0.2 * inch))

        table_data = [
            ["Tema", _safe_text(datos.get("tema") or master_json.get("input", {}).get("tema"))],
            ["Grado / Grupo", f"{_safe_text(datos.get('grado'))} {_safe_text(datos.get('grupo'))}".strip()],
            ["Docente", _safe_text(datos.get("docente"))],
            ["Escuela", _safe_text(datos.get("escuela"))],
            ["Campo formativo", _safe_text(curriculum.get("campo_formativo"))],
            ["Eje", _safe_text(curriculum.get("eje"))],
            ["PDA", _safe_text(curriculum.get("pda"))],
            ["Proyecto", _safe_text(proyecto.get("nombre_proyecto"))],
            ["Producto final", _safe_text(proyecto.get("producto_final"))],
        ]

        tbl = Table(table_data, colWidths=[1.45 * inch, 5.8 * inch])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), design.tokens.table_header_bg),
                    ("TEXTCOLOR", (0, 0), (-1, -1), design.tokens.text),
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("GRID", (0, 0), (-1, -1), 0.5, design.tokens.table_grid),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                ]
            )
        )
        story.append(tbl)
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}", styles["muted"]))
        if cover_path:
            # Minimal attribution line (full attribution can go in a dedicated section later)
            license_txt = _safe_text(cover_asset.get("license"))
            page_url = _safe_text(cover_asset.get("page_url"))
            attr = _safe_text(cover_asset.get("attribution") or cover_asset.get("artist") or cover_asset.get("credit"))
            parts = [p for p in [attr, license_txt, page_url] if p]
            if parts:
                story.append(Spacer(1, 0.08 * inch))
                story.append(Paragraph("Portada: " + _xml_escape(" — ".join(parts))[:350], styles["muted"]))


class SectionBlock(PdfBlock):
    def __init__(self, block_id: str, title: str):
        super().__init__(block_id, title)

    def _header(self, story: list, styles: dict, design: DesignTheme) -> None:
        icon = design.icon_drawing(self.id, size=18)
        title = Paragraph(_xml_escape(_safe_text(self.title)), styles["h1"])
        header = Table([[icon, title]], colWidths=[0.3 * inch, 6.95 * inch])
        header.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        story.append(header)


class ProyectoBlock(SectionBlock):
    def __init__(self):
        super().__init__("proyecto", "Proyecto educativo")

    def render(self, story: list, master_json: dict, styles: dict, design: DesignTheme) -> None:
        self._header(story, styles, design)
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
            story.append(Spacer(1, 0.08 * inch))


class SecuenciaBlock(SectionBlock):
    def __init__(self):
        super().__init__("secuencia", "Secuencia didáctica (NEM)")

    def render(self, story: list, master_json: dict, styles: dict, design: DesignTheme) -> None:
        self._header(story, styles, design)
        sec = (master_json.get("planeacion") or {}).get("secuencia_didactica") or {}

        # Variant: cards vs linear paragraphs
        variant = _design_variant(master_json)

        def _card(title: str, body: str) -> None:
            header = Paragraph(_xml_escape(title), styles["h2"])
            content = Paragraph(_xml_escape(body).replace("\n", "<br/>"), styles["normal"])
            card = Table([[header], [content]], colWidths=[7.25 * inch])
            card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#fbfdff")),
                        ("BOX", (0, 0), (-1, -1), 0.6, design.tokens.table_grid),
                        ("LEFTPADDING", (0, 0), (-1, -1), 10),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(card)
            story.append(Spacer(1, 0.08 * inch))

        def add_sub(title: str, text: Any) -> None:
            body = _safe_text(text)
            if not body:
                return
            if variant == 0:
                story.append(Paragraph(title, styles["h2"]))
                story.append(Paragraph(_xml_escape(body).replace("\n", "<br/>"), styles["normal"]))
                story.append(Spacer(1, 0.06 * inch))
            else:
                _card(title, body)

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

    def render(self, story: list, master_json: dict, styles: dict, design: DesignTheme) -> None:
        self._header(story, styles, design)
        actividades = (master_json.get("planeacion") or {}).get("actividades") or []
        if not actividades:
            story.append(Paragraph("No hay actividades generadas.", styles["muted"]))
            return

        variant = _design_variant(master_json)

        for item in actividades:
            if not isinstance(item, dict):
                continue
            dia = _safe_text(item.get("dia"))
            momento = _safe_text(item.get("momento"))
            actividad = item.get("actividad") or {}

            title = f"Día {dia} — {momento}"
            nombre = _safe_text(actividad.get("actividad"))
            pasos = _safe_list(actividad.get("pasos"))
            materiales = _safe_list(actividad.get("materiales"))

            if variant == 0:
                story.append(Paragraph(_xml_escape(title), styles["h2"]))
                story.append(Paragraph(f"<b>Actividad:</b> {_xml_escape(nombre)}", styles["normal"]))
                if pasos:
                    story.append(Paragraph("<b>Pasos:</b>", styles["normal"]))
                    story.append(Paragraph(_bullets(pasos), styles["normal"]))
                if materiales:
                    story.append(
                        Paragraph(
                            "<b>Materiales:</b> "
                            + _xml_escape(_safe_text(", ".join([_safe_text(m) for m in materiales if _safe_text(m)]))),
                            styles["small"],
                        )
                    )
                story.append(Spacer(1, 0.12 * inch))
            else:
                header = Paragraph(_xml_escape(title), styles["h2"])
                header_tbl = Table([[header]], colWidths=[7.25 * inch])
                header_tbl.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), design.tokens.table_header_bg),
                            ("BOX", (0, 0), (-1, -1), 0.6, design.tokens.table_grid),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )

                body_parts = [
                    Paragraph(f"<b>Actividad:</b> {_xml_escape(nombre)}", styles["normal"]),
                ]
                if pasos:
                    body_parts.append(Paragraph("<b>Pasos:</b>", styles["normal"]))
                    body_parts.append(Paragraph(_bullets(pasos), styles["normal"]))
                if materiales:
                    mats = _xml_escape(_safe_text(", ".join([_safe_text(m) for m in materiales if _safe_text(m)])))
                    body_parts.append(Paragraph(f"<b>Materiales:</b> {mats}", styles["small"]))

                body_tbl = Table([[p] for p in body_parts], colWidths=[7.25 * inch])
                body_tbl.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfdff")),
                            ("BOX", (0, 0), (-1, -1), 0.6, design.tokens.table_grid),
                            ("LEFTPADDING", (0, 0), (-1, -1), 10),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ]
                    )
                )

                story.append(header_tbl)
                story.append(body_tbl)
                story.append(Spacer(1, 0.14 * inch))


class EvaluacionBlock(SectionBlock):
    def __init__(self):
        super().__init__("evaluacion", "Evaluación (rúbrica analítica)")

    def render(self, story: list, master_json: dict, styles: dict, design: DesignTheme) -> None:
        self._header(story, styles, design)
        evaluacion = (master_json.get("planeacion") or {}).get("evaluacion") or {}
        criterios = evaluacion.get("criterios") or []

        if not criterios:
            story.append(Paragraph("No hay evaluación generada.", styles["muted"]))
            return

        indicadores = evaluacion.get("indicadores") or []
        if indicadores:
            story.append(Paragraph("Indicadores generales", styles["h2"]))
            story.append(Paragraph(_bullets(indicadores), styles["normal"]))
            story.append(Spacer(1, 0.08 * inch))

        levels = ["Insuficiente", "Básico", "Satisfactorio", "Destacado"]

        variant = _design_variant(master_json)

        if variant == 2:
            # Rubric matrix (criterio x niveles)
            header = ["Criterio"] + levels
            rows = [header]
            for c in criterios:
                if not isinstance(c, dict):
                    continue
                criterio = _safe_text(c.get("criterio"))
                if not criterio:
                    continue
                niveles = c.get("niveles") or {}
                row = [criterio] + [_safe_text(niveles.get(lvl)) for lvl in levels]
                rows.append(row)

            tbl = Table(
                [[Paragraph(_xml_escape(cell).replace("\n", "<br/>"), styles["small"]) for cell in r] for r in rows],
                colWidths=[1.55 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch],
            )
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), design.tokens.table_header_bg),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.5, design.tokens.table_grid),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            story.append(tbl)
            story.append(Spacer(1, 0.12 * inch))

            # Evidence & indicators per criterio (compact)
            for idx, c in enumerate(criterios, start=1):
                if not isinstance(c, dict):
                    continue
                criterio = _safe_text(c.get("criterio"))
                if not criterio:
                    continue
                evidencia = _safe_text(c.get("evidencia"))
                inds = c.get("indicadores") or []
                line = f"<b>{_xml_escape(criterio)}:</b> "
                if evidencia:
                    line += f"Evidencia: {_xml_escape(evidencia)}. "
                if inds:
                    line += f"Indicadores: {_bullets(inds)}"
                story.append(Paragraph(line, styles["small"]))
        else:
            # Per-criterio blocks (more readable)
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
                            ("BACKGROUND", (0, 0), (-1, 0), design.tokens.table_header_bg),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 9),
                            ("GRID", (0, 0), (-1, -1), 0.5, design.tokens.table_grid),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
                        ]
                    )
                )
                story.append(Spacer(1, 0.08 * inch))
                story.append(tbl)
                story.append(Spacer(1, 0.18 * inch))


class RawMasterBlock(SectionBlock):
    def __init__(self):
        super().__init__("raw_master", "Anexo: JSON maestro (recortado)")

    def render(self, story: list, master_json: dict, styles: dict, design: DesignTheme) -> None:
        self._header(story, styles, design)
        raw = json.dumps(master_json, ensure_ascii=False, indent=2)
        story.append(Paragraph(_xml_escape(_safe_text(raw)).replace("\n", "<br/>"), styles["code"]))


def _on_page(canvas, doc, *, design: DesignTheme, options: PdfRenderOptions) -> None:
    canvas.saveState()
    # Header accent
    canvas.setFillColor(design.tokens.primary)
    canvas.rect(0, doc.pagesize[1] - 10, doc.pagesize[0], 10, stroke=0, fill=1)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(design.tokens.muted)
    footer = options.footer_text
    canvas.drawString(0.7 * inch, 0.5 * inch, footer[:120])
    canvas.drawRightString(doc.pagesize[0] - 0.7 * inch, 0.5 * inch, f"Página {doc.page}")
    canvas.restoreState()


def render_planeacion_pdf(
    master_json: Dict[str, Any],
    output_path: str,
    *,
    options: Optional[PdfRenderOptions] = None,
    design_theme: Optional[DesignTheme] = None,
    theme_id: Optional[str] = None,
    mode: str = "screen",
    styles_factory: StylesFactory = default_styles,
    blocks: Optional[List[PdfBlock]] = None,
) -> str:
    """
    Renderiza el JSON maestro (salida del coordinador) a PDF.

    Args:
        master_json: dict maestro (incluye "planeacion", "results" y "meta")
        output_path: ruta del PDF a escribir
        options: opciones del documento
        theme: colores/tema
        styles_factory: fabrica de estilos (para personalización)
        blocks: lista de bloques; si no se pasa, usa el set por defecto
    """
    if options is None:
        options = PdfRenderOptions()
    if design_theme is None:
        if theme_id is None:
            theme_id = pick_theme_id(master_json.get("input", {}) if isinstance(master_json.get("input"), dict) else {}, master_json)
        design_theme = get_design_theme(theme_id, mode=mode)

    theme_tokens = PdfTheme(
        primary=design_theme.tokens.primary,
        secondary=design_theme.tokens.secondary,
        text=design_theme.tokens.text,
        muted=design_theme.tokens.muted,
        table_header_bg=design_theme.tokens.table_header_bg,
        table_grid=design_theme.tokens.table_grid,
    )
    styles = styles_factory(theme_tokens)

    if blocks is None:
        blocks = [
            CoverBlock(),
            ProyectoBlock(),
            SecuenciaBlock(),
            ActividadesBlock(),
            EvaluacionBlock(),
        ]
        if options.include_raw_master_json:
            blocks.append(RawMasterBlock())

    doc = BaseDocTemplate(
        output_path,
        pagesize=options.pagesize,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=options.title,
        author="Lumi",
    )

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="normal")
    template = PageTemplate(
        id="main",
        frames=[frame],
        onPage=lambda c, d: _on_page(c, d, design=design_theme, options=options),
    )
    doc.addPageTemplates([template])

    story: List[Any] = []
    for b in blocks:
        b.render(story, master_json, styles, design_theme)
        story.append(Spacer(1, 0.12 * inch))

    doc.build(story)
    return output_path
