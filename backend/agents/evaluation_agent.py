from services.llm_json_service import parse_llm_json_object
from services.llm_service import generar_respuesta


LEVELS = ["Insuficiente", "Básico", "Satisfactorio", "Destacado"]


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _to_str_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = [_to_text(v) for v in value]
        return [i for i in items if i]
    if isinstance(value, str):
        items = [line.strip("-• \t\r") for line in value.splitlines()]
        return [i for i in items if i]
    return [_to_text(value)] if _to_text(value) else []


def _normalize_levels(levels_value) -> dict:
    if levels_value is None:
        return {lvl: "" for lvl in LEVELS}

    if isinstance(levels_value, dict):
        normalized: dict = {}
        lower_map = {str(k).strip().lower(): k for k in levels_value.keys()}
        for lvl in LEVELS:
            key = lower_map.get(lvl.lower())
            normalized[lvl] = _to_text(levels_value.get(key)) if key else ""
        return normalized

    if isinstance(levels_value, list):
        texts = [_to_text(v) for v in levels_value]
        texts = [t for t in texts if t]
        normalized = {lvl: "" for lvl in LEVELS}
        for i, lvl in enumerate(LEVELS):
            if i < len(texts):
                normalized[lvl] = texts[i]
        return normalized

    if isinstance(levels_value, str):
        items = _to_str_list(levels_value)
        normalized = {lvl: "" for lvl in LEVELS}
        for i, lvl in enumerate(LEVELS):
            if i < len(items):
                normalized[lvl] = items[i]
        return normalized

    return {lvl: "" for lvl in LEVELS}


def _normalize_criterio(item) -> dict:
    if isinstance(item, str):
        item = {"criterio": item}
    if not isinstance(item, dict):
        item = {"criterio": _to_text(item)}

    key_map = {str(k).strip().lower(): k for k in item.keys()}

    criterio_key = None
    for alias in ("criterio", "aspecto", "dimension", "dimensión", "criterios", "nombre"):
        if alias in key_map:
            criterio_key = key_map[alias]
            break

    criterio = _to_text(item.get(criterio_key)) if criterio_key else _to_text(item.get("criterio"))
    indicadores = _to_str_list(item.get(key_map.get("indicadores", "indicadores")))
    if not indicadores:
        indicadores = _to_str_list(item.get(key_map.get("indicador", "indicador")))

    evidencia = _to_text(item.get(key_map.get("evidencia", "evidencia")))
    if not evidencia:
        evidencia = _to_text(item.get(key_map.get("evidencias", "evidencias")))

    niveles = _normalize_levels(item.get(key_map.get("niveles", "niveles")))

    return {
        "criterio": criterio,
        "indicadores": indicadores,
        "evidencia": evidencia,
        "niveles": niveles,
    }


def _normalize_evaluation_json(data: dict) -> dict:
    instrumento = _to_text(data.get("instrumento")) or "rubrica"
    instrumento = instrumento.replace("rúbrica", "rubrica").lower()
    if instrumento != "rubrica":
        instrumento = "rubrica"

    criterios_raw = data.get("criterios")
    if criterios_raw is None:
        criterios_raw = data.get("rubrica") or data.get("rúbrica") or []

    if not isinstance(criterios_raw, list):
        criterios_raw = [criterios_raw]

    criterios = [_normalize_criterio(c) for c in criterios_raw]
    criterios = [c for c in criterios if c.get("criterio")]

    indicadores_top = data.get("indicadores")
    if indicadores_top is None:
        indicadores_top = []

    if isinstance(indicadores_top, list):
        indicadores = [_to_text(x) for x in indicadores_top]
        indicadores = [i for i in indicadores if i]
    else:
        indicadores = _to_str_list(indicadores_top)

    if not indicadores:
        indicadores = []
        for c in criterios:
            indicadores.extend(c.get("indicadores") or [])

    if not criterios:
        raise ValueError(
            "La evaluación generada no incluye 'criterios' válidos. "
            f"Claves recibidas: {sorted(list(data.keys()))}"
        )

    # Ensure 4 levels exist (keys) for every criterio
    for c in criterios:
        niveles = c.get("niveles") or {}
        c["niveles"] = {lvl: _to_text(niveles.get(lvl)) for lvl in LEVELS}

    return {
        "instrumento": "rubrica",
        "criterios": criterios,
        "indicadores": indicadores,
    }


def generar_evaluacion(tema, grado, curriculum, proyecto, secuencia, actividades):
    prompt = f"""
Eres un docente experto en educación básica en México.

Tu tarea es generar una evaluación (enfoque formativo) alineada a la Nueva Escuela Mexicana y a los criterios de la SEP.
Debe adaptarse a la planeación específica (tema, grado, PDA, producto final y actividades reales).

Datos de la planeación:
Tema: {tema}
Grado: {grado}

Currículum:
{curriculum}

Proyecto educativo:
{proyecto}

Secuencia didáctica:
{secuencia}

Actividades generadas:
{actividades}

Reglas:
- NO inventes nuevas actividades. Evalúa con base en el proyecto/actividades dadas.
- Usa indicadores observables y evidencias concretas (producto final, participación, bitácora, exposición, etc. si aplica).
- Instrumento: rúbrica analítica de 4 niveles EXACTOS: Insuficiente, Básico, Satisfactorio, Destacado.
- Evita lenguaje genérico; que sea útil para el aula.

Devuelve SOLO JSON con esta estructura:
{{
  "criterios": [
    {{
      "criterio": "",
      "indicadores": [""],
      "evidencia": "",
      "niveles": {{
        "Insuficiente": "",
        "Básico": "",
        "Satisfactorio": "",
        "Destacado": ""
      }}
    }}
  ],
  "instrumento": "rubrica",
  "indicadores": [""]
}}
"""

    respuesta = generar_respuesta(prompt)
    try:
        return _normalize_evaluation_json(parse_llm_json_object(respuesta))
    except ValueError:
        reprompt = f"""
Convierte el siguiente contenido a JSON válido y responde SOLO con JSON.

Estructura requerida:
{{
  "criterios": [
    {{
      "criterio": "",
      "indicadores": [""],
      "evidencia": "",
      "niveles": {{
        "Insuficiente": "",
        "Básico": "",
        "Satisfactorio": "",
        "Destacado": ""
      }}
    }}
  ],
  "instrumento": "rubrica",
  "indicadores": [""]
}}

Contenido a convertir:
{respuesta}
"""
        respuesta2 = generar_respuesta(reprompt)
        return _normalize_evaluation_json(parse_llm_json_object(respuesta2))

