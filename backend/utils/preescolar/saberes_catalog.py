from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class ContentEntry:
    contenido: str
    pdas: list[str]


@dataclass(frozen=True)
class CampoCatalog:
    campo_formativo: str
    contenidos: list[ContentEntry]
    source_path: str


_STOPWORDS = {
    "a",
    "al",
    "ante",
    "bajo",
    "con",
    "contra",
    "de",
    "del",
    "desde",
    "durante",
    "e",
    "el",
    "ella",
    "ellas",
    "ellos",
    "en",
    "entre",
    "es",
    "esa",
    "esas",
    "ese",
    "eso",
    "esos",
    "esta",
    "estas",
    "este",
    "esto",
    "estos",
    "fue",
    "ha",
    "hasta",
    "la",
    "las",
    "le",
    "les",
    "lo",
    "los",
    "mas",
    "más",
    "me",
    "mi",
    "mis",
    "muy",
    "o",
    "para",
    "pero",
    "por",
    "que",
    "qué",
    "se",
    "sin",
    "sobre",
    "su",
    "sus",
    "también",
    "te",
    "tu",
    "tus",
    "un",
    "una",
    "unas",
    "uno",
    "unos",
    "y",
    "ya",
}


def normalize_text(text: str) -> str:
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join([c for c in text if not unicodedata.combining(c)])
    text = re.sub(r"\s+", " ", text)
    return text


def _tokens(text: str) -> set[str]:
    text_n = normalize_text(text)
    raw = re.findall(r"[a-zA-ZáéíóúñüÁÉÍÓÚÑÜ0-9]+", text_n, flags=re.IGNORECASE)
    out = set()
    for w in raw:
        w2 = w.strip().lower()
        if len(w2) < 4:
            continue
        if w2 in _STOPWORDS:
            continue
        out.add(w2)
    return out


def score_relevance(candidate: str, *, context: str) -> float:
    cand_t = _tokens(candidate)
    ctx_t = _tokens(context)
    if not cand_t or not ctx_t:
        return 0.0
    inter = len(cand_t & ctx_t)
    union = len(cand_t | ctx_t)
    return inter / max(1, union)


def parse_campo_catalog(text: str, *, source_path: str) -> CampoCatalog:
    """
    Formato esperado (como en tus .txt):
      CAMPO FORMATIVO: X

      Contenido: ...

      LOS PDA'S de ese contenido:
      1° ...
      2° ...
    """
    campo_match = re.search(r"CAMPO\s+FORMATIVO:\s*(.+)", text, flags=re.IGNORECASE)
    campo = campo_match.group(1).strip() if campo_match else ""

    contenidos: list[ContentEntry] = []
    parts = re.split(r"(?m)^\s*Contenido:\s*", text)
    for part in parts[1:]:
        # termina antes del siguiente "Contenido:" (ya está split) y parsea el bloque PDA.
        # contenido es la primera línea hasta el doble salto o hasta "LOS PDA"
        contenido_text = part.strip()
        if not contenido_text:
            continue

        # separa "LOS PDA..."
        pda_split = re.split(r"LOS\s+PDA'S\s+de\s+ese\s+contenido:\s*", contenido_text, flags=re.IGNORECASE)
        contenido = pda_split[0].strip()
        pdas_block = pda_split[1] if len(pda_split) > 1 else ""
        pdas = []
        for line in pdas_block.splitlines():
            line2 = line.strip().lstrip("-").strip()
            if not line2:
                continue
            pdas.append(line2)

        if contenido:
            contenidos.append(ContentEntry(contenido=contenido, pdas=pdas))

    if not campo:
        # fallback: si no hay header, inferimos por filename.
        campo = Path(source_path).stem

    return CampoCatalog(campo_formativo=campo, contenidos=contenidos, source_path=source_path)


def load_catalog(path: Path) -> CampoCatalog:
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_campo_catalog(text, source_path=str(path))


def load_preescolar_catalogs(base_dir: Path) -> dict[str, CampoCatalog]:
    """
    Carga los 4 catálogos esperados si existen:
      - lenguajes.txt
      - Saberes.txt
      - etica.txt
      - humano.txt
    """
    mapping = {
        "Lenguajes": base_dir / "lenguajes.txt",
        "Saberes y pensamiento científico": base_dir / "Saberes.txt",
        "Ética, naturaleza y sociedades": base_dir / "etica.txt",
        "De lo humano y lo comunitario": base_dir / "humano.txt",
    }
    out: dict[str, CampoCatalog] = {}
    for campo, path in mapping.items():
        if path.exists():
            cat = load_catalog(path)
            # fuerza el nombre "oficial" para el render
            out[normalize_text(campo)] = CampoCatalog(
                campo_formativo=campo,
                contenidos=cat.contenidos,
                source_path=cat.source_path,
            )
    return out


def pick_best_contenido(cat: CampoCatalog, *, context: str) -> Optional[ContentEntry]:
    if not cat.contenidos:
        return None
    scored = [(score_relevance(c.contenido, context=context), c) for c in cat.contenidos]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def pick_best_pda(pdas: Iterable[str], *, context: str, grado: str = "") -> str:
    pdas_list = [p for p in pdas if isinstance(p, str) and p.strip()]
    if not pdas_list:
        return ""
    grado_n = normalize_text(grado)
    grade_hint = ""
    if grado_n.isdigit():
        grade_hint = f"{grado_n}°"

    scored = []
    for p in pdas_list:
        s = score_relevance(p, context=context)
        if grade_hint and grade_hint in normalize_text(p):
            s += 0.15
        scored.append((s, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]

