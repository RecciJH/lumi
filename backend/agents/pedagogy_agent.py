def definir_estrategia_pedagogica(tema, grado, pda):
    tema_lower = tema.lower()
    
    if "animales" in tema_lower or "naturaleza" in tema_lower:
        enfoque = "exploración y descubrimiento del entorno"
    elif "lenguaje" in tema_lower or "lectura" in tema_lower:
        enfoque = "juegos de comunicación y narración de historias"
    elif "matemática" in tema_lower or "números" in tema_lower:
        enfoque = "resolución de problemas y actividades manipulativas"
    else:
        enfoque = "aprendizaje basado en proyectos"
    
    estrategia = {
        "enfoque": enfoque,
        "objetivo_general": f"Que los estudiantes comprendan el tema {tema} mediante exploración, investigación y creación.",
        "habilidades": [
            "observación",
            "investigación",
            "expresión oral",
            "creatividad",
            "reflexión"
        ],
        "progresion": [
            "explorar conocimientos previos",
            "observar y analizar",
            "investigar",
            "crear productos",
            "comunicar aprendizajes",
            "reflexionar"
        ]
    }

    return estrategia