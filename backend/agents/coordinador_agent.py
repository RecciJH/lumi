"""
coordinador_agent.py

Director central de Lumi: coordina múltiples agentes para generar una planeación completa
en un formato unificado (JSON maestro). Está diseñado para ser modular y escalable:
agregar un agente nuevo normalmente implica registrar un nuevo `PipelineStep`.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from agents.activity_agent import generar_actividades
from agents.curriculum_agent import elegir_curriculum
from agents.didactic_sequence_agent import generar_secuencia_didactica
from agents.evaluation_agent import generar_evaluacion
from agents.methodology_agent import dividir_momentos
from agents.pedagogy_agent import definir_estrategia_pedagogica
from agents.planning_agent import construir_planeacion
from agents.project_agent import generar_proyecto

logger = logging.getLogger("lumi.coordinador")


class AgentExecutionError(RuntimeError):
    """Error claro cuando un paso/agent no logra ejecutarse después de reintentos."""

    def __init__(self, step_name: str, input_snapshot: dict, last_error: Exception):
        self.step_name = step_name
        self.input_snapshot = input_snapshot
        self.last_error = last_error
        super().__init__(
            f"Falló el agente/paso '{step_name}' después de reintentos. "
            f"Error: {type(last_error).__name__}: {last_error}"
        )


Validator = Callable[[Any], Any]
StepFn = Callable[[dict], Any]


@dataclass(frozen=True)
class PipelineStep:
    """
    Un paso del pipeline.

    - `name`: nombre legible para logs/metadatos.
    - `output_key`: llave donde se guardará el resultado en el estado.
    - `requires`: llaves mínimas que deben existir en el estado para poder ejecutar.
    - `fn`: función que recibe el estado completo y produce el resultado.
    - `validator`: normaliza/valida el resultado antes de guardarlo.
    - `skip_if_present`: si True y `output_key` ya existe, se omite el paso.
    """

    name: str
    output_key: str
    requires: Tuple[str, ...]
    fn: StepFn
    validator: Validator
    skip_if_present: bool = True


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dict(value: Any, *, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"Se esperaba dict para '{name}', pero llegó: {type(value).__name__}")
    return value


def _ensure_list(value: Any, *, name: str) -> list:
    if not isinstance(value, list):
        raise ValueError(f"Se esperaba list para '{name}', pero llegó: {type(value).__name__}")
    return value


def _validate_curriculum(value: Any) -> dict:
    data = _ensure_dict(value, name="curriculum")
    for k in ("campo_formativo", "eje", "pda"):
        data.setdefault(k, "")
    return data


def _validate_estrategia(value: Any) -> dict:
    return _ensure_dict(value, name="estrategia_pedagogica")


def _validate_proyecto(value: Any) -> dict:
    data = _ensure_dict(value, name="proyecto")
    for k in (
        "nombre_proyecto",
        "problematica",
        "justificacion",
        "proposito",
        "producto_final",
        "temporalidad",
    ):
        data.setdefault(k, "")
    return data


def _validate_momentos(value: Any) -> list[dict]:
    momentos = _ensure_list(value, name="momentos")
    out: list[dict] = []
    for item in momentos:
        if not isinstance(item, dict):
            continue
        if "dia" not in item or "momento" not in item:
            continue
        out.append({"dia": int(item["dia"]), "momento": str(item["momento"])})
    if not out:
        raise ValueError("La lista de 'momentos' llegó vacía o inválida.")
    return out


def _validate_actividades(value: Any) -> list[dict]:
    actividades = _ensure_list(value, name="actividades")
    out: list[dict] = []
    for item in actividades:
        if not isinstance(item, dict):
            continue
        out.append(item)
    if not out:
        raise ValueError("La lista de 'actividades' llegó vacía o inválida.")
    return out


def _validate_secuencia(value: Any) -> dict:
    data = _ensure_dict(value, name="secuencia_didactica")
    for k in ("inicio", "desarrollo", "cierre", "evaluacion"):
        data.setdefault(k, "")
    data.setdefault("evidencias", [])
    data.setdefault("materiales", [])
    if not isinstance(data["evidencias"], list):
        data["evidencias"] = []
    if not isinstance(data["materiales"], list):
        data["materiales"] = []
    return data


def _validate_evaluacion(value: Any) -> dict:
    data = _ensure_dict(value, name="evaluacion")
    data.setdefault("instrumento", "rubrica")
    data.setdefault("criterios", [])
    data.setdefault("indicadores", [])
    if not isinstance(data["criterios"], list):
        raise ValueError("La evaluación no trae 'criterios' como lista.")
    return data


def _validate_planeacion(value: Any) -> dict:
    return _ensure_dict(value, name="planeacion")


def _step_curriculum(state: dict) -> dict:
    return elegir_curriculum(state["tema"])


def _step_estrategia(state: dict) -> dict:
    pda = state.get("pda") or (state.get("curriculum") or {}).get("pda") or ""
    return definir_estrategia_pedagogica(state["tema"], state["grado"], pda)


def _step_proyecto(state: dict) -> dict:
    duracion = state.get("duracion_dias")
    return generar_proyecto(state["tema"], state["grado"], int(duracion) if duracion is not None else None)


def _step_momentos(state: dict) -> list[dict]:
    return dividir_momentos(int(state["duracion_dias"]), state["metodologia"])


def _step_actividades(state: dict) -> list[dict]:
    return generar_actividades(
        state["tema"],
        state["grado"],
        state["momentos"],
        state["estrategia_pedagogica"],
        state["proyecto"],
    )


def _step_secuencia(state: dict) -> dict:
    return generar_secuencia_didactica(
        state["tema"],
        state["grado"],
        state["proyecto"],
        state["actividades"],
    )


def _step_evaluacion(state: dict) -> dict:
    return generar_evaluacion(
        state["tema"],
        state["grado"],
        state["curriculum"],
        state["proyecto"],
        state["secuencia_didactica"],
        state["actividades"],
    )


def _step_planeacion(state: dict) -> dict:
    # `construir_planeacion` espera un objeto `data`; aquí aceptamos dict.
    class _DataShim:
        def __init__(self, d: dict):
            self.__dict__.update(d)

    data = _DataShim(state)
    return construir_planeacion(
        data,
        state["curriculum"],
        state["proyecto"],
        state["evaluacion"],
        state["secuencia_didactica"],
        state["actividades"],
    )


DEFAULT_PIPELINE: Tuple[PipelineStep, ...] = (
    PipelineStep(
        name="curriculum_agent",
        output_key="curriculum",
        requires=("tema",),
        fn=_step_curriculum,
        validator=_validate_curriculum,
    ),
    PipelineStep(
        name="pedagogy_agent",
        output_key="estrategia_pedagogica",
        requires=("tema", "grado"),
        fn=_step_estrategia,
        validator=_validate_estrategia,
    ),
    PipelineStep(
        name="project_agent",
        output_key="proyecto",
        requires=("tema", "grado"),
        fn=_step_proyecto,
        validator=_validate_proyecto,
    ),
    PipelineStep(
        name="methodology_agent",
        output_key="momentos",
        requires=("duracion_dias", "metodologia"),
        fn=_step_momentos,
        validator=_validate_momentos,
    ),
    PipelineStep(
        name="activity_agent",
        output_key="actividades",
        requires=("tema", "grado", "momentos", "estrategia_pedagogica", "proyecto"),
        fn=_step_actividades,
        validator=_validate_actividades,
    ),
    PipelineStep(
        name="didactic_sequence_agent",
        output_key="secuencia_didactica",
        requires=("tema", "grado", "proyecto", "actividades"),
        fn=_step_secuencia,
        validator=_validate_secuencia,
    ),
    PipelineStep(
        name="evaluation_agent",
        output_key="evaluacion",
        requires=("tema", "grado", "curriculum", "proyecto", "secuencia_didactica", "actividades"),
        fn=_step_evaluacion,
        validator=_validate_evaluacion,
    ),
    PipelineStep(
        name="planning_agent",
        output_key="planeacion",
        requires=("curriculum", "proyecto", "evaluacion", "secuencia_didactica", "actividades"),
        fn=_step_planeacion,
        validator=_validate_planeacion,
        skip_if_present=False,
    ),
)


def _run_step_with_retries(
    step: PipelineStep,
    state: dict,
    *,
    max_retries: int = 2,
) -> Tuple[Any, dict]:
    """
    Ejecuta un paso con reintentos.
    - `max_retries=2` => 1 intento inicial + 2 reintentos = 3 intentos total.
    Retorna (resultado_validado, metadata_del_paso).
    """
    attempts_total = 1 + max_retries
    last_exc: Optional[Exception] = None
    t0 = time.perf_counter()

    for attempt in range(1, attempts_total + 1):
        try:
            logger.info("Paso %s (intento %s/%s) iniciando", step.name, attempt, attempts_total)
            raw = step.fn(state)
            validated = step.validator(raw)
            dt_ms = int((time.perf_counter() - t0) * 1000)
            meta = {
                "name": step.name,
                "output_key": step.output_key,
                "status": "ok",
                "attempts": attempt,
                "duration_ms": dt_ms,
            }
            return validated, meta
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.exception("Paso %s falló en intento %s/%s", step.name, attempt, attempts_total)
            if attempt >= attempts_total:
                break

    dt_ms = int((time.perf_counter() - t0) * 1000)
    meta = {
        "name": step.name,
        "output_key": step.output_key,
        "status": "error",
        "attempts": attempts_total,
        "duration_ms": dt_ms,
        "error": f"{type(last_exc).__name__}: {last_exc}" if last_exc else "Unknown error",
    }
    raise AgentExecutionError(step.name, input_snapshot=dict(state), last_error=last_exc or RuntimeError("Unknown"))


def generar_planeacion_maestra(
    planeacion_input: Dict[str, Any],
    *,
    pipeline: Iterable[PipelineStep] = DEFAULT_PIPELINE,
    max_retries: int = 2,
) -> Dict[str, Any]:
    """
    Ejecuta el pipeline de Lumi y devuelve un JSON maestro con:
    - input original
    - resultados por agente/paso
    - planeación final unificada
    - metadatos de ejecución

    Args:
        planeacion_input: dict con cualquier dato disponible (tema, grado, pda, duracion_dias, etc.)
        pipeline: pasos a ejecutar (modificable para agregar/quitar agentes)
        max_retries: reintentos por paso (2 => hasta 3 intentos total)
    """
    if not isinstance(planeacion_input, dict):
        raise ValueError("planeacion_input debe ser un dict.")

    state: dict = dict(planeacion_input)
    step_metas: list[dict] = []
    results_by_step: dict = {}

    started_at = _utc_iso()
    logger.info("Coordinación iniciada: %s", started_at)

    for step in pipeline:
        missing = [k for k in step.requires if k not in state or state[k] in (None, "")]
        if missing:
            logger.info("Omitiendo %s: faltan llaves requeridas: %s", step.name, missing)
            step_metas.append(
                {
                    "name": step.name,
                    "output_key": step.output_key,
                    "status": "skipped",
                    "missing_keys": missing,
                }
            )
            continue

        if step.skip_if_present and step.output_key in state and state[step.output_key] not in (None, ""):
            logger.info("Omitiendo %s: '%s' ya existe en el estado", step.name, step.output_key)
            step_metas.append(
                {
                    "name": step.name,
                    "output_key": step.output_key,
                    "status": "skipped",
                    "reason": "already_present",
                }
            )
            continue

        result, meta = _run_step_with_retries(step, state, max_retries=max_retries)
        state[step.output_key] = result
        results_by_step[step.output_key] = result
        step_metas.append(meta)

    finished_at = _utc_iso()
    master = {
        "meta": {
            "started_at": started_at,
            "finished_at": finished_at,
            "pipeline_steps": step_metas,
            "version": "coordinador_agent_v1",
        },
        "input": planeacion_input,
        "results": results_by_step,
        "planeacion": state.get("planeacion") or results_by_step.get("planeacion") or {},
    }

    return master


def exportar_planeacion_a_pdf_placeholder(master_json: Dict[str, Any], output_path: str) -> str:
    """
    Placeholder para exportación a PDF "bonito".

    Implementación actual:
    - Genera un PDF mínimo (válido) con texto simple, sin dependencias externas.
    - Sirve como punto de reemplazo futuro por una versión con plantillas/estilos.
    """
    if not isinstance(master_json, dict):
        raise ValueError("master_json debe ser dict.")
    if not output_path.lower().endswith(".pdf"):
        raise ValueError("output_path debe terminar en .pdf")

    title = "Lumi - Planeación"
    planeacion = master_json.get("planeacion") or {}
    tema = str(planeacion.get("datos_generales", {}).get("tema", master_json.get("input", {}).get("tema", "")))
    grado = str(planeacion.get("datos_generales", {}).get("grado", master_json.get("input", {}).get("grado", "")))

    lines: List[str] = [
        title,
        "",
        f"Tema: {tema}",
        f"Grado: {grado}",
        "",
        "Este PDF es un placeholder (texto simple).",
        "Reemplazar por una plantilla con diseño posteriormente.",
        "",
        "Resumen (JSON maestro):",
        json.dumps(master_json, ensure_ascii=False, indent=2)[:4000],
    ]

    _write_minimal_pdf("\n".join(lines), output_path)
    return output_path


def _write_minimal_pdf(text: str, output_path: str) -> None:
    """
    Escribe un PDF mínimo con texto monoespaciado.
    No usa librerías externas (reportlab, etc.).
    """

    # Sanitizar caracteres que rompen el stream PDF básico
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    safe = safe.replace("\r\n", "\n").replace("\r", "\n")

    # Construcción simple de PDF (1 página, fuente base Courier).
    # Referencia: estructura mínima PDF 1.4 con un Content Stream.
    content_lines = []
    y = 760
    for line in safe.split("\n"):
        content_lines.append(f"72 {y} Td ({line[:120]}) Tj")
        content_lines.append("T*")
        y -= 12
        if y < 72:
            break

    content_stream = "BT /F1 10 Tf 0 0 0 rg\n" + "\n".join(content_lines) + "\nET"
    content_bytes = content_stream.encode("utf-8")

    objects: List[bytes] = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources<< /Font<< /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n"
    )
    objects.append(b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>endobj\n")
    objects.append(
        b"5 0 obj<< /Length "
        + str(len(content_bytes)).encode("ascii")
        + b" >>stream\n"
        + content_bytes
        + b"\nendstream\nendobj\n"
    )

    header = b"%PDF-1.4\n"
    xref_offsets: List[int] = [0]
    body = b""
    offset = len(header)
    for obj in objects:
        xref_offsets.append(offset)
        body += obj
        offset += len(obj)

    xref_start = len(header) + len(body)
    xref = [b"xref\n0 6\n", b"0000000000 65535 f \n"]
    for off in xref_offsets[1:]:
        xref.append(f"{off:010d} 00000 n \n".encode("ascii"))

    trailer = (
        b"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n"
        + str(xref_start).encode("ascii")
        + b"\n%%EOF\n"
    )

    pdf_bytes = header + body + b"".join(xref) + trailer
    with open(output_path, "wb") as f:
        f.write(pdf_bytes)
