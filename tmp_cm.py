from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from PyPDF2 import PdfReader
from PyPDF2.generic import IndirectObject

EXAMPLE = Path(r"C:\Users\ReneJ\Desktop\planeacion_polinizadores.pdf")
r = PdfReader(str(EXAMPLE))


def deref(obj):
    if isinstance(obj, IndirectObject):
        return obj.get_object()
    return obj


def page_bytes(i: int) -> bytes:
    p = r.pages[i]
    c = p.get_contents()
    if isinstance(c, list):
        chunks = []
        for cc in c:
            s = deref(cc)
            if s is not None:
                chunks.append(s.get_data())
        return b"".join(chunks)
    if c:
        s = deref(c)
        return s.get_data() if s is not None else b""
    return b""


data = page_bytes(0)

# extract cm operators
cms = re.findall(rb"(-?\d*\.?\d+)\s+(-?\d*\.?\d+)\s+(-?\d*\.?\d+)\s+(-?\d*\.?\d+)\s+(-?\d*\.?\d+)\s+(-?\d*\.?\d+)\s+cm", data)
print("cm count", len(cms))
# keep only scale-like ones (b and c near 0)
scale = []
for a,b,c,d,e,f in cms:
    a=float(a); b=float(b); c=float(c); d=float(d)
    if abs(b) < 1e-6 and abs(c) < 1e-6:
        scale.append((round(a,4), round(d,4)))
print("scale unique (top 20)", Counter(scale).most_common(20))

# show first 15 cm ops
print("first 15 cm:")
for tup in cms[:15]:
    print(tuple(x.decode("ascii") for x in tup))
