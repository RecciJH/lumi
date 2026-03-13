import json
import re
from typing import Any


def _escape_newlines_in_json_strings(text: str) -> str:
    """
    Convierte saltos de lÃ­nea literales dentro de strings JSON en \\n para tolerar
    salidas "casi JSON" del modelo.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            out.append(ch)
            in_string = not in_string
            continue
        if in_string and ch in ("\n", "\r"):
            out.append("\\n")
            continue
        out.append(ch)
    return "".join(out)


def _try_json_loads(text: str) -> Any:
    # Reparaciones conservadoras para salidas comunes del modelo.
    variants = [
        text,
        text.replace("\u201c", '"').replace("\u201d", '"'),
    ]

    last_exc: Exception | None = None
    for s in variants:
        # trailing commas
        s2 = re.sub(r",\s*([}\]])", r"\1", s)
        # newlines inside strings
        s2 = _escape_newlines_in_json_strings(s2)
        try:
            return json.loads(s2)
        except json.JSONDecodeError as e:
            last_exc = e

    raise last_exc or json.JSONDecodeError("Invalid JSON", text, 0)


def _strip_code_fences(text: str) -> str:
    text = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _balanced_json_substring(text: str, open_ch: str, close_ch: str) -> list[str]:
    candidates: list[str] = []
    starts = [i for i, ch in enumerate(text) if ch == open_ch]
    for start in starts:
        depth = 0
        for end in range(start, len(text)):
            ch = text[end]
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : end + 1])
                    break
    return candidates


def parse_llm_json(text: str) -> Any:
    if text is None or str(text).strip() == "":
        raise ValueError("El modelo devolvió una respuesta vacía.")

    cleaned = _strip_code_fences(str(text))

    try:
        return _try_json_loads(cleaned)
    except json.JSONDecodeError:
        pass

    for candidate in _balanced_json_substring(cleaned, "{", "}"):
        try:
            return _try_json_loads(candidate)
        except json.JSONDecodeError:
            continue

    for candidate in _balanced_json_substring(cleaned, "[", "]"):
        try:
            return _try_json_loads(candidate)
        except json.JSONDecodeError:
            continue

    snippet = cleaned[:400].replace("\r", " ").replace("\n", " ").strip()
    raise ValueError(
        "No se encontró JSON válido en la respuesta del modelo. "
        f"Inicio de respuesta: {snippet!r}"
    )


def parse_llm_json_object(text: str) -> dict:
    parsed = parse_llm_json(text)
    # A veces el modelo devuelve una lista con un solo objeto.
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, dict):
                return item
    if not isinstance(parsed, dict):
        raise ValueError(f"Se esperaba un objeto JSON, pero llegó: {type(parsed).__name__}.")
    return parsed
