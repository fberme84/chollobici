from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_PATH = DATA_DIR / "decathlon_products.json"
DEBUG_RAW_PATH = DATA_DIR / "debug_decathlon_raw.txt"
TMP_XML_PATH = DATA_DIR / "debug_decathlon_raw.xml"

FEED_URL = os.getenv("DECATHLON_FEED_URL", "").strip()

MIN_PRICE = 10
MAX_PRODUCTS = 200

CYCLING_KEYWORDS = [
    "ciclismo", "bicicleta", "bici", "mtb", "gravel", "carretera",
    "maillot", "culotte", "casco", "pedal", "pedales", "sillin", "sillín",
    "manillar", "zapatillas ciclismo", "gafas ciclismo", "luces bici",
    "bidon", "bidón", "portabidon", "portabidón", "cadena bici", "freno bici",
    "herramienta bici", "rueda bici", "cubierta bici", "cámara bici",
    "cubrezapatillas", "portabultos", "guardabarros", "calas", "look keo",
    "btwin", "b'twin", "rockrider", "triban", "van rysel"
]

EXCLUDE_KEYWORDS = [
    "fútbol", "running", "pesca", "yoga", "voleibol", "baloncesto",
    "béisbol", "bikini", "esquí", "pádel", "boxeo", "judo", "natación"
]

BRAND_MARKERS = [
    "DECATHLON", "BTWIN", "B'TWIN", "ROCKRIDER", "TRIBAN", "VAN RYSEL",
    "KIPSTA", "DOMYOS", "OXELO", "NABAIJI", "QUECHUA", "WEDZE",
    "FORCLAZ", "INESIS", "SOLOGNAC", "KALENJI", "NYAMBA", "CAPERLAN",
    "OUTSHOCK", "TARMAK", "ARTENGO", "KIMJALY", "GEOLOGIC", "FOUGANZA"
]

BRAND_PATTERN = re.compile(r"\b(" + "|".join(re.escape(x) for x in BRAND_MARKERS) + r")\b")
IMAGE_RE = re.compile(r"https://contents\.mediadecathlon\.com[^\s<>\"]+")
AFFILIATE_RE = re.compile(r"https?://afiliacion\.decathlon\.es/tracking/clk\?[^\s<>\"]+")
PRICE_RE = re.compile(r"\b(\d+\.\d{2})\b")


def log(msg: str):
    print(msg, flush=True)


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def normalize(text: Optional[str]) -> str:
    value = html.unescape(str(text or ""))
    value = urllib.parse.unquote(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = normalize(value)
    if not text:
        return None
    text = text.replace("€", "").replace("EUR", "").replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def fetch_feed():
    log(f"[INFO] DECATHLON_FEED_URL configurado: {'sí' if FEED_URL else 'no'}")

    if not FEED_URL:
        return None

    ensure_dirs()

    for i in range(3):
        try:
            log(f"[INFO] Intento {i+1} descarga Decathlon")
            r = requests.get(FEED_URL, timeout=(20, 180))
            text = r.text or ""

            DEBUG_RAW_PATH.write_text(text[:20000], encoding="utf-8")
            log(f"[INFO] Status: {r.status_code}")
            log(f"[INFO] Bytes: {len(text)}")

            if r.status_code == 200 and len(text) > 1000:
                TMP_XML_PATH.write_text(text, encoding="utf-8")
                return text
        except Exception as e:
            log(f"[ERROR] {e}")

        time.sleep(10 * (i + 1))

    return None


def is_cycling(text: str):
    text = normalize(text).lower()
    return any(k in text for k in CYCLING_KEYWORDS) and not any(k in text for k in EXCLUDE_KEYWORDS)


def quality_filter(product: dict) -> bool:
    if not product.get("image") or not product.get("url") or not product.get("title"):
        return False
    if product.get("price") is not None and product["price"] < MIN_PRICE:
        return False
    return True


def decode_affiliate_target(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        target = params.get("url", [""])[0]
        return normalize(target)
    except Exception:
        return ""


def build_title(prefix_text: str, sku: str, brand: str) -> str:
    text = normalize(prefix_text)

    # recorta descripciones largas y se queda con la parte de nombre más cercana al SKU
    if sku:
        m = re.search(rf"\b{re.escape(sku)}\b\s+(.+?)\s+\b{re.escape(sku)}\b", text)
        if m:
            candidate = normalize(m.group(1))
            if candidate:
                return candidate[:180]

    # fallback: eliminar la marca al inicio y una posible descripción demasiado larga
    if brand and text.startswith(brand):
        text = normalize(text[len(brand):])

    # si aparece una imagen, normalmente el nombre útil va al final de la zona previa a la imagen
    parts = re.split(r"[.!?]\s+", text)
    if len(parts) > 1:
        # suele ser mejor la última frase antes de la imagen
        candidate = normalize(parts[-1])
        if candidate:
            return candidate[:180]

    return text[:180]


def parse_entry(entry_text: str, brand: str) -> Optional[dict]:
    image_match = IMAGE_RE.search(entry_text)
    affiliate_match = AFFILIATE_RE.search(entry_text)

    if not image_match or not affiliate_match:
        return None

    image = normalize(image_match.group(0))
    affiliate_url = normalize(affiliate_match.group(0))
    url = decode_affiliate_target(affiliate_url)

    before_image = normalize(entry_text[:image_match.start()])
    between = normalize(entry_text[image_match.end():affiliate_match.start()])

    sku_match = re.search(r"\b(\d{7})\b", between)
    sku = sku_match.group(1) if sku_match else ""

    price = None
    prices = PRICE_RE.findall(between)
    if prices:
        # normalmente el último precio antes de la affiliate_url es el bueno
        price = safe_float(prices[-1])

    title = build_title(before_image + " " + between, sku, brand)

    cycling_text = f"{brand} {title} {between}"
    if not is_cycling(cycling_text):
        return None

    product = {
        "id": url or affiliate_url,
        "title": title,
        "brand": brand,
        "category": "ciclismo",
        "category_hint": between[:200],
        "image": image,
        "url": url,
        "affiliate_url": affiliate_url,
        "source": "decathlon",
        "source_label": "Decathlon",
        "price": price,
        "old_price": None,
        "discount_pct": 0,
        "recomendacion": 0,
        "detail_enabled": False,
        "sku": sku,
    }

    if product["price"] is not None:
        product["recomendacion"] = max(0, 1000 - product["price"])
    else:
        product["recomendacion"] = 0

    return product if quality_filter(product) else None


def parse_feed(raw: str):
    text = normalize(raw)
    products = []
    seen = set()

    # trocea el feed a partir de cada marca reconocida
    matches = list(BRAND_PATTERN.finditer(text))

    total_blocks = 0
    valid_products = 0
    filtered_out = 0
    duplicates = 0

    for i, match in enumerate(matches):
        brand = normalize(match.group(1))
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end]

        if "afiliacion.decathlon.es/tracking/clk" not in block:
            continue

        total_blocks += 1
        product = parse_entry(block, brand)

        if not product:
            filtered_out += 1
            continue

        key = product["url"] or product["affiliate_url"]
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)

        products.append(product)
        valid_products += 1

    log(f"[INFO] Bloques detectados en feed plano: {total_blocks}")
    log(f"[INFO] Productos válidos detectados: {valid_products}")
    log(f"[INFO] Duplicados descartados: {duplicates}")
    log(f"[INFO] Productos descartados por quality_filter/parser: {filtered_out}")

    products.sort(
        key=lambda x: (
            x.get("recomendacion", 0),
            -(x.get("price") or 999999)
        ),
        reverse=True
    )

    return products[:MAX_PRODUCTS]


def save(products):
    ensure_dirs()
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT_PATH)


def main():
    raw = fetch_feed()

    if not raw:
        log("[WARN] No se pudo obtener feed")
        return

    products = parse_feed(raw)
    save(products)

    log(f"Productos Decathlon finales: {len(products)}")


if __name__ == "__main__":
    main()
