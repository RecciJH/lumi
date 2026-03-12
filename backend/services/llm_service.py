import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1"


def generar_respuesta(prompt):

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
            },
            timeout=180,
        )
    except requests.RequestException as exc:
        raise RuntimeError(
            "No se pudo conectar a Ollama en http://localhost:11434. "
            "Verifica que esté corriendo y que el modelo exista."
        ) from exc

    if not response.ok:
        snippet = (response.text or "")[:400].replace("\r", " ").replace("\n", " ").strip()
        raise RuntimeError(f"Ollama respondió {response.status_code}. Respuesta: {snippet!r}")

    try:
        data = response.json()
    except ValueError as exc:
        snippet = (response.text or "")[:400].replace("\r", " ").replace("\n", " ").strip()
        raise RuntimeError(f"La respuesta de Ollama no fue JSON válido: {snippet!r}") from exc

    respuesta = data.get("response")
    if not isinstance(respuesta, str):
        raise RuntimeError("Ollama no devolvió el campo 'response' como texto.")

    return respuesta.strip()
