from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from PyPDF2 import PdfReader
from PyPDF2.generic import IndirectObject

sys.stdout.reconfigure(encoding="utf-8")

EXAMPLE = Path(r"C:\Users\ReneJ\Desktop\planeacion_polinizadores.pdf")

r = PdfReader(str(EXAMPLE))
print("pages", len(r.pages))


def deref(obj):
    if isinstance(obj, IndirectObject):
        return obj.get_object()
    return obj


def page_content_bytes(page):
    c = page.get_contents()
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


def xobject_info(page):
    res = deref(page.get("/Resources")) or {}
    xobj = deref(res.get("/XObject"))
    if not xobj:
        return (0, 0, 0)
    total = images = forms = 0
    for _, v in xobj.items():
        o = deref(v)
        total += 1
        subtype = o.get("/Subtype")
        if subtype == "/Image":
            images += 1
        elif subtype == "/Form":
            forms += 1
    return (total, images, forms)


for i in range(len(r.pages)):
    p = r.pages[i]
    text = (p.extract_text() or "").strip()
    first_line = text.splitlines()[0] if text else ""

    data = page_content_bytes(p)
    sizes = [float(s) for s in re.findall(rb"(\d+(?:\.\d+)?)\s+Tf", data)]
    ws = [float(s) for s in re.findall(rb"(\d+(?:\.\d+)?)\s+w", data)]
    rects = len(re.findall(rb"\bre\b", data))
    (x_total, x_images, x_forms) = xobject_info(p)

    safe_first = first_line.encode("utf-8", "backslashreplace").decode("utf-8")

    print(f"\n--- page {i+1} ---")
    print("first line:", safe_first[:120])
    print("text chars:", len(text), "content bytes:", len(data))
    print("Tf unique:", sorted(set(sizes))[:20], "most common:", Counter(sizes).most_common(3))
    print("w unique:", sorted(set(ws))[:10], "rect ops:", rects)
    print("xobjects:", x_total, "images:", x_images, "forms:", x_forms)
