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
    from renderers.pdf_renderer import PdfRenderOptions, render_planeacion_pdf  # noqa: WPS433

    parser = argparse.ArgumentParser(description="Generar planeación (Lumi) en PDF.")
    parser.add_argument("--input", default="", help="Ruta a JSON con planeacion_input (si no usas --master).")
    parser.add_argument("--master", default="", help="Ruta a JSON maestro ya generado (salida del coordinador).")
    parser.add_argument(
        "--out",
        default=str(Path("outputs") / "planeaciones" / "planeacion.pdf"),
        help="Ruta de salida .pdf (por defecto dentro del proyecto).",
    )
    parser.add_argument("--out-master", default="", help="Opcional: guardar JSON maestro aquí.")
    parser.add_argument("--log-level", default="INFO", help="DEBUG|INFO|WARNING|ERROR")
    parser.add_argument("--include-raw-json", action="store_true", help="Incluye anexo de JSON maestro (recortado).")
    parser.add_argument("--include-evaluacion", action="store_true", help="Incluye evaluación/rúbrica (puede tardar más).")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    if args.master:
        master = _load_json(args.master)
    else:
        if not args.input:
            raise SystemExit("Debes proporcionar --input (planeacion_input) o --master (JSON maestro).")
        planeacion_input = _load_json(args.input)
        if not args.include_evaluacion:
            planeacion_input = dict(planeacion_input)
            planeacion_input["skip_steps"] = list(set(list(planeacion_input.get("skip_steps") or []) + ["evaluation_agent"]))

        master = generar_planeacion_maestra(planeacion_input)

    if args.out_master:
        _write_json(args.out_master, master)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        project_root = Path(__file__).resolve().parents[2]
        if not out_path.resolve().is_relative_to(project_root.resolve()):
            print(f"ADVERTENCIA: El PDF se guardará fuera del proyecto: {out_path.resolve()}", file=sys.stderr)
    except Exception:
        pass

    options = PdfRenderOptions(
        include_raw_master_json=bool(args.include_raw_json),
        include_evaluacion=bool(args.include_evaluacion),
    )
    render_planeacion_pdf(master, str(out_path), options=options)
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
