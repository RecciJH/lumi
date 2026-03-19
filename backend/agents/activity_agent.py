from services.llm_json_service import parse_llm_json
import ast
import json
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
    # Si el modelo usa ';' como separador de pasos, lo convertimos a saltos de línea para legibilidad.
    if s.count(";") >= 2:
        s = s.replace("; ", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _short_text(text: str, *, max_len: int = 160) -> str:
    t = _to_text(text)
    if not t:
        return ""
    # Primera línea o primera oración
    first_line = t.splitlines()[0].strip()
    first_sentence = first_line.split(".")[0].strip() if "." in first_line else first_line
    out = first_sentence or first_line
    out = out.strip().rstrip(".")
    if len(out) > max_len:
        out = out[: max_len - 1].rstrip() + "…"
    return out


def _try_parse_mapping(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        t = value.strip()
        if not t:
            return {}
        if t.startswith("{") and t.endswith("}"):
            try:
                parsed = json.loads(t)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                try:
                    parsed = ast.literal_eval(t)  # noqa: S307 (solo literales)
                    return parsed if isinstance(parsed, dict) else {}
                except Exception:
                    return {}
    return {}


def _day_focus_from_project(proyecto, dia: int | None) -> str:
    if dia is None or not isinstance(dia, int):
        return ""
    if not isinstance(proyecto, dict):
        return ""
    temporalidad = _try_parse_mapping(proyecto.get("temporalidad"))
    if not temporalidad:
        return ""

    candidates = [
        f"día_{dia}",
        f"dia_{dia}",
        f"día {dia}",
        f"dia {dia}",
        str(dia),
    ]
    for k in candidates:
        if k in temporalidad:
            return _to_text(temporalidad.get(k))

    for k, v in temporalidad.items():
        ks = _to_text(k).lower()
        if str(dia) in ks:
            return _to_text(v)

    return ""


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


def _ensure_activity_sections(
    activity: dict,
    *,
    tema: str,
    grado: str,
    momento: str,
    dia: int | None = None,
    enfoque_dia: str = "",
    producto_final: str = "",
) -> dict:
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
    producto_final_txt = _to_text(producto_final)
    producto_final_short = _short_text(producto_final_txt, max_len=140)
    enfoque_txt = _to_text(enfoque_dia)

    # Fallback con VARIACIÓN por momento (evita que todas queden iguales).
    if not (inicio and desarrollo and cierre):
        if mlab == "Punto de partida":
            inicio = inicio or (
                "(5 min) Activación y saberes previos:\n"
                f"- Muestra 2 o 3 imágenes, objetos o situaciones relacionadas con el tema: {tema}.\n"
                "- Recupera lo que las niñas y los niños ya han vivido o escuchado sobre este tema.\n"
                "- Registra ideas en el pizarrón/papel bond usando palabras sencillas."
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
                f"- Recupera lo observado o comentado sobre {tema} y plantea una pregunta guía del proyecto.\n"
                "- Aclara de manera sencilla qué se quiere averiguar o explicar hoy."
            )
            desarrollo = desarrollo or (
                "(25 min) Organizamos la información:\n"
                "- En parejas o equipos pequeños, agrupan sus ideas o dibujos en categorías que tengan sentido para el tema.\n"
                "- Elaboran un cuadro simple y escriben o dibujan 1 ejemplo por categoría.\n"
                "- La docente circula, pregunta y ayuda a precisar el lenguaje que usan."
            )
            cierre = cierre or (
                "(10 min) Acuerdos:\n"
                "- Cada pareja comparte 1 idea.\n"
                "- Se acuerda qué evidencia se juntará para el producto final (lista en el salón)."
            )
        elif mlab == "A trabajar":
            inicio = inicio or (
                "(5 min) Consigna y roles:\n"
                "- Explica el reto del día y asigna roles (quien observa, quien registra, quien comparte al grupo).\n"
                "- Acuerda reglas de uso de materiales y de convivencia durante la actividad."
            )
            desarrollo = desarrollo or (
                "(25 min) Trabajo práctico:\n"
                f"- Las niñas y los niños realizan una experiencia concreta relacionada con {tema} (exploración, juego o pequeña indagación).\n"
                "- Registran lo que observan mediante dibujos, marcas o palabras sencillas.\n"
                "- La docente pregunta qué notan y les ayuda a relacionarlo con lo que ya habían comentado sobre el tema.\n"
                "- Se prepara un registro sencillo (tabla, cartel o colección de dibujos) que después alimentará el producto final."
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
                f"- En equipos, transforman sus registros en un material para explicar {tema}.\n"
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
                f"- Pregunta: ¿qué aprendimos sobre {tema}?"
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

    # Si el título quedó genérico, proponemos uno específico (preferimos enfoque de temporalidad del proyecto).
    if _to_text(activity.get("actividad")).strip().lower() in ("actividad", "") or _to_text(activity.get("actividad")).strip().lower().startswith("actividad ("):
        if enfoque_txt and dia is not None:
            activity["actividad"] = f"Día {dia}: {enfoque_txt}".strip()
        elif enfoque_txt:
            activity["actividad"] = enfoque_txt
        else:
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

    preguntas_punto_partida = [
        "Preguntas detonadoras:",
        f"- ¿Qué te viene a la mente cuando escuchas o ves algo relacionado con {tema}?",
        "- ¿Qué has vivido, visto o escuchado sobre este tema en tu casa o en tu comunidad?",
        "- ¿Por qué crees que es importante hablar de esto en el jardín de niñas y niños?",
    ]
    preguntas_planeacion = [
        "Preguntas detonadoras:",
        "- ¿Qué ideas se parecen y cuáles son diferentes?",
        "- ¿Qué ejemplos nos ayudan a explicar mejor este tema?",
        "- ¿Qué información nos hace falta para entenderlo mejor?",
    ]
    preguntas_trabajo = [
        "Preguntas detonadoras:",
        f"- ¿Qué queremos hacer con los materiales para explorar el tema: {tema}?",
        "- ¿Qué observamos que cambia o se nota durante la experiencia?",
        "- ¿Cómo lo registramos con un dibujo, una marca o palabras sencillas?",
    ]
    preguntas_comunicar = [
        "Preguntas detonadoras:",
        "- ¿Qué queremos que las demás niñas y niños comprendan con nuestra explicación breve?",
        "- ¿Qué evidencia vamos a mostrar (dibujo, registro, foto o muestra) para sostener la idea?",
        "- ¿Qué pregunta podría hacernos alguien y cómo responderíamos con lo que vimos?",
    ]
    preguntas_reflexion = [
        "Preguntas detonadoras:",
        "- ¿Qué aprendí y qué evidencia tengo de ello?",
        "- ¿Qué fue difícil y cómo lo resolví o lo resolvería?",
        "- ¿Qué mejoraría para que el producto final sea más claro?",
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

    contribucion = ""
    if producto_final_txt:
        if mlab == "Punto de partida":
            contribucion = f"Contribución al producto final: insumos (dibujos/observaciones) para {producto_final_short or producto_final_txt}."
        elif mlab == "Planeación":
            contribucion = f"Contribución al producto final: organizador de ideas y ejemplos sobre {tema} que alimenta {producto_final_short or producto_final_txt}."
        elif mlab == "A trabajar":
            contribucion = f"Contribución al producto final: tabla de resultados y conclusión breve para integrar en {producto_final_short or producto_final_txt}."
        elif mlab == "Comunicar":
            contribucion = f"Contribución al producto final: ensayo de explicación y ajustes a {producto_final_short or producto_final_txt}."
        else:
            contribucion = f"Contribución al producto final: mejoras y reflexiones finales para {producto_final_short or producto_final_txt}."

    if mlab == "Punto de partida":
        inicio = ensure_lines(
            inicio,
            10,
            [
                "Propósito: reconocer ideas y ejemplos sobre el tema a partir de lo que viven, observan o escuchan en su comunidad.",
                *preguntas_punto_partida,
                "Organización: plenaria → equipos pequeños (3–4).",
                contribucion,
            ],
        )
        desarrollo = ensure_lines(
            desarrollo,
            12,
            [
                "Docente: recuerda reglas del recorrido y asigna roles (observador/a, registrador/a, portavoz).",
                "Alumnado: registra 2 o 3 ejemplos o situaciones relacionadas con el tema en su vida cotidiana (por ejemplo: lo que ven en casa o en el barrio) con dibujo y palabras clave.",
                "Esta actividad permitirá: poner en palabras lo que observan, escuchar otras ideas y preparar insumos para el producto final.",
                *evaluacion_base,
            ],
        )
        cierre = ensure_lines(
            cierre,
            10,
            [
                "Cierre con 2 preguntas: ¿qué aprendimos hoy? ¿qué queremos hacer con lo que descubrimos para el producto final?",
                *evidencia_base,
            ],
        )
    elif mlab == "Planeación":
        inicio = ensure_lines(
            inicio,
            10,
            [
                "Propósito: organizar ideas y ejemplos sobre el tema para explicar con mayor claridad lo que ocurre en su entorno.",
                *preguntas_planeacion,
                "Organización: parejas.",
                contribucion,
            ],
        )
        desarrollo = ensure_lines(
            desarrollo,
            12,
            [
                "Docente: guía para elegir una idea central y organizar sus dibujos o recortes en una hoja con 2 o 3 espacios, donde las niñas y los niños proponen categorías sencillas.",
                "Alumnado: coloca sus ejemplos donde corresponde y dialoga sobre cuál ayuda más a explicar el tema.",
                "Esta actividad permitirá: construir acuerdos con base en evidencias cercanas y preparar el material para el producto final.",
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
                *preguntas_trabajo,
                contribucion,
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
                *preguntas_comunicar,
                contribucion,
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
                *preguntas_reflexion,
                contribucion,
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


def _needs_refinement(activity: dict, *, momento: str = "") -> bool:
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

    ml = _to_text(momento).lower()
    if "punto" in ml or "partida" in ml:
        mlab = "Punto de partida"
    elif "plane" in ml:
        mlab = "Planeación"
    elif "trabaj" in ml:
        mlab = "A trabajar"
    elif "comun" in ml:
        mlab = "Comunicar"
    else:
        mlab = "Reflexión"

    # Repetición típica: observar/registrar/compartir sin cambio cognitivo (sobre todo fuera de Punto de partida).
    body_low = (inicio + "\n" + desarrollo + "\n" + cierre).lower()
    if mlab != "Punto de partida":
        if ("observ" in body_low) and ("registr" in body_low) and ("compart" in body_low):
            return True

    # Requisitos por momento (asegura aumento de complejidad).
    if mlab == "A trabajar":
        must = ("variable", "control", "tabla", "registro")
        if sum(1 for m in must if m in body_low) < 2:
            return True
    if mlab == "Planeación":
        must = ("clasific", "cuadro", "columna", "organiza", "secuencia")
        if sum(1 for m in must if m in body_low) < 2:
            return True
    if mlab == "Comunicar":
        must = ("present", "explic", "públic", "galer", "pregunta", "ensay")
        if sum(1 for m in must if m in body_low) < 2:
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
    dia: int | None = None,
    enfoque_dia: str = "",
    producto_final: str = "",
) -> dict:
    """
    Segundo pase (solo cuando hace falta) para forzar detalle consistente,
    alineado con el Plan de Estudio 2022 (NEM) y con redacción narrativa.
    """
    prompt = f"""
Corrige y mejora la siguiente actividad para que quede MUY detallada, situada en el contexto y coherente con la Nueva Escuela Mexicana, privilegiando la coherencia pedagógica interna.

Tema: {tema}
Grado: {grado}
{f'Día/Sesión: {dia}.' if dia is not None else ''}
Momento metodológico: {momento}
Estrategia pedagógica: {estrategia}
Proyecto educativo (incluye problemática y propósito): {proyecto}
{f'Producto final (debe verse y construirse progresivamente): {producto_final}' if producto_final else ''}
{f'Enfoque sugerido del día (temporalidad): {enfoque_dia}' if enfoque_dia else ''}
Actividades anteriores (evita repetir exactamente): {historial}

Actividad actual (puede estar incompleta): {current}

CRITERIOS PEDAGÓGICOS OBLIGATORIOS (Plan 2022, NEM):
- Enfoque: aprendizaje situado y significativo, vinculado al entorno de las niñas y los niños (hogar, comunidad, clima, costumbres, uso de recursos).
- Lenguaje: usa expresiones como "la docente guía", "las niñas y los niños exploran, comentan, acuerdan", "el grupo dialoga", etc.
- Evita lenguaje conductista (premios, castigos, obediencia ciega) y evita instrucciones mecánicas.
- NO redactes la actividad como lista de "Paso 1, Paso 2, Paso 3". Usa párrafos narrativos que describan la intervención docente y la participación del alumnado.
- Garantiza coherencia con la problemática, el propósito del proyecto y el producto final (la actividad aporta algo visible al producto).

COHERENCIA INTERNA DE LA ACTIVIDAD (OBLIGATORIA):
- Define una sola intención didáctica dominante para esta actividad (por ejemplo: observación, exploración, experimentación, representación o reflexión) y manténla durante todo el INICIO, DESARROLLO y CIERRE.
- Todas las acciones dentro de la actividad deben corresponder al MISMO tipo de experiencia. No mezcles dinámicas incompatibles (por ejemplo: video + recorrido largo + experimento en la misma secuencia).
- Evita arrastrar fragmentos de otras planeaciones: no introduzcas temas ajenos al proyecto actual (como clima, estaciones del año, plantas, etc.) si no forman parte explícita del tema y del proyecto proporcionado.
- Mantén el mismo contexto durante toda la actividad (misma situación, mismo lugar o secuencia lógica), sin cambios bruscos de escenario que confundan.
- La actividad debe poder entenderse de principio a fin como una experiencia completa, lógica y comprensible por sí misma.

NIVEL PREESCOLAR OBLIGATORIO (sin excepción):
- Usa experiencias concretas y cercanas (cuento, conversación, observación breve, juego con objetos, dibujo/recorte para representar).
- Prohibido: mapas, imágenes aéreas, diagramas técnicos o recursos que requieran abstracción de niveles superiores.
- Si el proyecto menciona infraestructura o conceptos técnicos (por ejemplo: “sistema”, “drenaje”, “alcantarillado”), la actividad debe traducirlo a lenguaje cotidiano y accesible (por ejemplo: “lugares por donde corre el agua”).
- Prohibido: lenguaje de “variable/control” o comparaciones con diseño experimental propio de primaria; cuando se hable de experiencias, que sea una exploración sencilla sin controles formales.

REQUISITOS DE FORMATO DE LA ACTIVIDAD:
- NO uses títulos genéricos como "Actividad". Pon un título específico con sentido para el grupo.
- Escribe INICIO/DESARROLLO/CIERRE en formato narrativo: describe qué hace la docente y qué hacen las niñas y los niños, incluye preguntas detonadoras y organización (individual, parejas, equipos, plenaria), e integra tiempos por sección (suma ~40 min).
- Incluye evaluación formativa: qué observar en las niñas y los niños y qué se tomará como evidencia (dibujos, comentarios, registros, acuerdos).
- `materiales` debe ser una lista de recursos realistas, vinculados al contexto (por ejemplo: hojas recicladas, recipientes que las familias puedan llevar, imágenes de la comunidad, etc.).
- `pasos`: lista de 10–14 strings detallados, pero cada elemento puede ser una pequeña escena narrativa (NO digas "Paso 1", "Paso 2" ni uses solo frases telegráficas).

Condiciones por momento (si aplica):
- Si es "A trabajar": incluye indagación o experimentación sencilla con registro (tabla, dibujo comparativo) y conversación sobre lo observado.
- Si es "Planeación": organiza información (clasificar, secuenciar, decidir cómo avanzar hacia el producto final) con justificación basada en lo que han vivido.
- Si es "Comunicar": incluye ensayo, presentación ante grupo o familias, preguntas del público y acuerdos de mejora.
- Si es de cierre/reflexión: propicia que las niñas y los niños hablen de lo que comprendieron y cómo lo relacionan con su vida diaria.

Responde SOLO con un objeto JSON (NO lista, NO texto extra) y SOLO estas claves:
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
    return _ensure_activity_sections(
        normalized,
        tema=str(tema),
        grado=str(grado),
        momento=str(momento),
        dia=dia,
        enfoque_dia=enfoque_dia,
        producto_final=producto_final,
    )


def generar_actividad_ia(tema, grado, momento, estrategia, historial, proyecto, *, dia: int | None = None, total_dias: int | None = None, enfoque_dia: str = ""):
    """
    Genera una actividad individual usando la IA, devolviendo JSON limpio,
    alineada con el Plan de Estudio 2022 (NEM) y con redacción narrativa.
    Protege contra respuestas vacías o con formato incorrecto.
    """
    producto_final_txt = ""
    if isinstance(proyecto, dict):
        producto_final_txt = _to_text(proyecto.get("producto_final"))

    ml = _to_text(momento).lower()
    if "punto" in ml or "partida" in ml:
        demanda = "Diagnóstico y observación (nombrar, describir, explicar con evidencias simples)."
        producto_parcial = "Registro diagnóstico + lista de hallazgos (insumos para el producto final)."
    elif "plane" in ml:
        demanda = "Organización de información (clasificar, secuenciar, justificar con evidencia)."
        producto_parcial = "Organizador gráfico (cuadro/tabla) listo para integrarse al producto final."
    elif "trabaj" in ml:
        demanda = "Indagación/experimento (variable-control, registro en tabla y conclusión)."
        producto_parcial = "Tabla de resultados + conclusión breve para integrar al producto final."
    elif "comun" in ml:
        demanda = "Comunicación (preparar mensaje, ensayar, exponer y responder preguntas)."
        producto_parcial = "Guion breve + presentación/galería con retroalimentación."
    else:
        demanda = "Reflexión y mejora (metacognición, autoevaluación y acuerdos)."
        producto_parcial = "Autoevaluación + lista de mejoras y compromisos."

    prompt = f"""
Eres una docente experta en educación preescolar en México, trabajando con el Plan de Estudio 2022 (Nueva Escuela Mexicana).

Diseña una actividad educativa clara, creativa y MUY detallada, situada en la realidad de las niñas y los niños y coherente con el proyecto, con una intención didáctica única y bien definida.

Tema: {tema}
Grado: {grado}
{f'Día/Sesión: {dia} de {total_dias}.' if (dia is not None and total_dias is not None) else (f'Día/Sesión: {dia}.' if dia is not None else '')}
{f'Enfoque sugerido del día (temporalidad): {enfoque_dia}' if _to_text(enfoque_dia) else ''}

Proyecto educativo (incluye problemática, justificación, propósito y producto final):
{proyecto}
{f'Producto final (debe ser visible y construirse progresivamente): {producto_final_txt}' if producto_final_txt else ''}
Producto parcial esperado hoy (aporte concreto al producto final): {producto_parcial}
Demanda cognitiva (no repetir solo observar/registrar/compartir): {demanda}

Momento metodológico: {momento}
Estrategia pedagógica:
{estrategia}

Actividades anteriores:
{historial}

CRITERIOS PEDAGÓGICOS NEM (OBLIGATORIOS):
- Aprendizaje situado y significativo: vincula la actividad con el entorno inmediato (hogar, comunidad, clima, costumbres, uso de recursos cotidianos).
- Lenguaje pedagógico: usa expresiones como "la docente guía", "las niñas y los niños exploran, dialogan, acuerdan", "el grupo compara y decide", etc.
- Evita redactar la actividad como una lista mecánica de instrucciones. NO uses "Paso 1", "Paso 2", etc.
- Todas las acciones deben guardar coherencia con la problemática, el propósito del proyecto y el producto final (la actividad aporta algo reconocible al producto).

COHERENCIA INTERNA DE LA ACTIVIDAD:
- Define una sola intención didáctica dominante para esta actividad (por ejemplo: observación, exploración, experimentación, representación o reflexión) y manténla durante todo el INICIO, DESARROLLO y CIERRE.
- Todas las acciones dentro de la actividad deben corresponder al MISMO tipo de experiencia. No mezcles en la misma secuencia dinámicas incompatibles (por ejemplo: video + recorrido largo + experimento en agua) si no forman parte de una sola experiencia claramente integrada.
- No arrastres fragmentos de otras planeaciones: no introduzcas temas ajenos al proyecto actual (como clima, estaciones del año, plantas, etc.) si no forman parte explícita del tema y del proyecto proporcionado.
- Mantén el mismo contexto durante toda la actividad (misma situación o secuencia lógica), sin cambios bruscos que confundan.
- La actividad debe poder entenderse de principio a fin como una experiencia completa, lógica y comprensible por sí misma.

NIVEL PREESCOLAR OBLIGATORIO (sin excepción):
- Usa lenguaje sencillo y experiencias concretas (cuento, conversación, observación breve, juego con objetos, dibujo/recorte).
- Prohibido: mapas, imágenes aéreas, conceptos de “sistemas” o infraestructura explicada de manera técnica.
- Si el proyecto menciona infraestructura (p. ej., drenaje/alcantarillado), la actividad debe reexpresarlo en términos cotidianos y accesibles para preescolar.
- Evita “variable/control/mantener igual” y cualquier marco de experimento propio de primaria: la exploración debe ser sencilla y comprensible.

La actividad debe:
- durar aproximadamente 40 minutos
- favorecer la participación activa, el diálogo y la reflexión
- aportar un avance claro hacia el producto final del proyecto

La actividad debe además:
- describir acciones observables del docente y del alumnado en INICIO, DESARROLLO y CIERRE (formato narrativo, no solo frases sueltas)
- incluir preguntas detonadoras y evaluación formativa (qué observar y qué se tomará como evidencia)
- evitar pasos demasiado breves: en cada sección escribe varios renglones con sentido pedagógico

Reglas de formato (muy importante):
- Devuelve SOLO JSON válido (sin texto extra).
- No devuelvas una lista/arreglo: debe ser un objeto JSON (dict) con las claves indicadas.
- En `pasos` NO uses objetos/dicts; SOLO strings. Cada string puede describir una pequeña escena o momento de la actividad (sin numerar Paso 1, Paso 2, etc.).
- En `inicio`/`desarrollo`/`cierre` usa párrafos con saltos de línea cuando haga falta. Describe lo que hace la docente y lo que hacen las niñas y los niños.
- Incluye tiempos sugeridos por sección (ej. \"(5 min)\") sin exceder 40 min en total.
- No uses títulos genéricos como "Actividad". El campo `actividad` debe tener un título significativo que anticipe el sentido de la experiencia.
- Evita repetir las mismas acciones centrales de sesiones anteriores; debe haber aumento de complejidad o profundización.

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
        enriched = _ensure_activity_sections(
            normalized,
            tema=str(tema),
            grado=str(grado),
            momento=str(momento),
            dia=dia,
            enfoque_dia=enfoque_dia,
            producto_final=producto_final_txt,
        )
        if _needs_refinement(enriched, momento=str(momento)):
            enriched = _refine_activity_with_llm(
                tema=str(tema),
                grado=str(grado),
                momento=str(momento),
                estrategia=str(estrategia),
                proyecto=str(proyecto),
                historial=str(historial),
                current=enriched,
                dia=dia,
                enfoque_dia=enfoque_dia,
                producto_final=producto_final_txt,
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
        enriched2 = _ensure_activity_sections(
            normalized2,
            tema=str(tema),
            grado=str(grado),
            momento=str(momento),
            dia=dia,
            enfoque_dia=enfoque_dia,
            producto_final=producto_final_txt,
        )
        if _needs_refinement(enriched2, momento=str(momento)):
            enriched2 = _refine_activity_with_llm(
                tema=str(tema),
                grado=str(grado),
                momento=str(momento),
                estrategia=str(estrategia),
                proyecto=str(proyecto),
                historial=str(historial),
                current=enriched2,
                dia=dia,
                enfoque_dia=enfoque_dia,
                producto_final=producto_final_txt,
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

    total = len(momentos) if isinstance(momentos, list) else None

    for item in momentos:
        dia = item.get("dia") if isinstance(item, dict) else None
        enfoque_dia = _day_focus_from_project(proyecto, int(dia)) if isinstance(dia, int) else ""
        actividad_json = generar_actividad_ia(
            tema,
            grado,
            item["momento"],
            estrategia,
            historial,
            proyecto,
            dia=int(dia) if isinstance(dia, int) else None,
            total_dias=int(total) if isinstance(total, int) else None,
            enfoque_dia=enfoque_dia,
        )

        actividades.append({
            "dia": item["dia"],
            "momento": item["momento"],
            "actividad": actividad_json
        })

        # Mantener historial de actividades para referencia en la IA
        historial += f"\nDia {item['dia']} - {actividad_json.get('actividad', '')}\n"

    return actividades
