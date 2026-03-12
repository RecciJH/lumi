from services.llm_json_service import parse_llm_json_object
from services.llm_service import generar_respuesta


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("actividad", "descripcion", "texto", "detalle"):
            if key in value:
                return _to_text(value.get(key))
        return str(value).strip()
    if isinstance(value, list):
        parts = [_to_text(v) for v in value]
        parts = [p for p in parts if p]
        return "; ".join(parts).strip()
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


def _normalize_activity_json(data: dict) -> dict:
    # Key aliases (common model variations)
    key_map = {str(k).strip().lower(): k for k in data.keys()}
    for alias in ("activity", "actividad", "nombre_actividad", "titulo", "título", "nombre"):
        if "actividad" in data:
            break
        if alias in key_map:
            data["actividad"] = data.get(key_map[alias])

    data["actividad"] = _to_text(data.get("actividad"))
    materiales = _to_str_list(data.get("materiales"))
    if not materiales:
        materiales = _to_str_list(data.get("material"))
    data["materiales"] = materiales
    data["pasos"] = _to_str_list(data.get("pasos"))

    if not data["actividad"]:
        raise ValueError(
            "La respuesta del activity_agent no incluye la clave 'actividad' (o viene vacía). "
            f"Claves recibidas: {sorted(list(data.keys()))}"
        )

    return data


def generar_actividad_ia(tema, grado, momento, estrategia, historial, proyecto):
    """
    Genera una actividad individual usando la IA, devolviendo JSON limpio.
    Protege contra respuestas vacías o con formato incorrecto.
    """
    prompt = f"""
Eres un docente experto en educación básica en México.

Diseña una actividad educativa clara y creativa.

Tema: {tema}
Grado: {grado}

Proyecto educativo:
{proyecto}

Momento metodológico: {momento}

Estrategia pedagógica:
{estrategia}

Actividades anteriores:
{historial}

La actividad debe:
- durar aproximadamente 40 minutos
- fomentar participación
- preparar el producto final del proyecto

Devuelve SOLO JSON con esta estructura:

{{
 "actividad": "",
 "materiales": [],
 "pasos": []
}}
"""

    respuesta = generar_respuesta(prompt)

    if not respuesta or respuesta.strip() == "":
        raise ValueError("Activity agent devolvió respuesta vacía")

    try:
        return _normalize_activity_json(parse_llm_json_object(respuesta))
    except ValueError:
        # Segundo intento: corregir estructura y asegurar campos NO vacíos.
        reprompt = f"""
Tu respuesta anterior no cumplió el formato o dejó campos vacíos. Corrige y responde SOLO con JSON.

Contexto (no inventes contenido fuera del tema/proyecto):
Tema: {tema}
Grado: {grado}
Momento metodológico: {momento}
Estrategia pedagógica: {estrategia}
Proyecto educativo: {proyecto}
Actividades anteriores: {historial}

Reglas:
- "actividad" debe ser un texto NO vacío (nombre + descripción breve).
- "pasos" debe tener al menos 3 pasos claros.
- "materiales" debe ser una lista (puede estar vacía solo si realmente no aplica).

Devuelve SOLO JSON con esta estructura EXACTA:
{{
  "actividad": "",
  "materiales": [],
  "pasos": []
}}

Respuesta anterior a corregir:
{respuesta}
"""
        respuesta2 = generar_respuesta(reprompt)
        return _normalize_activity_json(parse_llm_json_object(respuesta2))


def generar_actividades(tema, grado, momentos, estrategia, proyecto):
    """
    Genera todas las actividades de una secuencia didáctica.
    
    Args:
        tema (str): Tema de la planeación.
        grado (str): Grado escolar.
        momentos (list): Lista de dicts con {"dia": int, "momento": str}.
        estrategia (str): Estrategia pedagógica a aplicar.
        proyecto (dict): Información del proyecto educativo.

    Returns:
        list: Lista de actividades con dia, momento y JSON de la actividad.
    """
    actividades = []
    historial = ""

    for item in momentos:
        actividad_json = generar_actividad_ia(
            tema,
            grado,
            item["momento"],
            estrategia,
            historial,
            proyecto
        )

        actividades.append({
            "dia": item["dia"],
            "momento": item["momento"],
            "actividad": actividad_json
        })

        # Mantener historial de actividades para referencia en la IA
        historial += f"\nDia {item['dia']} - {actividad_json.get('actividad', '')}\n"

    return actividades
