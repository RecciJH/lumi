from services.llm_json_service import parse_llm_json
import re

from services.llm_service import generar_respuesta


_VERB_HINTS = (
    "observa",
    "pregunta",
    "explora",
    "dibuja",
    "recorta",
    "ordena",
    "compara",
    "clasifica",
    "registra",
    "anota",
    "escribe",
    "conversa",
    "comparte",
    "discute",
    "identifica",
    "mide",
    "cuenta",
    "arma",
    "construye",
    "realiza",
    "experimenta",
    "investiga",
    "lee",
    "escucha",
    "juega",
    "representa",
    "marca",
    "colorea",
    "pega",
    "señala",
    "describe",
    "explica",
    "argumenta",
    "reflexiona",
)


def _looks_like_step(text: str) -> bool:
    t = _to_text(text)
    if not t:
        return False
    t_low = t.lower()
    if any(ch in t for ch in (".", ":", "¿", "?", "¡", "!", "\n", "(", ")")):
        return True
    if len(t.split()) >= 7:
        return True
    return any(v in t_low for v in _VERB_HINTS)


def _looks_like_materials_block(text: str) -> bool:
    """
    Detecta "texto" que en realidad parece lista de materiales (líneas cortas, sin verbos).
    """
    t = _to_text(text)
    if not t:
        return False
    lines = [ln.strip("-• \t\r") for ln in t.splitlines() if ln.strip()]
    if not lines:
        return False
    if len(lines) < 2:
        return False
    # Si casi todas las líneas son muy cortas y sin verbos -> materiales
    short = sum(1 for ln in lines if len(ln.split()) <= 4)
    verbish = sum(1 for ln in lines if any(v in ln.lower() for v in _VERB_HINTS))
    return short >= max(2, int(0.8 * len(lines))) and verbish == 0


def _clean_text(text: str) -> str:
    """
    Normaliza texto para que el PDF no muestre artefactos comunes del modelo (markdown, bullets raros).
    """
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not s:
        return ""
    s = s.replace("**", "")
    s = re.sub(r"^\s*#{1,6}\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*\*\s+", "- ", s, flags=re.MULTILINE)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _clean_text(value.strip())
    if isinstance(value, dict):
        # Common structured step formats returned by LLMs
        titulo = value.get("titulo") or value.get("título") or value.get("title")
        contenido = (
            value.get("contenido")
            or value.get("content")
            or value.get("descripcion")
            or value.get("descripción")
            or value.get("description")
        )
        if titulo and contenido:
            return f"{_to_text(titulo)}: {_to_text(contenido)}".strip()
        if contenido:
            return _to_text(contenido)
        if titulo:
            return _to_text(titulo)

        # Common "role split" / "structured section" dicts
        docente = value.get("docente") or value.get("acción_docente") or value.get("accion_docente")
        alumno = value.get("alumno") or value.get("alumnado") or value.get("estudiantes")
        preguntas = value.get("preguntas_detonadoras") or value.get("preguntas") or value.get("preguntas guía")
        organizacion = value.get("organización") or value.get("organizacion")
        tiempo = value.get("tiempo")
        if any(x is not None for x in (docente, alumno, preguntas, organizacion, tiempo)):
            parts: list[str] = []
            if docente is not None:
                ds = _to_str_list(docente)
                if ds:
                    parts.append("Docente:")
                    parts.extend([f"- {d}" for d in ds])
                else:
                    dt = _to_text(docente)
                    if dt:
                        parts.append(f"Docente: {dt}")
            if alumno is not None:
                als = _to_str_list(alumno)
                if als:
                    parts.append("Alumnado:")
                    parts.extend([f"- {a}" for a in als])
                else:
                    at = _to_text(alumno)
                    if at:
                        parts.append(f"Alumnado: {at}")
            if preguntas is not None:
                qs = _to_str_list(preguntas)
                if qs:
                    parts.append("Preguntas detonadoras:")
                    parts.extend([f"- {q}" for q in qs])
            if organizacion is not None:
                org = _to_text(organizacion)
                if org:
                    parts.append(f"Organización: {org}")
            if tiempo is not None:
                tt = _to_text(tiempo)
                if tt:
                    parts.append(f"Tiempo: {tt}")
            if parts:
                return "\n".join(parts).strip()

        # Generic dict pretty-print (avoid raw "{'k': ...}")
        lines: list[str] = []
        for k, v in value.items():
            key = _to_text(k)
            if isinstance(v, list):
                items = _to_str_list(v)
                if not items:
                    continue
                lines.append(f"{key}:")
                lines.extend([f"- {it}" for it in items])
            else:
                vv = _to_text(v)
                if vv:
                    lines.append(f"{key}: {vv}")
        if lines:
            return "\n".join(lines).strip()

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
    # Optional rich sections (used later by sesiones/PDF builder)
    for k in ("inicio", "desarrollo", "cierre"):
        if k in data:
            data[k] = _to_text(data.get(k))
    materiales = _to_str_list(data.get("materiales"))
    if not materiales:
        materiales = _to_str_list(data.get("material"))
    data["materiales"] = materiales
    data["pasos"] = _to_str_list(data.get("pasos"))

    if not data["actividad"]:
        # Fallback para evitar romper el pipeline cuando el modelo deja `actividad` vacía,
        # pero sí devuelve secciones útiles.
        candidates = []
        for k in ("inicio", "desarrollo", "cierre"):
            candidates.append(_to_text(data.get(k)))
        candidates.extend(_to_str_list(data.get("pasos"))[:2])
        candidates = [c for c in candidates if c]
        if candidates:
            first_line = candidates[0].splitlines()[0].strip()
            data["actividad"] = (first_line[:90] or "Actividad").strip()
        else:
            data["actividad"] = "Actividad"

    return data


def _coerce_activity_payload(value, *, momento: str) -> dict:
    """
    Normaliza respuestas inesperadas del LLM a un dict con la estructura de actividad.

    El modelo a veces devuelve:
    - una lista (de pasos como strings)
    - una lista de objetos {titulo/contenido}
    En esos casos lo convertimos a {"actividad","inicio","desarrollo","cierre","materiales","pasos"}.
    """
    if isinstance(value, dict):
        return value

    if isinstance(value, list):
        items = _to_str_list(value)
        step_votes = sum(1 for it in items if _looks_like_step(it))
        treat_as_steps = bool(items) and (step_votes / max(1, len(items))) >= 0.5

        if not treat_as_steps:
            # Probablemente el modelo devolvió materiales en forma de lista.
            return {
                "actividad": f"Actividad ({_to_text(momento)})",
                "inicio": "",
                "desarrollo": "",
                "cierre": "",
                "materiales": items,
                "pasos": [],
            }

        pasos = items
        inicio = ""
        desarrollo = ""
        cierre = ""
        if len(pasos) >= 5:
            inicio = "\n".join(pasos[:2])
            desarrollo = "\n".join(pasos[2:-2])
            cierre = "\n".join(pasos[-2:])
        elif len(pasos) == 4:
            inicio = pasos[0]
            desarrollo = "\n".join(pasos[1:3])
            cierre = pasos[3]
        elif len(pasos) == 3:
            inicio, desarrollo, cierre = pasos
        elif len(pasos) == 2:
            inicio, cierre = pasos
        elif len(pasos) == 1:
            desarrollo = pasos[0]

        return {
            "actividad": f"Actividad ({_to_text(momento)})",
            "inicio": inicio,
            "desarrollo": desarrollo,
            "cierre": cierre,
            "materiales": [],
            "pasos": pasos,
        }

    # Último recurso: convertir a texto.
    text = _to_text(value)
    return {
        "actividad": text or f"Actividad ({_to_text(momento)})",
        "inicio": "",
        "desarrollo": text,
        "cierre": "",
        "materiales": [],
        "pasos": [text] if text else [],
    }


def _ensure_activity_sections(activity: dict, *, tema: str, grado: str, momento: str) -> dict:
    """
    Asegura que inicio/desarrollo/cierre tengan contenido útil.

    Si el modelo no los llena, los derivamos de `pasos` o ponemos un fallback estructurado.
    """
    pasos = activity.get("pasos")
    if not isinstance(pasos, list):
        pasos = []
    paso_texts = _to_str_list(pasos)

    inicio = _to_text(activity.get("inicio"))
    desarrollo = _to_text(activity.get("desarrollo"))
    cierre = _to_text(activity.get("cierre"))

    # Si el modelo puso materiales en lugar de texto pedagógico, lo tratamos como vacío.
    if _looks_like_materials_block(inicio):
        inicio = ""
    if _looks_like_materials_block(desarrollo):
        desarrollo = ""
    if _looks_like_materials_block(cierre):
        cierre = ""

    # Derivar secciones desde pasos si están vacías.
    if paso_texts:
        if not inicio and len(paso_texts) >= 1:
            inicio = paso_texts[0]
        if not cierre and len(paso_texts) >= 2:
            cierre = paso_texts[-1]
        if not desarrollo and len(paso_texts) > 2:
            desarrollo = "\n".join(paso_texts[1:-1])

    def moment_label(m: str) -> str:
        ml = _to_text(m).lower()
        if "punto" in ml or "partida" in ml:
            return "Punto de partida"
        if "plane" in ml:
            return "Planeación"
        if "trabaj" in ml:
            return "A trabajar"
        if "comun" in ml:
            return "Comunicar"
        return "Reflexión"

    mlab = moment_label(momento)

    # Fallback con VARIACIÓN por momento (evita que todas queden iguales).
    if not (inicio and desarrollo and cierre):
        if mlab == "Punto de partida":
            inicio = inicio or (
                "(5 min) Activación y saberes previos:\n"
                f"- Muestra 3 imágenes (o un video corto) sobre: {tema}.\n"
                "- Preguntas detonadoras: ¿Qué cambia? ¿Qué seres vivos observas? ¿Cómo lo sabes?\n"
                "- Registra ideas en el pizarrón/papel bond."
            )
            desarrollo = desarrollo or (
                "(25 min) Observación guiada:\n"
                "- Salida breve al patio/ventana: observar plantas/animales/temperatura (seguro y con reglas).\n"
                "- Alumnado registra con dibujo + 2 palabras clave (según el grado).\n"
                "- En equipos, comparan registros y eligen 1 hallazgo para compartir."
            )
            cierre = cierre or (
                "(10 min) Cierre:\n"
                "- Puesta en común (2–3 equipos) y conclusión colectiva.\n"
                "- Evidencia: registro en cuaderno/hoja + participación oral."
            )
        elif mlab == "Planeación":
            inicio = inicio or (
                "(5 min) Enfoque del problema:\n"
                f"- Recupera lo observado sobre {tema} y plantea una pregunta guía del proyecto.\n"
                "- Aclara qué se quiere averiguar o explicar hoy."
            )
            desarrollo = desarrollo or (
                "(25 min) Organizamos la información:\n"
                "- En parejas, clasifican lo observado en: clima / plantas / animales.\n"
                "- Elaboran un cuadro simple (3 columnas) y escriben 1 ejemplo por columna.\n"
                "- Docente circula, pregunta y ayuda a precisar vocabulario."
            )
            cierre = cierre or (
                "(10 min) Acuerdos:\n"
                "- Cada pareja comparte 1 idea.\n"
                "- Se acuerda qué evidencia se juntará para el producto final (lista en el salón)."
            )
        elif mlab == "A trabajar":
            inicio = inicio or (
                "(5 min) Consigna y roles:\n"
                "- Explica el reto del día y asigna roles (observador/a, registrador/a, portavoz).\n"
                "- Reglas de uso de materiales y cuidado del entorno."
            )
            desarrollo = desarrollo or (
                "(25 min) Trabajo práctico:\n"
                "- Actividad manipulativa: comparar 2 escenarios (con/sin sombra, seco/húmedo, etc.) según {tema}.\n"
                "- Registran resultados con una tabla simple o pictogramas.\n"
                "- Docente modela cómo describir con evidencia (\"veo…\", \"cambió…\")."
            )
            cierre = cierre or (
                "(10 min) Socialización:\n"
                "- Presentan hallazgos y justifican con su registro.\n"
                "- Retroalimentación breve: qué fue claro y qué mejorar."
            )
        elif mlab == "Comunicar":
            inicio = inicio or (
                "(5 min) Preparación para comunicar:\n"
                "- Define formato: cartel/infografía mini/maqueta simple.\n"
                "- Revisa criterios: título, 3 ideas clave, evidencia visual."
            )
            desarrollo = desarrollo or (
                "(25 min) Elaboración del producto:\n"
                "- En equipos, transforman sus registros en un material para explicar {tema}.\n"
                "- Incluyen al menos 1 dibujo y 1 texto breve por integrante.\n"
                "- Docente apoya con preguntas: ¿qué quieres que el público entienda?"
            )
            cierre = cierre or (
                "(10 min) Galería:\n"
                "- Exponen (1 min por equipo) y reciben 1 pregunta del grupo.\n"
                "- Evidencia: cartel/producto + explicación oral."
            )
        else:  # Reflexión
            inicio = inicio or (
                "(5 min) Recuperación:\n"
                "- Repasa lo trabajado y muestra 2 evidencias del grupo.\n"
                "- Pregunta: ¿qué aprendimos sobre {tema}?"
            )
            desarrollo = desarrollo or (
                "(25 min) Reflexión guiada:\n"
                "- Semáforo (verde/amarillo/rojo): qué entendí, qué dudo, qué necesito practicar.\n"
                "- En equipos, proponen 2 mejoras para el producto final.\n"
                "- Docente registra acuerdos y apoya con ejemplos."
            )
            cierre = cierre or (
                "(10 min) Cierre:\n"
                "- Compromiso: 1 acción concreta para mejorar el trabajo.\n"
                "- Evidencia: autoevaluación + acuerdos del grupo."
            )

    # Si el título quedó genérico, proponemos uno específico según momento/tema.
    if _to_text(activity.get("actividad")).strip().lower() in ("actividad", "") or _to_text(activity.get("actividad")).strip().lower().startswith("actividad ("):
        activity["actividad"] = f"{mlab}: {tema}".strip()

    # Enforce: nunca breve. Si el modelo dio texto corto, lo ampliamos (sin depender de otro llamado).
    def ensure_lines(section: str, min_lines: int, extras: list[str]) -> str:
        sec = _to_text(section)
        lines = [ln.strip() for ln in sec.splitlines() if ln.strip()]
        if len(lines) >= min_lines:
            return sec
        existing = sec.lower()
        out_lines = list(lines)
        for ex in extras:
            ex_clean = _to_text(ex)
            if not ex_clean:
                continue
            if ex_clean.lower() in existing:
                continue
            out_lines.append(ex_clean)
            existing += "\n" + ex_clean.lower()
            if len([ln for ln in out_lines if ln.strip()]) >= min_lines:
                break
        return "\n".join(out_lines).strip()

    preguntas_base = [
        "Preguntas detonadoras:",
        "- ¿Qué observaste que cambió y cómo lo sabes?",
        "- ¿Qué relación tiene ese cambio con el clima/estación?",
        "- ¿Qué pasaría si no ocurriera ese cambio?",
    ]
    evaluacion_base = [
        "Evaluación formativa (observables):",
        "- Participa y argumenta con base en lo que observa/registra.",
        "- Sigue la consigna y usa materiales con cuidado.",
        "- Comunica un hallazgo con evidencia (dibujo, marcas, palabras).",
    ]
    adecuaciones_base = [
        "Adecuaciones:",
        "- Apoyo visual (imágenes/pictogramas) y consignas por pasos.",
        "- Opciones de respuesta: señalar/dibujar/decir en lugar de escribir.",
        "- Trabajo en pareja tutor/a para acompañamiento.",
    ]
    evidencia_base = ["Evidencia: registro en cuaderno/hoja de trabajo + participación oral."]

    if mlab == "Punto de partida":
        inicio = ensure_lines(
            inicio,
            10,
            [
                "Propósito: reconocer cambios de la primavera en seres vivos a partir de observación.",
                *preguntas_base,
                "Organización: plenaria → equipos pequeños (3–4).",
            ],
        )
        desarrollo = ensure_lines(
            desarrollo,
            12,
            [
                "Docente: recuerda reglas del recorrido y asigna roles (observador/a, registrador/a, portavoz).",
                "Alumnado: registra 3 hallazgos (1 planta, 1 animal, 1 clima) con dibujo + palabras clave.",
                "Esta actividad permitirá: fortalecer observación, vocabulario y explicación con evidencia.",
                *evaluacion_base,
            ],
        )
        cierre = ensure_lines(
            cierre,
            10,
            [
                "Cierre con 2 preguntas: ¿qué aprendimos hoy? ¿qué queremos investigar después?",
                *evidencia_base,
            ],
        )
    elif mlab == "Planeación":
        inicio = ensure_lines(
            inicio,
            10,
            [
                "Propósito: organizar información (clima/plantas/animales) para explicar el fenómeno.",
                *preguntas_base,
                "Organización: parejas.",
            ],
        )
        desarrollo = ensure_lines(
            desarrollo,
            12,
            [
                "Docente: entrega organizador gráfico (3 columnas) y modela un ejemplo.",
                "Alumnado: completa el cuadro con 3 ejemplos y subraya el más importante.",
                "Esta actividad permitirá: ordenar ideas, comparar y construir una explicación simple.",
                *evaluacion_base,
            ],
        )
        cierre = ensure_lines(
            cierre,
            10,
            [
                "Cierre: acuerdos del grupo sobre qué evidencia se usará en el producto final.",
                *evidencia_base,
            ],
        )
    elif mlab == "A trabajar":
        inicio = ensure_lines(
            inicio,
            10,
            [
                "Propósito: realizar una actividad práctica para comprobar/explicar un cambio observado.",
                "Organización: equipos con roles.",
                *preguntas_base,
            ],
        )
        desarrollo = ensure_lines(
            desarrollo,
            12,
            [
                "Docente: da tiempos por fase (preparación, ejecución, registro, revisión).",
                "Alumnado: registra resultados en tabla o pictogramas y compara con otro equipo.",
                "Esta actividad permitirá: experimentar, registrar datos simples y explicar con evidencia.",
                *evaluacion_base,
            ],
        )
        cierre = ensure_lines(
            cierre,
            10,
            [
                "Cierre: retroalimentación breve (1 fortaleza + 1 mejora por equipo).",
                *evidencia_base,
            ],
        )
    elif mlab == "Comunicar":
        inicio = ensure_lines(
            inicio,
            10,
            [
                "Propósito: comunicar hallazgos de forma clara para un público (grupo/escuela).",
                "Organización: equipos.",
                "Criterios: título, 3 ideas clave, evidencia visual, explicación oral breve.",
            ],
        )
        desarrollo = ensure_lines(
            desarrollo,
            12,
            [
                "Docente: circula y hace preguntas para precisar (¿qué evidencia lo muestra?).",
                "Alumnado: integra dibujo + texto breve y ensaya explicación (30–60 s).",
                "Esta actividad permitirá: comunicar procesos, escuchar preguntas y mejorar el producto.",
                *evaluacion_base,
            ],
        )
        cierre = ensure_lines(
            cierre,
            10,
            [
                "Cierre: galería con 1 pregunta del público y 1 ajuste al producto.",
                *evidencia_base,
            ],
        )
    else:  # Reflexión
        inicio = ensure_lines(
            inicio,
            10,
            [
                "Propósito: reflexionar sobre lo aprendido y acordar mejoras para el producto final.",
                "Organización: plenaria y equipos.",
            ],
        )
        desarrollo = ensure_lines(
            desarrollo,
            12,
            [
                "Docente: guía autoevaluación (semáforo) y recupera evidencias del grupo.",
                "Alumnado: propone 2 mejoras y explica por qué.",
                "Esta actividad permitirá: metacognición, mejora continua y compromiso con el proyecto.",
                *evaluacion_base,
                *adecuaciones_base,
            ],
        )
        cierre = ensure_lines(
            cierre,
            10,
            [
                "Cierre: compromiso individual + acuerdo grupal (qué haremos la próxima sesión).",
                *evidencia_base,
            ],
        )

    # Materiales mínimos (para que Recursos no quede vacío).
    materiales = activity.get("materiales")
    if not isinstance(materiales, list):
        materiales = []
    materiales = _to_str_list(materiales)
    if not materiales:
        baseline = ["Cuaderno", "Lápiz", "Pizarrón o papel bond", "Marcadores"]
        if mlab == "Punto de partida":
            baseline.append("Imágenes impresas (o recortes) relacionadas con el tema")
        if mlab == "Comunicar":
            baseline.extend(["Cartulina o hojas", "Colores/crayolas", "Pegamento"])
        materiales = baseline
    activity["materiales"] = materiales

    # Pasos mínimos (10-14) coherentes con las secciones.
    def extract_steps(text: str) -> list[str]:
        out: list[str] = []
        for ln in (_to_text(text) or "").splitlines():
            s = ln.strip().lstrip("-•").strip()
            if not s:
                continue
            if s.endswith(":") and len(s.split()) <= 4:
                continue
            out.append(s)
        return out

    steps = _to_str_list(activity.get("pasos"))
    if len(steps) < 10:
        derived = extract_steps(inicio) + extract_steps(desarrollo) + extract_steps(cierre)
        merged: list[str] = []
        seen: set[str] = set()
        for s in steps + derived:
            key = s.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(s)
        steps = merged

    if len(steps) < 10:
        append_steps = [
            "Organiza al grupo y presenta el propósito del día.",
            "Plantea preguntas detonadoras y recupera saberes previos.",
            "Explica la consigna paso a paso y modela un ejemplo breve.",
            "Distribuye materiales y asigna roles (si aplica).",
            "Acompaña el trabajo; realiza preguntas para precisar ideas.",
            "Pide registro de evidencia (dibujo/marcas/palabras) en cuaderno/hoja.",
            "Detén para un chequeo rápido: ¿qué vamos entendiendo?",
            "Socializa 2–3 participaciones y recupera hallazgos clave.",
            "Da retroalimentación formativa (1 fortaleza + 1 mejora).",
            "Cierra con una conclusión y un acuerdo para la siguiente sesión.",
        ]
        existing = {s.lower() for s in steps}
        for s in append_steps:
            if len(steps) >= 12:
                break
            if s.lower() not in existing:
                steps.append(s)
                existing.add(s.lower())

    activity["pasos"] = steps[:14]

    activity["inicio"] = inicio
    activity["desarrollo"] = desarrollo
    activity["cierre"] = cierre
    return activity


def _needs_refinement(activity: dict) -> bool:
    """
    Señales de que el contenido quedó genérico/corto y conviene pedir una corrección al modelo.
    """
    actividad_txt = _to_text(activity.get("actividad"))
    inicio = _to_text(activity.get("inicio"))
    desarrollo = _to_text(activity.get("desarrollo"))
    cierre = _to_text(activity.get("cierre"))

    if not (inicio and desarrollo and cierre):
        return True

    if actividad_txt.strip().lower() == "actividad" or actividad_txt.strip().lower().startswith("actividad ("):
        return True

    # Detecta nuestro fallback genérico
    fallback_markers = ("Activación y encuadre", "Desarrollo guiado", "Cierre y metacognición")
    if any(m.lower() in (inicio + desarrollo + cierre).lower() for m in fallback_markers):
        return True

    # Muy corto o sin estructura accionable
    total_len = len(inicio) + len(desarrollo) + len(cierre)
    if total_len < 520:
        return True

    # Sin verbos/acciones claras (típico de respuestas pobres)
    verbish = sum(1 for part in (inicio, desarrollo, cierre) if any(v in part.lower() for v in _VERB_HINTS))
    if verbish <= 1:
        return True

    return False


def _refine_activity_with_llm(
    *,
    tema: str,
    grado: str,
    momento: str,
    estrategia: str,
    proyecto: str,
    historial: str,
    current: dict,
) -> dict:
    """
    Segundo pase (solo cuando hace falta) para forzar detalle consistente.
    """
    prompt = f"""
Corrige y mejora la siguiente actividad para que quede MUY detallada y específica, tipo planeación SEP.

Tema: {tema}
Grado: {grado}
Momento metodológico: {momento}
Estrategia pedagógica: {estrategia}
Proyecto educativo: {proyecto}
Actividades anteriores (evita repetir exactamente): {historial}

Actividad actual (puede estar incompleta): {current}

Requisitos:
- NO uses títulos genéricos como "Actividad". Pon un título específico.
- Escribe INICIO/DESARROLLO/CIERRE con acciones del docente y del alumnado, preguntas detonadoras, organización (individual/parejas/equipos), y tiempos por sección (sumar ~40 min).
- Incluye evaluación formativa: qué observar y cómo registrar (evidencia).
- `materiales` como lista (sin inventar demasiado, usa lo que haya y agrega solo lo necesario).
- `pasos`: lista de 10–14 strings detallados (no objetos/dicts), coherentes con inicio/desarrollo/cierre.
- Responde SOLO con un objeto JSON (NO lista, NO texto extra) y SOLO estas claves:
{{
  "actividad": "",
  "inicio": "",
  "desarrollo": "",
  "cierre": "",
  "materiales": [],
  "pasos": []
}}
"""
    respuesta = generar_respuesta(prompt)
    parsed = parse_llm_json(respuesta)
    payload = _coerce_activity_payload(parsed, momento=momento)
    normalized = _normalize_activity_json(payload)
    return _ensure_activity_sections(normalized, tema=str(tema), grado=str(grado), momento=str(momento))


def generar_actividad_ia(tema, grado, momento, estrategia, historial, proyecto):
    """
    Genera una actividad individual usando la IA, devolviendo JSON limpio.
    Protege contra respuestas vacías o con formato incorrecto.
    """
    prompt = f"""
Eres un docente experto en educación básica en México.

Diseña una actividad educativa clara, creativa y MUY detallada (evita generalidades).

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

La actividad debe además:
- describir acciones observables del docente y del alumnado
- incluir preguntas detonadoras y evaluación formativa (qué observar/registrar)
- evitar pasos demasiado breves: escribe varios renglones por sección

Reglas de formato (muy importante):
- Devuelve SOLO JSON válido (sin texto extra).
- No devuelvas una lista/arreglo: debe ser un objeto JSON (dict) con las claves indicadas.
- En `pasos` NO uses objetos/dicts; SOLO strings.
- En `inicio`/`desarrollo`/`cierre` usa párrafos y/o viñetas con saltos de línea.
- Incluye tiempos sugeridos por sección (ej. \"(5 min)\") sin exceder 40 min en total.
- No uses títulos genéricos como "Actividad".

Devuelve SOLO JSON con esta estructura EXACTA:

{{
  "actividad": "",
  "inicio": "",
  "desarrollo": "",
  "cierre": "",
  "materiales": [],
  "pasos": []
}}
"""

    respuesta = generar_respuesta(prompt)

    if not respuesta or respuesta.strip() == "":
        raise ValueError("Activity agent devolvió respuesta vacía")

    try:
        parsed = parse_llm_json(respuesta)
        payload = _coerce_activity_payload(parsed, momento=momento)
        normalized = _normalize_activity_json(payload)
        enriched = _ensure_activity_sections(normalized, tema=str(tema), grado=str(grado), momento=str(momento))
        if _needs_refinement(enriched):
            enriched = _refine_activity_with_llm(
                tema=str(tema),
                grado=str(grado),
                momento=str(momento),
                estrategia=str(estrategia),
                proyecto=str(proyecto),
                historial=str(historial),
                current=enriched,
            )
        return enriched
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
- "actividad" debe ser un texto NO vacío (nombre + propósito en 1 frase).
- "inicio", "desarrollo" y "cierre" deben ser textos detallados (varios renglones cada uno), con acciones del docente y del alumnado.
- "pasos" debe tener al menos 8 pasos claros y detallados (strings únicamente, sin objetos/dicts).
- "materiales" debe ser una lista (puede estar vacía solo si realmente no aplica).
- Responde con un objeto JSON (NO una lista/arreglo).

Devuelve SOLO JSON con esta estructura EXACTA:
{{
  "actividad": "",
  "inicio": "",
  "desarrollo": "",
  "cierre": "",
  "materiales": [],
  "pasos": []
}}

Respuesta anterior a corregir:
{respuesta}
"""
        respuesta2 = generar_respuesta(reprompt)
        parsed2 = parse_llm_json(respuesta2)
        payload2 = _coerce_activity_payload(parsed2, momento=momento)
        normalized2 = _normalize_activity_json(payload2)
        enriched2 = _ensure_activity_sections(normalized2, tema=str(tema), grado=str(grado), momento=str(momento))
        if _needs_refinement(enriched2):
            enriched2 = _refine_activity_with_llm(
                tema=str(tema),
                grado=str(grado),
                momento=str(momento),
                estrategia=str(estrategia),
                proyecto=str(proyecto),
                historial=str(historial),
                current=enriched2,
            )
        return enriched2


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
