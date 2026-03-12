# Documentacion del proyecto `lumi`

Este repo contiene un backend en Python que expone una API (FastAPI) para **generar una planeacion** a partir de datos de un docente/escuela/tema/metodologia.

Además incluye un flujo "backend puro" (sin Swagger) para generar la planeación en **PDF** usando un coordinador central y un renderer.

Actualmente el repo tiene:

- `backend/`: API + logica de negocio (servicio y "agentes").
- `frontend/`: carpeta vacia (placeholder).

Arbol actual:

```text
lumi/
  backend/
    main.py
    agents/
      activity_agent.py
      coordinador_agent.py
      curriculum_agent.py
      didactic_sequence_agent.py
      evaluation_agent.py
      methodology_agent.py
      pedagogy_agent.py
      planning_agent.py
      project_agent.py
    data/
      campos_formativos.json
      metodologias.json
    models/
      planeacion_request.py
    renderers/
      pdf_renderer.py
    scripts/
      generar_planeacion_pdf.py
    services/
      planeacion_service.py
      llm_service.py
      llm_json_service.py
  frontend/
```

## Generar PDF sin Swagger (recomendado para producción)

1) Crea un archivo `input.json` con un objeto JSON (dict) con lo mínimo recomendado:

```json
{
  "docente": "Nombre Docente",
  "escuela": "Escuela",
  "grado": "3",
  "grupo": "A",
  "tema": "Mi tema",
  "pda": "PDA",
  "duracion_dias": 5,
  "metodologia": "ABP"
}
```

2) Ejecuta el script desde la raíz del repo:

```powershell
python backend/scripts/generar_planeacion_pdf.py --input input.json --out planeacion.pdf
```

Opcional (para depuración):

```powershell
python backend/scripts/generar_planeacion_pdf.py --input input.json --out planeacion.pdf --out-master master.json --include-raw-json --log-level DEBUG
```

Opcional (incluir evaluación/rúbrica; puede tardar más):

```powershell
python backend/scripts/generar_planeacion_pdf.py --input input.json --out planeacion.pdf --include-evaluacion
```

## Mapa de carpetas y archivos

### `backend/main.py`

**Rol:** punto de entrada de la API.

- Crea `app = FastAPI()`.
- Define un endpoint `POST /generar-planeacion`.
- Valida el cuerpo de la solicitud con `PlaneacionRequest` (Pydantic).
- Llama a `services.planeacion_service.generar_planeacion(data)` y devuelve su resultado tal cual.

**Endpoint**

- Ruta: `POST /generar-planeacion`
- Entrada: JSON compatible con `PlaneacionRequest`
- Salida: JSON con la planeacion generada (ver "Estructura de respuesta").

### `backend/models/planeacion_request.py`

**Rol:** modelo de entrada (request) del endpoint.

Define `PlaneacionRequest(BaseModel)` con estos campos:

- `docente: str`: nombre del docente.
- `escuela: str`: nombre de la escuela.
- `cct: str`: clave del centro de trabajo (o identificador equivalente).
- `grado: str`: grado escolar.
- `grupo: str`: grupo (por ejemplo "A", "B", etc.).
- `tema: str`: tema central de la planeacion.
- `duracion_dias: int`: duracion total en dias para repartir actividades.
- `metodologia: str`: nombre/clave de la metodologia (por ahora se pasa, pero no afecta el calculo de momentos).

### `backend/services/planeacion_service.py`

**Rol:** orquestador del flujo (logica de negocio principal).

Funcion principal: `generar_planeacion(data)`.

Flujo interno:

1. `curriculum = elegir_curriculum(data.tema)`:
   - Resuelve un "curriculum" (campo formativo, eje, pda) con heuristicas simples.
2. `momentos = dividir_momentos(data.duracion_dias, data.metodologia)`:
   - Parte la duracion en momentos metodologicos y asigna numeros de dia.
3. `actividades = generar_actividades(data.tema, data.grado, momentos)`:
   - Genera el texto de actividades, 1 por cada elemento de `momentos`.
4. `planeacion = construir_planeacion(data, curriculum, momentos, actividades)`:
   - Arma el objeto final que se devuelve al cliente.

### `backend/agents/` (agentes)

Los "agentes" son funciones que encapsulan decisiones o transformaciones especificas del proceso.

#### `backend/agents/curriculum_agent.py`

Funcion: `elegir_curriculum(tema)`.

**Que hace:**

- Normaliza `tema` a minusculas y busca palabras clave.
- Si `tema` contiene `"naturaleza"` o `"primavera"`, devuelve:
  - `campo_formativo = "Ã‰tica, naturaleza y sociedades"`
  - `eje = "Vida saludable"`
  - `pda = "Convive con su entorno natural"`
- En caso contrario, devuelve un fallback:
  - `campo_formativo = "Lenguajes"`
  - `eje = "Pensamiento crÃ­tico"`
  - `pda = "Expresa ideas mediante lenguaje"`

**Salida:** un `dict` con `campo_formativo`, `eje`, `pda`.

#### `backend/agents/methodology_agent.py`

Funcion: `dividir_momentos(dias, metodologia)`.

**Que hace:**

- Define 5 momentos fijos (en este orden):
  - `"Punto de partida"`, `"PlaneaciÃ³n"`, `"A trabajar"`, `"Comunicar"`, `"ReflexiÃ³n"`.
- Calcula `dias_por_momento = dias // 5` (division entera).
- Genera una lista `resultado` con elementos:
  - `{"dia": <numero>, "momento": <nombre>}`
  - Asigna dias consecutivos empezando en 1.
  - Repite cada `momento` `dias_por_momento` veces.

**Notas importantes (comportamiento actual):**

- Si `dias` no es multiplo de 5, los dias sobrantes se pierden (no se asignan).
- El parametro `metodologia` se recibe pero no se usa aun.

**Salida:** lista de `dict` con `dia` y `momento`.

#### `backend/agents/activity_agent.py`

Funcion: `generar_actividades(tema, grado, momentos)`.

**Que hace:**

- Recorre la lista `momentos` (cada item debe traer `dia` y `momento`).
- Lleva un contador por `momento` para saber si es la 1ra, 2da, 3ra vez que aparece ese momento.
- Para cada `momento` elige una actividad de una lista de 3 opciones.
  - La seleccion rota con: `opciones[(paso - 1) % len(opciones)]`.
  - Ejemplo: para la 1ra ocurrencia usa opcion 1, para la 2da opcion 2, etc.
- Devuelve una lista de actividades con estructura:
  - `{"dia": <numero>, "momento": <nombre>, "actividad": <texto>}`

**Notas importantes (comportamiento actual):**

- El parametro `grado` se recibe pero no se usa para variar las actividades.
- El archivo contiene textos con acentos que actualmente aparecen "mojibake" (por ejemplo `PlaneaciÃ³n`), lo que sugiere un tema de codificacion (UTF-8 vs ANSI/Windows-1252).

#### `backend/agents/planning_agent.py`

Funcion: `construir_planeacion(data, curriculum, momentos, actividades)`.

**Que hace:**

- Arma el `dict` final que la API devuelve.
- Incluye:
  - Datos del request: `docente`, `escuela`, `tema`.
  - Datos del "curriculum": `campo_formativo`, `eje`, `pda`.
  - Lista de `actividades`.

**Nota:** hoy no incluye `cct`, `grado`, `grupo`, `duracion_dias` ni `metodologia` en la respuesta (aunque vienen en el request).

### `backend/data/`

Actualmente contiene placeholders (archivos vacios):

- `backend/data/campos_formativos.json`
- `backend/data/metodologias.json`

Intencion probable: mover ahi catalogos/parametros para que `elegir_curriculum()` y/o `dividir_momentos()` sean data-driven en vez de heuristicas hardcodeadas.

## Contratos JSON (lo que entra y sale)

### Request (entrada)

Ejemplo de payload valido para `POST /generar-planeacion`:

```json
{
  "docente": "Maria Perez",
  "escuela": "Primaria Benito Juarez",
  "cct": "00ABC1234Z",
  "grado": "3",
  "grupo": "A",
  "tema": "La naturaleza en primavera",
  "duracion_dias": 10,
  "metodologia": "proyectos"
}
```

### Response (salida)

Estructura actual de respuesta:

```json
{
  "docente": "string",
  "escuela": "string",
  "tema": "string",
  "campo_formativo": "string",
  "eje": "string",
  "pda": "string",
  "actividades": [
    {
      "dia": 1,
      "momento": "Punto de partida",
      "actividad": "..."
    }
  ]
}
```

## Como correr (local)

Este repo no incluye `requirements.txt`/`pyproject.toml` por ahora, pero el codigo importa `fastapi` y `pydantic`.

Si ya tienes el entorno con dependencias instaladas, una forma comun de correrlo es:

1. Desde `backend/`:
   - `uvicorn main:app --reload`

Nota: `backend/main.py` usa imports como `from models...` y `from services...`, por lo que normalmente se ejecuta con el directorio `backend/` en el `PYTHONPATH` (por ejemplo, corriendo uvicorn dentro de `backend/`).

## Resumen del flujo end-to-end

1. Cliente hace `POST /generar-planeacion` con `PlaneacionRequest`.
2. `backend/main.py` valida y manda a `generar_planeacion`.
3. `generar_planeacion`:
   - Elige curriculum (por tema),
   - Divide momentos (por dias),
   - Genera actividades (por momento),
   - Construye y devuelve la planeacion.
