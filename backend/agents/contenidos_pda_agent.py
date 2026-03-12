from __future__ import annotations

from pathlib import Path

from services.llm_json_service import parse_llm_json_object
from services.llm_service import generar_respuesta
from utils.preescolar.saberes_catalog import (
    load_preescolar_catalogs,
    normalize_text,
    pick_best_contenido,
    pick_best_pda,
)


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_contenidos_pda(data: dict) -> dict:
    campos = data.get("campos")
    if not isinstance(campos, list) or not campos:
        raise ValueError("contenidos_pda no incluye 'campos' como lista no vacía.")

    out_campos = []
    for item in campos:
        if not isinstance(item, dict):
            continue
        campo = _to_text(item.get("campo_formativo"))
        contenido = _to_text(item.get("contenido"))
        procesos = item.get("procesos") or {}
        if not isinstance(procesos, dict):
            procesos = {}
        procesos_norm = {str(k).strip(): _to_text(v) for k, v in procesos.items()}
        if not campo or not contenido:
            continue
        out_campos.append(
            {
                "campo_formativo": campo,
                "contenido": contenido,
                "procesos": procesos_norm,
            }
        )

    if not out_campos:
        raise ValueError("contenidos_pda no devolvió campos válidos.")

    return {
        "grado": _to_text(data.get("grado")) or "",
        "campos": out_campos,
    }


def generar_contenidos_pda(
    *,
    tema: str,
    grado: str,
    campos_formativos: list[str],
) -> dict:
    """
    Genera una sección tipo 'CONTENIDOS Y PDA' en formato similar al de planeaciones SEP/NEM.
    Devuelve SOLO JSON:
    {
      "grado": "3",
      "campos": [
        {
          "campo_formativo": "...",
          "contenido": "...",
          "procesos": {"2°": "...", "3°": "...", "4°": "..."}
        }
      ]
    }
    """
    # 1) Intento local (sin LLM) usando archivos en backend/utils/preescolar/*.txt
    base_dir = Path(__file__).resolve().parents[1] / "utils" / "preescolar"
    catalogs = load_preescolar_catalogs(base_dir) if base_dir.exists() else {}

    if catalogs:
        context = f"{tema}\nGrado: {grado}\nCampos: {', '.join(campos_formativos or [])}"
        out_campos = []
        for campo in campos_formativos:
            campo_txt = _to_text(campo)
            if not campo_txt:
                continue
            cat = catalogs.get(normalize_text(campo_txt))
            if not cat:
                continue
            best = pick_best_contenido(cat, context=context)
            if not best:
                continue
            pda = pick_best_pda(best.pdas, context=context + "\n" + best.contenido, grado=grado)
            out_campos.append(
                {
                    "campo_formativo": cat.campo_formativo,
                    "contenido": best.contenido,
                    "pda": pda,
                    "fuente": cat.source_path,
                }
            )

        if out_campos:
            return {"grado": _to_text(grado), "campos": out_campos}

    campos_txt = "\n".join([f"- {c}" for c in campos_formativos if isinstance(c, str) and c.strip()])

    prompt = f"""
Eres un docente experto en educación básica en México (Nueva Escuela Mexicana).

Necesito redactar la sección "CONTENIDOS Y PDA" para una planeación.

Tema: {tema}
Grado: {grado}
Campos formativos a incluir (solo estos):
{campos_txt}

Reglas:
- No inventes campos formativos fuera de la lista.
- El "contenido" debe ser concreto y breve (1-2 renglones).
- En "procesos" escribe 3 niveles de progresión: grado anterior, actual y siguiente.
  Ejemplo si Grado=3 => usar claves: "2°", "3°", "4°".
  Si no se puede inferir, usa "prev", "actual", "next".
- Devuelve SOLO JSON con esta estructura:
{{
  "grado": "",
  "campos": [
    {{
      "campo_formativo": "",
      "contenido": "",
      "procesos": {{
        "2°": "",
        "3°": "",
        "4°": ""
      }}
    }}
  ]
}}
"""

    respuesta = generar_respuesta(prompt)
    try:
        return _normalize_contenidos_pda(parse_llm_json_object(respuesta))
    except ValueError:
        reprompt = f"""
Convierte el siguiente contenido a JSON válido y responde SOLO con JSON.

Estructura requerida:
{{
  "grado": "",
  "campos": [
    {{
      "campo_formativo": "",
      "contenido": "",
      "procesos": {{}}
    }}
  ]
}}

Contenido a convertir:
{respuesta}
"""
        respuesta2 = generar_respuesta(reprompt)
        return _normalize_contenidos_pda(parse_llm_json_object(respuesta2))
