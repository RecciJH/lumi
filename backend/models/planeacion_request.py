from pydantic import BaseModel

class PlaneacionRequest(BaseModel):
    docente: str
    escuela: str
    grado: str
    grupo: str
    cct: str
    tema: str
    campo_formativo: str
    eje: str
    pda: str
    duracion_dias: int
    metodologia: str