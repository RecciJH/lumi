import sys
from pathlib import Path
from PyPDF2 import PdfReader

sys.stdout.reconfigure(encoding='utf-8')
path = Path(r"C:\Users\ReneJ\Desktop\planeacion_polinizadores.pdf")
r = PdfReader(str(path))
print(r.pages[2].extract_text())
