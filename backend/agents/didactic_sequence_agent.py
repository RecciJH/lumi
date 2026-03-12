from services.llm_json_service import parse_llm_json_object
from services.llm_service import generar_respuesta


def generar_secuencia_didactica(tema, grado, proyecto, actividades):

    prompt = f"""
Eres un experto en educación básica en México.

Organiza la siguiente planeación didáctica según la Nueva Escuela Mexicana.

Tema: {tema}
Grado: {grado}

Proyecto educativo:
{proyecto}

Actividades generadas:
{actividades}

NO inventes nuevas actividades.
Solo organiza las existentes.

Devuelve SOLO JSON con esta estructura:

{{
 "inicio": "",
 "desarrollo": "",
 "cierre": "",
 "evaluacion": "",
 "evidencias": [],
 "materiales": []
}}
"""

    respuesta = generar_respuesta(prompt)

    try:
        return parse_llm_json_object(respuesta)
    except ValueError:
        reprompt = f"""
Convierte el siguiente contenido a JSON válido y responde SOLO con JSON.

Estructura requerida:
{{
 "inicio": "",
 "desarrollo": "",
 "cierre": "",
 "evaluacion": "",
 "evidencias": [],
 "materiales": []
}}

Contenido a convertir:
{respuesta}
"""
        respuesta2 = generar_respuesta(reprompt)
        return parse_llm_json_object(respuesta2)
