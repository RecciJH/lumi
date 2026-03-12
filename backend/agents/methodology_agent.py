def dividir_momentos(dias, metodologia):

    momentos = [
        "Punto de partida",
        "Planeación",
        "A trabajar",
        "Comunicar",
        "Reflexión"
    ]

    dias_por_momento = dias // len(momentos)

    resultado = []

    dia_actual = 1

    for momento in momentos:

        for _ in range(dias_por_momento):

            resultado.append({
                "dia": dia_actual,
                "momento": momento
            })

            dia_actual += 1

    return resultado