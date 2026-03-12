"""
Script CLI para generar una planeación en PDF sin Swagger/UI.

Ejemplo:
  python backend/scripts/generar_planeacion_pdf.py --input input.json --out planeacion.pdf

El input es un dict libre; lo mínimo recomendado:
  tema, grado, duracion_dias, metodologia, docente, escuela, grupo, pda
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict


def _ensure_backend_on_syspath() -> None:
    backend_dir = Path(__file__).resolve().parents[1]
    backend_str = str(backend_dir)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)


def _load_json(path: str) -> Dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("El archivo de input debe contener un objeto JSON (dict).")
    return data


def _write_json(path: str, data: Dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    _ensure_backend_on_syspath()

    from agents.coordinador_agent import generar_planeacion_maestra  # noqa: WPS433
    from design.theme_system import get_design_theme, pick_theme_id  # noqa: WPS433
    from renderers.pdf_renderer import PdfRenderOptions, render_planeacion_pdf  # noqa: WPS433

    parser = argparse.ArgumentParser(description="Generar planeación (Lumi) en PDF.")
    parser.add_argument("--input", required=True, help="Ruta a JSON con planeacion_input.")
    parser.add_argument("--out", required=True, help="Ruta de salida .pdf")
    parser.add_argument("--out-master", default="", help="Opcional: guardar JSON maestro aquí.")
    parser.add_argument("--log-level", default="INFO", help="DEBUG|INFO|WARNING|ERROR")
    parser.add_argument("--include-raw-json", action="store_true", help="Incluye anexo de JSON maestro (recortado).")
    parser.add_argument("--theme", default="", help="Tema visual (default|primavera|lenguajes|matematicas).")
    parser.add_argument("--mode", default="screen", help="Modo de render: screen|print")
    parser.add_argument("--cover-image", default="", help="Opcional: ruta a imagen local para portada (usa solo imágenes con derechos/licencia).")
    parser.add_argument("--cover-attribution", default="", help="Opcional: texto corto de atribución/licencia para la portada.")
    parser.add_argument("--remote-images", action="store_true", help="Intenta descargar una imagen real (licenciada) para portada.")
    parser.add_argument("--asset-cache-dir", default="", help="Opcional: override del cache de imágenes (default: ~/.lumi/cache/assets).")
    parser.add_argument("--design-seed", default="", help="Semilla para variar el diseño (vacío => cambia en cada ejecución).")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    planeacion_input = _load_json(args.input)
    master = generar_planeacion_maestra(planeacion_input)

    if args.out_master:
        _write_json(args.out_master, master)

    options = PdfRenderOptions(include_raw_master_json=bool(args.include_raw_json))
    theme_id = (args.theme or "").strip().lower() or pick_theme_id(planeacion_input, master)
    design_theme = get_design_theme(theme_id, mode=(args.mode or "screen").strip().lower())

    # Propaga el tema a meta para trazabilidad
    master.setdefault("meta", {})
    master["meta"]["theme_id"] = design_theme.id
    master["meta"]["theme_mode"] = design_theme.mode
    master["meta"]["title"] = master.get("meta", {}).get("title") or "Lumi — Planeación didáctica"
    if args.design_seed != "":
        try:
            master["meta"]["design_seed"] = int(args.design_seed)
        except Exception:
            raise ValueError("--design-seed debe ser entero.")
    else:
        # Variación por ejecución (sin afectar el contenido del JSON).
        master["meta"]["design_seed"] = int(time.time())

    if args.cover_image:
        cover_path = Path(args.cover_image).expanduser().resolve()
        if not cover_path.exists():
            raise ValueError(f"No existe --cover-image: {cover_path}")
        master["meta"].setdefault("assets", {})
        master["meta"]["assets"]["cover"] = {
            "source": "local",
            "path": str(cover_path),
            "attribution": (args.cover_attribution or "").strip(),
        }

    if args.remote_images:
        from pathlib import Path  # noqa: WPS433

        from design.remote_assets import fetch_cover_image, get_default_cache_dir  # noqa: WPS433

        cache_dir = Path(args.asset_cache_dir).expanduser().resolve() if args.asset_cache_dir else get_default_cache_dir()
        try:
            cover = fetch_cover_image(planeacion_input, theme_id=design_theme.id, cache_dir=cache_dir)
            if cover:
                master["meta"].setdefault("assets", {})
                master["meta"]["assets"]["cover"] = cover.to_meta()
            else:
                logging.getLogger(__name__).warning(
                    "No se encontró imagen remota para portada; usando ilustración vectorial."
                )
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "Fallo al descargar imagen remota (se continuará con portada vectorial): %s: %s",
                type(exc).__name__,
                exc,
            )

    render_planeacion_pdf(master, args.out, options=options, design_theme=design_theme)
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
