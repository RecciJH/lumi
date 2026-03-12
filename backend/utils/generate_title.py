
import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

async def generate_chat_title(message: str) -> str:
    prompt = f"""
    Genera un TÍTULO muy corto (máximo 7 palabras) que describa este mensaje de chat.

    Mensaje: "{message}"

    Reglas:
    - No uses comillas.
    - Hazlo profesional.
    - No uses palabras genéricas como "Chat" o "Conversación".
    - Enfócate en el tema principal del mensaje.
    """

    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",  # rápido y barato
        max_tokens=20,
        temperature=0.2
    )

    title = chat_completion.choices[0].message.content.strip()
    return title
