"""
Theme system for Lumi PDF rendering.

Design goals:
- Deterministic (repeatable output)
- No network / no external assets required
- Modular: new themes can be added without changing the renderer logic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from reportlab.lib import colors

from design.illustrations import pick_cover_illustration, pick_icon


@dataclass(frozen=True)
class ThemeTokens:
    primary: colors.Color
    secondary: colors.Color
    text: colors.Color
    muted: colors.Color
    table_header_bg: colors.Color
    table_grid: colors.Color


@dataclass(frozen=True)
class DesignTheme:
    id: str
    name: str
    tokens: ThemeTokens
    mode: str  # "screen" | "print"

    def cover_drawing(self, width: int = 520, height: int = 90, *, seed: int | None = None):
        fn = pick_cover_illustration(self.id)
        return fn(width, height, primary=self.tokens.primary, secondary=self.tokens.secondary, seed=seed)

    def icon_drawing(self, block_id: str, size: int = 18):
        fn = pick_icon(self.id, block_id)
        return fn(size, primary=self.tokens.primary, secondary=self.tokens.secondary)


def _printify(tokens: ThemeTokens) -> ThemeTokens:
    # Print mode: reduce heavy colors, keep readable contrast.
    return ThemeTokens(
        primary=colors.HexColor("#1f2937"),
        secondary=colors.HexColor("#374151"),
        text=colors.black,
        muted=colors.HexColor("#4b5563"),
        table_header_bg=colors.HexColor("#f3f4f6"),
        table_grid=colors.HexColor("#d1d5db"),
    )


THEMES: Dict[str, Dict[str, Any]] = {
    "default": {
        "name": "Clásico",
        "primary": "#1f4e79",
        "secondary": "#2f855a",
    },
    "primavera": {
        "name": "Primavera",
        "primary": "#2f855a",
        "secondary": "#8bc34a",
    },
    "lenguajes": {
        "name": "Lenguajes",
        "primary": "#6b46c1",
        "secondary": "#2b6cb0",
    },
    "matematicas": {
        "name": "Matemáticas",
        "primary": "#2b6cb0",
        "secondary": "#ed8936",
    },
}


def get_design_theme(theme_id: str | None = None, *, mode: str = "screen") -> DesignTheme:
    theme_id = (theme_id or "default").strip().lower()
    raw = THEMES.get(theme_id) or THEMES["default"]

    tokens = ThemeTokens(
        primary=colors.HexColor(raw["primary"]),
        secondary=colors.HexColor(raw["secondary"]),
        text=colors.black,
        muted=colors.HexColor("#4a5568"),
        table_header_bg=colors.HexColor("#e6eef7"),
        table_grid=colors.HexColor("#cbd5e0"),
    )

    if mode == "print":
        tokens = _printify(tokens)

    return DesignTheme(id=theme_id if theme_id in THEMES else "default", name=raw["name"], tokens=tokens, mode=mode)


def pick_theme_id(planeacion_input: Dict[str, Any], master_json: Optional[Dict[str, Any]] = None) -> str:
    """
    Selector determinístico del tema.
    - Si el usuario define `theme_id`, se respeta.
    - Si no, se infiere por palabras clave (tema/campo formativo).
    """
    theme_id = str(planeacion_input.get("theme_id") or "").strip().lower()
    if theme_id:
        return theme_id

    tema = str(planeacion_input.get("tema") or "").lower()
    if master_json:
        try:
            tema = str((master_json.get("planeacion") or {}).get("datos_generales", {}).get("tema") or tema).lower()
        except Exception:
            pass

    if any(k in tema for k in ("primavera", "flores", "plantas", "naturaleza", "seres vivos")):
        return "primavera"
    if any(k in tema for k in ("lectura", "escritura", "cuento", "narración", "lenguaje", "lenguajes")):
        return "lenguajes"
    if any(k in tema for k in ("números", "numeros", "suma", "resta", "multiplicación", "division", "matem")):
        return "matematicas"

    return "default"
