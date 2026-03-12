from pathlib import Path
from PyPDF2 import PdfReader

path = Path(r"C:\Users\ReneJ\Desktop\planeacion_polinizadores.pdf")
r = PdfReader(str(path))
print(r.pages[1].extract_text())
