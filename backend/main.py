from fastapi import FastAPI, HTTPException
import logging
from models.planeacion_request import PlaneacionRequest
from services.planeacion_service import generar_planeacion

app = FastAPI()
logger = logging.getLogger(__name__)

@app.post("/generar-planeacion")
def crear_planeacion(data: PlaneacionRequest):
    try:
        return generar_planeacion(data)
    except (ValueError, RuntimeError) as exc:
        logger.exception("Error generando planeación")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
