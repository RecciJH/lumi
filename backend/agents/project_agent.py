import json

from services.llm_service import generar_respuesta
from services.llm_json_service import parse_llm_json_object


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_project_json(data: dict) -> dict:
    required = [
        "nombre_proyecto",
        "problematica",
        "justificacion",
        "proposito",
        "producto_final",
        "temporalidad",
    ]
    for k in required:
        data.setdefault(k, "")

    # Forzar strings (el modelo a veces manda dict/list en temporalidad)
    for k in ("nombre_proyecto", "problematica", "justificacion", "proposito", "producto_final"):
        data[k] = _to_text(data.get(k))

    temporalidad = data.get("temporalidad")
    if isinstance(temporalidad, (dict, list)):
        data["temporalidad"] = _to_text(json.dumps(temporalidad, ensure_ascii=False))
    else:
        data["temporalidad"] = _to_text(temporalidad)

    if not data["nombre_proyecto"] or not data["producto_final"]:
        raise ValueError("El proyecto generado llegó incompleto (campos vacíos).")

    return data


def generar_proyecto(tema, grado, duracion_dias: int | None = None):

    prompt = f"""
Eres un experto en educación básica en México.

Diseña un proyecto educativo basado en la Nueva Escuela Mexicana.

Tema: {tema}
Grado: {grado}
{f'Duración total disponible: {duracion_dias} días (aprox. 1 sesión por día).' if duracion_dias else ''}

Devuelve la respuesta SOLO en formato JSON así:

{{
 "nombre_proyecto": "",
 "problematica": "",
 "justificacion": "",
 "proposito": "",
 "producto_final": "",
 "temporalidad": ""
}}
"""

    respuesta = generar_respuesta(prompt)
    
    if not respuesta or respuesta.strip() == "":
        raise ValueError("Project agent devolvió respuesta vacía")
    
    try:
        return _normalize_project_json(parse_llm_json_object(respuesta))
    except ValueError:
        reprompt = f"""
Tu respuesta anterior no cumplió el formato o dejó campos vacíos. Corrige y responde SOLO con JSON.

Reglas:
- No dejes campos vacíos.
- "temporalidad" debe ser un TEXTO corto y coherente con la duración disponible.

Estructura requerida:
{{
 "nombre_proyecto": "",
 "problematica": "",
 "justificacion": "",
 "proposito": "",
 "producto_final": "",
 "temporalidad": ""
}}

Respuesta anterior a corregir:
{respuesta}
"""
        respuesta2 = generar_respuesta(reprompt)
        return _normalize_project_json(parse_llm_json_object(respuesta2))
