"""
remote_assets.py

Descarga opcional de imágenes desde internet para enriquecer el PDF (portada, etc.).

Importante:
- NO se recomienda 'scrapear' Google Images (TOS/copyright).
- Este módulo usa Wikimedia Commons (MediaWiki API) porque ofrece metadatos de licencia y atribución.
- Siempre guarda metadatos de atribución para incluirlos en el PDF.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PIL import Image


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
DEFAULT_USER_AGENT = "Lumi/1.0 (educational planning generator; contact: not-provided)"

# Licencias típicamente aceptables para uso con atribución.
ALLOWED_LICENSE_SNIPPETS = (
    "CC0",
    "Public domain",
    "CC BY",
    "CC-BY",
    "CC BY-SA",
    "CC-BY-SA",
)


@dataclass
class RemoteAsset:
    source: str
    query: str
    file_url: str
    page_url: str
    title: str = ""
    license: str = ""
    license_url: str = ""
    attribution: str = ""
    artist: str = ""
    credit: str = ""
    downloaded_path: str = ""

    def to_meta(self) -> dict:
        d = asdict(self)
        return d


def get_default_cache_dir() -> Path:
    """
    Cache fuera del repo para no ensuciar git: ~/.lumi/cache/assets (override con env).
    """
    override = os.environ.get("LUMI_ASSET_CACHE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path.home() / ".lumi" / "cache" / "assets").resolve()


def _get_headers() -> dict:
    """
    Wikimedia APIs expect a descriptive User-Agent. Many services will throttle/block
    generic python-requests UAs.
    """
    ua = os.environ.get("LUMI_HTTP_USER_AGENT", "").strip() or os.environ.get("LUMI_USER_AGENT", "").strip()
    return {
        "User-Agent": ua or DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }


def _is_license_allowed(license_text: str) -> bool:
    if not license_text:
        return False
    return any(snippet.lower() in license_text.lower() for snippet in ALLOWED_LICENSE_SNIPPETS)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean_ext(url: str) -> str:
    u = url.lower().split("?")[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if u.endswith(ext):
            return ext.replace(".jpeg", ".jpg")
    return ".jpg"


def search_commons_images(query: str, *, limit: int = 8, timeout_s: int = 20) -> List[RemoteAsset]:
    """
    Busca imágenes en Wikimedia Commons y regresa candidatos con metadatos.
    """
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": str(limit),
        "gsrnamespace": "6",  # File:
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": "1600",
    }

    r = requests.get(COMMONS_API, params=params, timeout=timeout_s, headers=_get_headers())
    if r.status_code == 403:
        raise ValueError(
            "Wikimedia Commons respondió 403 (Forbidden). "
            "Suele resolverse definiendo un User-Agent descriptivo en LUMI_HTTP_USER_AGENT, "
            "o puede ser un bloqueo de red/proxy."
        )
    r.raise_for_status()
    data = r.json()

    pages = (((data or {}).get("query") or {}).get("pages") or {}).values()
    out: List[RemoteAsset] = []

    for p in pages:
        title = str(p.get("title") or "")
        imageinfo = (p.get("imageinfo") or [])
        if not imageinfo:
            continue
        info = imageinfo[0]
        thumb_url = str(info.get("thumburl") or info.get("url") or "")
        file_url = str(info.get("url") or "")
        if not thumb_url or not file_url:
            continue

        meta = info.get("extmetadata") or {}
        license_short = str((meta.get("LicenseShortName") or {}).get("value") or "")
        usage_terms = str((meta.get("UsageTerms") or {}).get("value") or "")
        license_url = str((meta.get("LicenseUrl") or {}).get("value") or "")
        attribution = str((meta.get("Attribution") or {}).get("value") or "")
        artist = str((meta.get("Artist") or {}).get("value") or "")
        credit = str((meta.get("Credit") or {}).get("value") or "")

        license_text = license_short or usage_terms
        if not _is_license_allowed(license_text):
            continue

        page_url = f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}"

        out.append(
            RemoteAsset(
                source="wikimedia_commons",
                query=query,
                file_url=thumb_url,  # we use the thumb to control size
                page_url=page_url,
                title=title,
                license=license_text,
                license_url=license_url,
                attribution=attribution,
                artist=artist,
                credit=credit,
            )
        )

    return out


def download_asset(
    asset: RemoteAsset,
    *,
    cache_dir: Optional[Path] = None,
    timeout_s: int = 30,
    max_bytes: int = 6_000_000,
) -> RemoteAsset:
    """
    Descarga una imagen y la guarda en cache (redimensionada a un ancho máximo razonable).
    """
    cache_dir = (cache_dir or get_default_cache_dir()).resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    ext = _clean_ext(asset.file_url)
    key = _sha256(asset.file_url)
    raw_path = cache_dir / f"{key}{ext}"
    jpg_path = cache_dir / f"{key}.jpg"
    meta_path = cache_dir / f"{key}.json"

    # Cache hit
    if jpg_path.exists() and meta_path.exists():
        asset.downloaded_path = str(jpg_path)
        return asset

    with requests.get(asset.file_url, stream=True, timeout=timeout_s, headers=_get_headers()) as r:
        r.raise_for_status()
        ctype = (r.headers.get("Content-Type") or "").lower()
        if "image" not in ctype:
            raise ValueError(f"El recurso no es imagen. Content-Type: {ctype!r}")

        total = 0
        with raw_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("La imagen excede el tamaño máximo permitido.")
                f.write(chunk)

    # Normalize to JPG for smaller PDFs
    with Image.open(raw_path) as im:
        im = im.convert("RGB")
        max_w = 1600
        if im.width > max_w:
            ratio = max_w / float(im.width)
            im = im.resize((max_w, int(im.height * ratio)))
        im.save(jpg_path, format="JPEG", quality=85, optimize=True)

    meta_path.write_text(json.dumps(asset.to_meta(), ensure_ascii=False, indent=2), encoding="utf-8")
    asset.downloaded_path = str(jpg_path)
    return asset


def pick_cover_asset_for_input(planeacion_input: Dict[str, Any], *, theme_id: str) -> str:
    """
    Construye un query de búsqueda para portada a partir del tema/planeación.
    """
    tema = str(planeacion_input.get("tema") or "").strip()
    if theme_id == "primavera":
        # Prefer illustration style
        return f"{tema} spring flowers illustration"
    return f"{tema} illustration"


def fetch_cover_image(
    planeacion_input: Dict[str, Any],
    *,
    theme_id: str,
    cache_dir: Optional[Path] = None,
) -> Optional[RemoteAsset]:
    """
    Intenta obtener una imagen de portada licenciada y cacheada.
    """
    query = pick_cover_asset_for_input(planeacion_input, theme_id=theme_id)
    candidates = search_commons_images(query, limit=10)
    if not candidates:
        return None

    # Pick first downloadable candidate
    for c in candidates:
        try:
            return download_asset(c, cache_dir=cache_dir)
        except Exception:
            continue
    return None
