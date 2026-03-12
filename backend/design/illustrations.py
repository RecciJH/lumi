"""
Deterministic illustrations/icons for PDF themes (no network, no copyright risk).

All drawings are vector-based (ReportLab graphics), so they embed cleanly in PDF.
"""

from __future__ import annotations

import random
from typing import Optional

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String
from reportlab.lib import colors


def _clamp(n: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, n))


def _tint(color: colors.Color, factor: float) -> colors.Color:
    factor = _clamp(factor, 0.0, 1.0)
    return colors.Color(
        red=_clamp(color.red + (1 - color.red) * factor, 0, 1),
        green=_clamp(color.green + (1 - color.green) * factor, 0, 1),
        blue=_clamp(color.blue + (1 - color.blue) * factor, 0, 1),
    )


def cover_default(
    width: int = 520,
    height: int = 90,
    *,
    primary: colors.Color,
    secondary: colors.Color,
    seed: Optional[int] = None,
) -> Drawing:
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=_tint(primary, 0.88), strokeColor=None))
    d.add(Rect(0, 0, width, int(height * 0.33), fillColor=_tint(secondary, 0.90), strokeColor=None))
    # Decorative dots
    rng = random.Random(seed if seed is not None else 1234)
    for i in range(10):
        x = 30 + i * (width - 60) / 9
        jitter = rng.uniform(-2.5, 2.5)
        d.add(Circle(x, height * 0.55 + jitter, 6, fillColor=_tint(primary, 0.65), strokeColor=None))
    return d


def _bee(x: float, y: float, *, size: float, primary: colors.Color) -> list:
    # Tiny bee: body + stripes + wings
    body = Circle(x, y, size, fillColor=colors.HexColor("#f6bd60"), strokeColor=None)
    stripe1 = Rect(x - size * 0.7, y - size * 0.2, size * 1.4, size * 0.25, fillColor=_tint(primary, 0.2), strokeColor=None)
    stripe2 = Rect(x - size * 0.6, y + size * 0.15, size * 1.2, size * 0.22, fillColor=_tint(primary, 0.2), strokeColor=None)
    wing1 = Circle(x - size * 0.6, y + size * 0.9, size * 0.65, fillColor=_tint(colors.white, 0.0), strokeColor=_tint(primary, 0.8))
    wing2 = Circle(x + size * 0.6, y + size * 0.9, size * 0.65, fillColor=_tint(colors.white, 0.0), strokeColor=_tint(primary, 0.8))
    return [wing1, wing2, body, stripe1, stripe2]


def _flower(cx: float, cy: float, *, petal_r: float, primary: colors.Color, stem: colors.Color) -> list:
    petal = _tint(primary, 0.78)
    parts = []
    for dx, dy in ((0, 1.6), (1.3, 0.8), (1.3, -0.8), (0, -1.6), (-1.3, -0.8), (-1.3, 0.8)):
        parts.append(Circle(cx + dx * petal_r, cy + dy * petal_r, petal_r, fillColor=petal, strokeColor=None))
    parts.append(Circle(cx, cy, petal_r * 0.9, fillColor=colors.HexColor("#ffd166"), strokeColor=None))
    parts.append(Rect(cx - 1, 0, 2, max(0, cy - petal_r * 1.8), fillColor=stem, strokeColor=None))
    return parts


def cover_primavera(
    width: int = 520,
    height: int = 90,
    *,
    primary: colors.Color,
    secondary: colors.Color,
    seed: Optional[int] = None,
) -> Drawing:
    d = Drawing(width, height)
    sky = _tint(colors.HexColor("#87ceeb"), 0.15)
    grass = _tint(colors.HexColor("#7ac74f"), 0.20)

    d.add(Rect(0, int(height * 0.35), width, int(height * 0.65), fillColor=sky, strokeColor=None))
    d.add(Rect(0, 0, width, int(height * 0.35), fillColor=grass, strokeColor=None))

    # Sun
    d.add(Circle(width - 40, height - 25, 14, fillColor=colors.HexColor("#ffd166"), strokeColor=None))
    d.add(Line(width - 40, height - 25, width - 18, height - 25, strokeColor=colors.HexColor("#ffd166"), strokeWidth=1))
    d.add(Line(width - 40, height - 25, width - 30, height - 7, strokeColor=colors.HexColor("#ffd166"), strokeWidth=1))

    rng = random.Random(seed if seed is not None else 2026)

    # Variant motifs (bees/flowers/butterflies) — changes per seed
    motif = rng.choice(["bees", "flowers", "butterflies", "mix"])

    # Flowers on grass
    flower_count = 1 if motif == "bees" else 3 if motif == "flowers" else 2 if motif == "butterflies" else 3
    for _ in range(flower_count):
        cx = rng.uniform(35, 130)
        cy = rng.uniform(height * 0.18, height * 0.33)
        petal_r = rng.uniform(4.5, 6.5)
        for shp in _flower(cx, cy, petal_r=petal_r, primary=primary, stem=secondary):
            d.add(shp)

    # Bees in the sky
    if motif in ("bees", "mix"):
        for _ in range(rng.randint(1, 2)):
            x = rng.uniform(150, 240)
            y = rng.uniform(height * 0.55, height * 0.78)
            for shp in _bee(x, y, size=rng.uniform(4.2, 5.2), primary=primary):
                d.add(shp)

    # Butterflies (tiny V shapes)
    if motif in ("butterflies", "mix"):
        for _ in range(rng.randint(2, 4)):
            x = rng.uniform(110, 210)
            y = rng.uniform(height * 0.58, height * 0.85)
            w = rng.uniform(4, 7)
            col = _tint(primary, rng.uniform(0.45, 0.7))
            d.add(Line(x, y, x + w, y - w, strokeColor=col, strokeWidth=1))
            d.add(Line(x + w, y - w, x + 2 * w, y, strokeColor=col, strokeWidth=1))

    # Title chip
    d.add(Rect(width - 210, 8, 200, 22, fillColor=_tint(primary, 0.90), strokeColor=None))
    d.add(String(width - 200, 13, "Tema: Primavera", fontName="Helvetica-Bold", fontSize=10, fillColor=primary))
    return d


def icon_leaf(size: int = 18, *, primary: colors.Color, secondary: colors.Color) -> Drawing:
    d = Drawing(size, size)
    d.add(Circle(size * 0.52, size * 0.52, size * 0.46, fillColor=_tint(secondary, 0.85), strokeColor=None))
    leaf = Polygon(
        [
            size * 0.25,
            size * 0.55,
            size * 0.50,
            size * 0.85,
            size * 0.78,
            size * 0.58,
            size * 0.50,
            size * 0.20,
        ],
        fillColor=_tint(primary, 0.75),
        strokeColor=None,
    )
    d.add(leaf)
    d.add(Line(size * 0.50, size * 0.20, size * 0.52, size * 0.84, strokeColor=_tint(primary, 0.35), strokeWidth=1))
    return d


def icon_book(size: int = 18, *, primary: colors.Color, secondary: colors.Color) -> Drawing:
    d = Drawing(size, size)
    d.add(Rect(1, 2, size - 2, size - 4, fillColor=_tint(primary, 0.90), strokeColor=None))
    d.add(Line(size * 0.5, 3, size * 0.5, size - 3, strokeColor=_tint(primary, 0.45), strokeWidth=1))
    d.add(Rect(3, 4, size * 0.44, size - 8, fillColor=colors.white, strokeColor=None))
    d.add(Rect(size * 0.53, 4, size * 0.44, size - 8, fillColor=colors.white, strokeColor=None))
    d.add(Line(4, size - 6, size - 4, size - 6, strokeColor=_tint(secondary, 0.6), strokeWidth=1))
    return d


def icon_calculator(size: int = 18, *, primary: colors.Color, secondary: colors.Color) -> Drawing:
    d = Drawing(size, size)
    d.add(Rect(1, 1, size - 2, size - 2, fillColor=_tint(primary, 0.92), strokeColor=None))
    d.add(Rect(3, size - 7, size - 6, 4, fillColor=colors.white, strokeColor=None))
    # Buttons
    x0, y0 = 3, 3
    btn = 3.2
    gap = 1.2
    for r in range(3):
        for c in range(3):
            d.add(
                Rect(
                    x0 + c * (btn + gap),
                    y0 + r * (btn + gap),
                    btn,
                    btn,
                    fillColor=_tint(secondary, 0.85),
                    strokeColor=None,
                )
            )
    return d


def icon_checklist(size: int = 18, *, primary: colors.Color, secondary: colors.Color) -> Drawing:
    d = Drawing(size, size)
    d.add(Rect(1, 1, size - 2, size - 2, fillColor=_tint(primary, 0.93), strokeColor=None))
    d.add(Line(4, size - 5, size - 4, size - 5, strokeColor=_tint(primary, 0.4), strokeWidth=1))
    d.add(Line(4, size - 9, size - 4, size - 9, strokeColor=_tint(primary, 0.4), strokeWidth=1))
    d.add(Line(4, size - 13, size - 4, size - 13, strokeColor=_tint(primary, 0.4), strokeWidth=1))
    # Check mark
    d.add(Line(4, 6, 7, 3, strokeColor=_tint(secondary, 0.4), strokeWidth=2))
    d.add(Line(7, 3, 13, 9, strokeColor=_tint(secondary, 0.4), strokeWidth=2))
    return d


def pick_cover_illustration(theme_id: str):
    if theme_id == "primavera":
        return cover_primavera
    return cover_default


def pick_icon(theme_id: str, block_id: str):
    # Icons per theme could vary; start simple and deterministic.
    if theme_id == "primavera":
        return icon_leaf

    # Generic mapping by section
    if block_id in ("proyecto",):
        return icon_book
    if block_id in ("secuencia", "actividades"):
        return icon_checklist
    if block_id in ("evaluacion",):
        return icon_calculator
    return icon_leaf
