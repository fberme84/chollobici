from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
INPUT_FILE = DATA_DIR / "amazon_manual_links.txt"
PRODUCTS_FILE = DATA_DIR / "amazon_products.json"
NOTES_FILE = DATA_DIR / "amazon_products_import_notes.txt"
DEFAULT_TAG = "chollobici0a-21"
TODAY = datetime.now(timezone.utc).date().isoformat()

CATEGORY_RULES = [
    ("gafas", "Gafas"),
    ("casco", "Cascos"),
    ("maillot", "Ropa"),
    ("culotte", "Ropa"),
    ("camiseta", "Ropa"),
    ("bolsa", "Bolsas"),
    ("manillar", "Bolsas"),
    ("soporte", "Accesorios"),
    ("portabidon", "Accesorios"),
    ("bidon", "Hidratación"),
    ("botella", "Hidratación"),
    ("inflador", "Taller"),
    ("tubeless", "Taller"),
    ("herramient", "Herramientas"),
    ("gps", "Electrónica"),
    ("ciclocomputador", "Electrónica"),
]


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://\S+", text)


def extract_asin(url: str) -> str | None:
    match = re.search(r"/(?:dp|gp/aw/d|aw/d)/([A-Z0-9]{10})", url)
    return match.group(1) if match else None


def canonical_amazon_url(url: str, partner_tag: str = DEFAULT_TAG) -> str:
    asin = extract_asin(url)
    if not asin:
        return url.strip()
    clean = f"https://www.amazon.es/dp/{asin}"
    parsed = urlparse(clean)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if partner_tag:
        query["tag"] = partner_tag
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), parsed.fragment))


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    return re.sub(r"-+", "-", norm)


def infer_title(url: str, asin: str) -> str:
    parsed = urlparse(url)
    path = parsed.path
    segment = ""
    if "/dp/" in path:
        segment = path.split("/dp/")[0].strip("/")
    elif "/gp/aw/d/" in path or "/aw/d/" in path:
        segment = ""

    if not segment:
        return f"Producto Amazon {asin}"

    words = [w for w in segment.split("-") if w and not re.fullmatch(r"[A-Z0-9]{10}", w, re.I)]
    if not words:
        return f"Producto Amazon {asin}"

    text = " ".join(words)
    text = re.sub(r"\b(ref|sr|sxin|gp|aw)\b.*$", "", text, flags=re.I).strip()
    if not text:
        return f"Producto Amazon {asin}"
    return text[:1].upper() + text[1:]


def infer_category(title: str) -> str:
    low = slugify(title)
    for needle, category in CATEGORY_RULES:
        if needle in low:
            return category
    return "Accesorios"


def build_item(url: str) -> dict | None:
    asin = extract_asin(url)
    if not asin:
        return None
    title = infer_title(url, asin)
    return {
        "id": f"amazon-{slugify(title)}-{asin.lower()}",
        "asin": asin,
        "title": title,
        "category": infer_category(title),
        "price": 0,
        "old_price": None,
        "url": canonical_amazon_url(url),
        "image": "",
        "source": "manual",
        "last_checked": TODAY,
        "editor_pick": False,
        "manual_visibility": True,
        "reason": "Enlace añadido manualmente pendiente de precio/API",
    }


def merge_items(existing: list[dict], incoming: list[dict]) -> tuple[list[dict], list[str]]:
    by_asin: dict[str, dict] = {}
    notes: list[str] = []

    for item in existing:
        asin = item.get("asin") or extract_asin(item.get("url", ""))
        if asin:
            item = dict(item)
            item["asin"] = asin
            by_asin[asin] = item

    for item in incoming:
        asin = item["asin"]
        current = by_asin.get(asin)
        if current:
            merged = dict(current)
            for key, value in item.items():
                if key in {"title", "category"} and merged.get(key):
                    continue
                if key in {"price", "old_price", "image"} and merged.get(key) not in (None, "", 0):
                    continue
                merged[key] = value
            merged["url"] = item["url"]
            merged["manual_visibility"] = True
            merged["last_checked"] = TODAY
            by_asin[asin] = merged
            notes.append(f"Actualizado/normalizado: {asin} -> {merged['title']}")
        else:
            by_asin[asin] = item
            notes.append(f"Añadido: {asin} -> {item['title']}")

    merged_items = list(by_asin.values())
    merged_items.sort(key=lambda x: (x.get("editor_pick", False), x.get("title", "").lower()), reverse=True)
    return merged_items, notes


def main() -> int:
    if not INPUT_FILE.exists():
        print(f"No existe {INPUT_FILE}", file=sys.stderr)
        return 1

    text = INPUT_FILE.read_text(encoding="utf-8")
    urls = extract_urls(text)
    if not urls:
        print("No se han encontrado URLs válidas.", file=sys.stderr)
        return 1

    incoming = [item for url in urls if (item := build_item(url))]
    existing = load_json(PRODUCTS_FILE, [])
    merged, notes = merge_items(existing, incoming)
    save_json(PRODUCTS_FILE, merged)

    note_text = (
        "Importación manual de enlaces Amazon.\n"
        f"Fecha: {TODAY}\n"
        f"Enlaces leídos: {len(urls)}\n"
        f"ASIN válidos: {len(incoming)}\n\n"
        + "\n".join(f"- {line}" for line in notes)
        + "\n"
    )
    NOTES_FILE.write_text(note_text, encoding="utf-8")
    print(f"Importados/normalizados {len(incoming)} enlaces. Total catálogo Amazon: {len(merged)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
