import sys
from pathlib import Path
from PyPDF2 import PdfReader

sys.stdout.reconfigure(encoding='utf-8')
path = Path(r"C:\Users\ReneJ\Desktop\planeacion_polinizadores.pdf")
r = PdfReader(str(path))
print('--- page 8 ---')
print(r.pages[7].extract_text())
