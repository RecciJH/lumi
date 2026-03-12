from agents.curriculum_agent import elegir_curriculum
from agents.methodology_agent import dividir_momentos
from agents.activity_agent import generar_actividades
from agents.planning_agent import construir_planeacion
from agents.pedagogy_agent import definir_estrategia_pedagogica
from agents.project_agent import generar_proyecto
from agents.didactic_sequence_agent import generar_secuencia_didactica
from agents.evaluation_agent import generar_evaluacion


def generar_planeacion(data):

    curriculum = elegir_curriculum(data.tema)

    estrategia = definir_estrategia_pedagogica(
        data.tema,
        data.grado,
        data.pda
    )

    proyecto = generar_proyecto(
        data.tema,
        data.grado,
        data.duracion_dias,
    )

    momentos = dividir_momentos(
        data.duracion_dias,
        data.metodologia
    )

    actividades = generar_actividades(
        data.tema,
        data.grado,
        momentos,
        estrategia,
        proyecto
    )

    secuencia = generar_secuencia_didactica(
        data.tema,
        data.grado,
        proyecto,
        actividades
    )

    evaluacion = generar_evaluacion(
        data.tema,
        data.grado,
        curriculum,
        proyecto,
        secuencia,
        actividades,
    )

    planeacion = construir_planeacion(
        data,
        curriculum,
        proyecto,
        evaluacion,
        secuencia,
        actividades
    )

    return planeacion
