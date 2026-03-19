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
Eres especialista en educación preescolar en México bajo el Plan de Estudio 2022 (Nueva Escuela Mexicana).

Diseña un proyecto educativo situado y coherente con la NEM.

Contexto:
- Tema central: {tema}
- Grado: {grado}
{f'- Duración total disponible: {duracion_dias} días (aprox. 1 sesión por día).' if duracion_dias else ''}

Criterios OBLIGATORIOS:

1) PROBLEMÁTICA (enfoque contextualizado y comunitario)
- Debe describir una situación REAL del entorno (comunidad, familia, contexto social o ambiental), NO una carencia de los niños.
- NO uses frases deficitarias como "los alumnos no saben", "no conocen", "tienen dificultades para", etc.
- Describe cómo se vive el tema en la comunidad (clima, uso de recursos, costumbres, situaciones cotidianas).
- Explica por qué el tema es relevante en la vida cotidiana de las niñas y los niños.

2) ENFOQUE PEDAGÓGICO NEM (aunque no se pida explícito, debe notarse en la redacción)
- Aprendizaje situado y significativo, vinculado al contexto de vida del grupo.
- Inclusión, pensamiento crítico y trabajo con la comunidad.

3) PROPÓSITO (aprendizaje significativo, sin verbos genéricos)
- Enfoca el propósito en lo que las niñas y los niños COMPRENDERÁN, RECONOCERÁN, RELACIONARÁN o CONSTRUIRÁN respecto al tema.
- EVITA verbos como "fomentar", "promover", "sensibilizar" como verbo principal.
- Usa verbos como: "comprender", "reconocer", "explicar con sus palabras", "relacionar con su vida diaria", "construir significados sobre…".

4) PRODUCTO FINAL
- Debe ser observable, realizable en preescolar y claramente vinculado al contexto (ej. mural comunitario, rincón en el aula, diario gráfico, cartel acordado con familias, etc.).
- Debe poder construirse parcialmente en cada sesión (coherencia con las actividades).

5) TEMPORALIDAD
- Escribe un texto corto que describa qué se hará, día por día o en bloques, sin detallar actividades específicas (eso lo hará otro agente).
- Puede ser una descripción general por días o sesiones, siempre en lenguaje claro.

Devuelve la respuesta SOLO en formato JSON con esta estructura EXACTA (sin texto adicional):

{{
 "nombre_proyecto": "Título atractivo para niñas y niños (breve).",
 "problematica": "Situación del contexto comunitario o familiar vinculada al tema, sin lenguaje deficitario sobre el alumnado.",
 "justificacion": "Explicación clara de por qué este proyecto es pertinente para la vida de las niñas y los niños y cómo se vincula con la NEM.",
 "proposito": "Enunciado único centrado en lo que las niñas y los niños comprenderán, reconocerán o construirán.",
 "producto_final": "Descripción concreta y observable del producto que se construirá a lo largo del proyecto.",
 "temporalidad": "Descripción breve de la organización del tiempo (por días o sesiones)."
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
