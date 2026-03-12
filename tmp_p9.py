from pathlib import Path
from PyPDF2 import PdfReader

path = Path(r"C:\Users\ReneJ\Desktop\planeacion_polinizadores.pdf")
r = PdfReader(str(path))
for i in [8]:
    p = r.pages[i]
    print('--- page', i+1, '---')
    print(p.extract_text())
