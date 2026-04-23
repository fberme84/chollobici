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
DEBUG_PRODUCTS_PATH = DATA_DIR / "debug_decathlon_products_sample.json"

FEED_URL = os.getenv("DECATHLON_FEED_URL", "").strip()

MIN_PRICE = 10
MAX_PRODUCTS = 200

CYCLING_KEYWORDS = [
    "ciclismo", "bicicleta", "bicicletas", "bici", "mtb", "gravel", "carretera",
    "maillot", "culotte", "casco", "pedal", "pedales", "sillin", "sillín",
    "manillar", "zapatillas ciclismo", "gafas ciclismo", "luces bici",
    "bidon", "bidón", "portabidon", "portabidón", "cadena bici", "freno bici",
    "herramienta bici", "rueda bici", "cubierta bici", "cubierta", "camara bici",
    "cámara bici", "cubrezapatillas", "portabultos", "guardabarros", "calas",
    "look keo", "rockrider", "triban", "van rysel", "btwin", "b'twin",
    "rodillo", "sillin bici", "porta bidon", "inflador bici", "ciclista", "ciclo"
]

EXCLUDE_KEYWORDS = [
    "fútbol", "futbol", "running", "pesca", "yoga", "voleibol", "baloncesto",
    "béisbol", "beisbol", "bikini", "esquí", "esqui", "pádel", "padel", "boxeo",
    "judo", "natación", "natacion", "golf", "pilates", "musculación", "musculacion",
    "crossfit", "marcha deportiva", "marcha nórdica", "marcha nordica"
]

BRAND_WORDS = [
    "DECATHLON", "KIPSTA", "DOMYOS", "ROCKRIDER", "TRIBAN", "VAN RYSEL", "BTWIN",
    "B'TWIN", "RIVERSIDE", "WEDZE", "KALENJI", "PUMA", "MINN KOTA", "CYCOLOGY",
    "VITTORIA", "SHIMANO", "GARMIN", "ELOPS", "OXELO", "FORCLAZ", "QUECHUA",
    "CERVÉLO", "CERVELO", "MICHELIN", "SRAM", "LOOK", "MAVIC"
]


def log(msg: str):
    print(msg, flush=True)


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def normalize(text: Optional[str]) -> str:
    value = html.unescape(str(text or ""))
    value = urllib.parse.unquote(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def strip_xml_tail(text: Optional[str]) -> str:
    value = normalize(text)
    if "<" in value:
        value = value.split("<", 1)[0].strip()
    return value


def clean_category_hint(text: Optional[str]) -> str:
    value = normalize(text)
    value = re.sub(r"</?[^>]+>", " ", value)
    value = re.sub(r"(SkuID|Seller|Price|Size|URL|Img|Name|Sport).*", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value).strip(" -|")
    return value[:180]


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
    if FEED_URL:
        log(f"[INFO] FEED_URL prefix: {FEED_URL[:60]}")

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
                return text
        except Exception as e:
            log(f"[ERROR] {e}")
        time.sleep(10 * (i + 1))
    return None


def is_cycling(text: str):
    text = normalize(text).lower()
    return any(k in text for k in CYCLING_KEYWORDS) and not any(k in text for k in EXCLUDE_KEYWORDS)


def quality_filter(product: dict) -> bool:
    if not product["image"] or not product["url"] or not product["title"]:
        return False
    if product["price"] is not None and product["price"] < MIN_PRICE:
        return False
    return True


def parse_affiliate_url(url: str):
    parsed = urllib.parse.urlparse(html.unescape(url))
    qs = urllib.parse.parse_qs(parsed.query)
    real_url = normalize(qs.get("url", [""])[0])
    pca = normalize(qs.get("pca", [""])[0])
    sku = ""
    title = ""
    if pca:
        parts = [p for p in pca.split("|") if p is not None]
        if parts:
            sku = normalize(parts[0])
        if len(parts) > 1:
            title = normalize(parts[1])
    return real_url, sku, title


def guess_brand(chunk: str):
    prefix = normalize(chunk[:140])
    for brand in sorted(BRAND_WORDS, key=len, reverse=True):
        if prefix.upper().startswith(brand.upper()):
            return brand.title() if brand.isupper() else brand
    seller_match = re.search(r"<Seller>([^<]+)</Seller>", chunk, flags=re.I)
    if seller_match:
        return normalize(seller_match.group(1))
    m = re.match(r"^\s*([A-Z0-9ÁÉÍÓÚÜÑ][A-Z0-9ÁÉÍÓÚÜÑ'&\- ]{1,30})", prefix)
    return normalize(m.group(1)) if m else ""


def extract_price(before_url: str) -> Optional[float]:
    tag_match = re.search(r"<Price>([^<]+)</Price>", before_url, flags=re.I)
    if tag_match:
        price = safe_float(tag_match.group(1))
        if price is not None:
            return price
    candidates = re.findall(r'(?<![\d])(\d{1,4}[.,]\d{2})(?!\d)', before_url)
    if not candidates:
        return None
    return safe_float(candidates[-1])


def extract_image(chunk: str) -> str:
    m = re.search(r'https://contents\.mediadecathlon\.com/[^\s<]+', chunk)
    return strip_xml_tail(m.group(0)) if m else ""


def clean_title(title: str, brand: str = "") -> str:
    title = normalize(title)
    title = re.sub(r"</?[^>]+>", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" -|")
    if brand and title.upper().startswith(brand.upper() + " "):
        title = title[len(brand):].strip(" -|")
    return title[:180]


def fallback_title_from_url(url: str) -> str:
    if not url:
        return ""
    try:
        path = urllib.parse.urlparse(url).path
        slug = path.rstrip("/").split("/")[-1]
        slug = re.sub(r"[-_]+", " ", slug)
        slug = re.sub(r"(c\d+|m\d+|x\d+|\d+)", "", slug, flags=re.I)
        return clean_title(slug.title())
    except Exception:
        return ""


def parse_feed(raw):
    products = []
    seen = set()
    raw = html.unescape(raw).replace("", " ").replace("
", " ")
    affiliate_pattern = re.compile(r"https://afiliacion\.decathlon\.es/tracking/clk\?[^\s<]+")
    matches = list(affiliate_pattern.finditer(raw))
    prev_end = 0

    for match in matches:
        affiliate_url = normalize(match.group(0))
        chunk = normalize(raw[prev_end:match.end()])
        prev_end = match.end()

        image = extract_image(chunk)
        before_aff = chunk[:chunk.rfind(affiliate_url)] if affiliate_url in chunk else chunk
        price = extract_price(before_aff)
        brand = guess_brand(chunk)
        real_url, sku, title_from_pca = parse_affiliate_url(affiliate_url)
        title = clean_title(title_from_pca, brand=brand) or fallback_title_from_url(real_url)
        sport_match = re.search(r"<Sport>([^<]+)</Sport>", chunk, flags=re.I)
        category_hint = clean_category_hint(sport_match.group(1) if sport_match else before_aff[-180:])
        text = f"{brand} {title} {real_url} {category_hint} {chunk}"

        if not title or not is_cycling(text):
            continue

        key = real_url or affiliate_url or title
        if key in seen:
            continue
        seen.add(key)

        product = {
            "id": key,
            "title": title,
            "brand": brand,
            "category": "ciclismo",
            "category_hint": category_hint,
            "image": image,
            "url": real_url,
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

        if quality_filter(product):
            products.append(product)

    DEBUG_PRODUCTS_PATH.write_text(json.dumps(products[:5], ensure_ascii=False, indent=2), encoding="utf-8")
    return products[:MAX_PRODUCTS]


def save(products):
    ensure_dirs()
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    payload = json.dumps(products, ensure_ascii=False, indent=2)
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(OUTPUT_PATH)
    print("WRITE OK:", OUTPUT_PATH, "BYTES:", len(payload), flush=True)


def main():
    raw = fetch_feed()
    if not raw:
        log("[WARN] No se pudo obtener feed")
        return
    products = parse_feed(raw)
    print("PARSE COUNT:", len(products), flush=True)
    if products:
        print("PARSE FIRST:", products[:2], flush=True)
    save(products)
    log(f"Productos Decathlon finales: {len(products)}")


if __name__ == "__main__":
    main()
