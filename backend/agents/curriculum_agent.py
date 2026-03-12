def elegir_curriculum(tema):

    if "naturaleza" in tema.lower() or "primavera" in tema.lower():
        return {
            "campo_formativo": "Ética, naturaleza y sociedades",
            "eje": "Vida saludable",
            "pda": "Convive con su entorno natural"
        }

    return {
        "campo_formativo": "Lenguajes",
        "eje": "Pensamiento crítico",
        "pda": "Expresa ideas mediante lenguaje"
    }