def construir_planeacion(data, curriculum, proyecto, evaluacion, secuencia, actividades):

    return {
        "datos_generales": {
            "docente": data.docente,
            "escuela": data.escuela,
            "grado": data.grado,
            "grupo": data.grupo,
            "tema": data.tema
        },

        "curriculum": {
            "campo_formativo": curriculum["campo_formativo"],
            "eje": curriculum["eje"],
            "pda": curriculum["pda"]
        },

        "proyecto": proyecto,

        "evaluacion": evaluacion,

        "secuencia_didactica": secuencia,

        "actividades": actividades
    }
