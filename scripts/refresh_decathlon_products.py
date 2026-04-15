from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_PATH = DATA_DIR / "decathlon_products.json"
DEBUG_RAW_PATH = DATA_DIR / "debug_decathlon_raw.txt"
TMP_XML_PATH = DATA_DIR / "debug_decathlon_raw.xml"

FEED_URL = os.getenv("DECATHLON_FEED_URL", "").strip()

# 🔥 CONFIGURACIÓN CLAVE
MIN_PRICE = 10
MAX_PRODUCTS = 200

CYCLING_KEYWORDS = [
    "ciclismo","bicicleta","bici","mtb","gravel","carretera",
    "maillot","culotte","casco","pedal","pedales","sillin","sillín",
    "manillar","zapatillas ciclismo","gafas ciclismo","luces bici",
    "bidon","bidón","portabidon","portabidón","cadena bici","freno bici",
    "herramienta bici","rueda bici","cubierta bici","cámara bici"
]

EXCLUDE_KEYWORDS = [
    "fútbol","running","pesca","yoga","voleibol","baloncesto",
    "béisbol","bikini","esquí","pádel","boxeo","judo","natación"
]

def log(msg: str):
    print(msg, flush=True)

def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def safe_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    value = value.replace(",", ".")
    try:
        return float(value)
    except:
        return None

def normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip()

def extract(product, names):
    for n in names:
        node = product.find(n)
        if node is not None and node.text:
            return normalize(node.text)
    return ""

# -------------------------
# FETCH
# -------------------------
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

        time.sleep(10 * (i+1))

    return None

# -------------------------
# FILTROS
# -------------------------
def is_cycling(text: str):
    text = text.lower()
    return any(k in text for k in CYCLING_KEYWORDS) and not any(k in text for k in EXCLUDE_KEYWORDS)

def quality_filter(p):
    if not p["price"] or p["price"] < MIN_PRICE:
        return False

    if not p["image"] or not p["url"]:
        return False

    return True

# -------------------------
# PARSER XML
# -------------------------
def parse_feed(raw):
    products = []
    seen = set()

    context = ET.iterparse(TMP_XML_PATH, events=("end",))

    for _, elem in context:
        if elem.tag != "Product":
            continue

        name = extract(elem, ["Name"])
        brand = extract(elem, ["Brand"])
        url = extract(elem, ["Url"])
        image = extract(elem, ["Images"])
        nature = extract(elem, ["Product_Nature"])

        price = safe_float(extract(elem, ["Sale_Price", "Price"]))
        old_price = safe_float(extract(elem, ["Retail_Price"]))

        text = f"{name} {brand} {nature}"

        if not is_cycling(text):
            elem.clear()
            continue

        key = url
        if key in seen:
            elem.clear()
            continue

        seen.add(key)

        product = {
            "id": key,
            "title": name,
            "brand": brand,
            "category": "ciclismo",
            "image": image,
            "url": url,
            "affiliate_url": url,
            "source": "decathlon",
            "price": price,
            "old_price": old_price,
            "discount_pct": 0,
            "recomendacion": price or 0,
            "detail_enabled": False
        }

        if quality_filter(product):
            products.append(product)

        elem.clear()

    log(f"[INFO] Productos válidos antes de limitar: {len(products)}")

    # ordenar por precio (más caros primero → mejor margen afiliado)
    products.sort(key=lambda x: x["price"] or 0, reverse=True)

    return products[:MAX_PRODUCTS]

# -------------------------
# SAVE
# -------------------------
def save(products):
    ensure_dirs()
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT_PATH)

# -------------------------
# MAIN
# -------------------------
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