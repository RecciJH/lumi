import json
import sys
from pathlib import Path

sys.path.insert(0, 'backend')
from agents.contenidos_pda_agent import generar_contenidos_pda

master = json.loads(Path('master_sep_like.json').read_text(encoding='utf-8'))
planeacion = master.get('planeacion') or {}
input_data = master.get('input') or {}

tema = input_data.get('tema') or (planeacion.get('datos_generales') or {}).get('tema') or 'La primavera y los seres vivos'
grado = input_data.get('grado') or (planeacion.get('datos_generales') or {}).get('grado') or '3'

campos = ['Lenguajes','Saberes y pensamiento científico','Ética, naturaleza y sociedades','De lo humano y lo comunitario']
planeacion['contenidos_pda'] = generar_contenidos_pda(tema=tema, grado=str(grado), campos_formativos=campos)
master['planeacion'] = planeacion

out = Path('master_utils.json')
out.write_text(json.dumps(master, ensure_ascii=False, indent=2), encoding='utf-8')
print('wrote', out)
