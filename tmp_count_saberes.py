from pathlib import Path
import re

text = Path('backend/utils/preescolar/Saberes.txt').read_text(encoding='utf-8')
print('campo count', len(re.findall(r'^CAMPO FORMATIVO:', text, flags=re.M)))
print('contenido count', len(re.findall(r'^Contenido:', text, flags=re.M)))
print('pda marker count', len(re.findall(r"LOS PDA'S de ese contenido:", text)))
