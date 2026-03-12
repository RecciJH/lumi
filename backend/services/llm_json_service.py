import json
import re
from typing import Any


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
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for candidate in _balanced_json_substring(cleaned, "{", "}"):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    for candidate in _balanced_json_substring(cleaned, "[", "]"):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    snippet = cleaned[:400].replace("\r", " ").replace("\n", " ").strip()
    raise ValueError(
        "No se encontró JSON válido en la respuesta del modelo. "
        f"Inicio de respuesta: {snippet!r}"
    )


def parse_llm_json_object(text: str) -> dict:
    parsed = parse_llm_json(text)
    if not isinstance(parsed, dict):
        raise ValueError(f"Se esperaba un objeto JSON, pero llegó: {type(parsed).__name__}.")
    return parsed

