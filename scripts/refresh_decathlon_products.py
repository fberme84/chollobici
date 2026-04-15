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

MIN_PRICE = 10
MAX_PRODUCTS = 200

CYCLING_KEYWORDS = [
    "ciclismo", "bicicleta", "bici", "mtb", "gravel", "carretera",
    "maillot", "culotte", "casco", "pedal", "pedales", "sillin", "sillín",
    "manillar", "zapatillas ciclismo", "gafas ciclismo", "luces bici",
    "bidon", "bidón", "portabidon", "portabidón", "cadena bici", "freno bici",
    "herramienta bici", "rueda bici", "cubierta bici", "cámara bici",
    "cubrezapatillas", "portabultos", "guardabarros", "calas", "look keo"
]

EXCLUDE_KEYWORDS = [
    "fútbol", "running", "pesca", "yoga", "voleibol", "baloncesto",
    "béisbol", "bikini", "esquí", "pádel", "boxeo", "judo", "natación"
]


def log(msg: str):
    print(msg, flush=True)


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def safe_float(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    text = str(value).strip()
    text = text.replace("€", "").replace("EUR", "").replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def extract(product, names):
    for n in names:
        node = product.find(n)
        if node is not None and node.text:
            return normalize(node.text)
    return ""


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
    text = text.lower()
    return any(k in text for k in CYCLING_KEYWORDS) and not any(k in text for k in EXCLUDE_KEYWORDS)


def quality_filter(p):
    # temporalmente relajado para diagnosticar
    if not p["image"] or not p["url"] or not p["title"]:
        return False
    if p["price"] is not None and p["price"] < MIN_PRICE:
        return False
    return True


def parse_feed(raw):
    products = []
    seen = set()

    total_products = 0
    cycling_products = 0
    with_title = 0
    with_url = 0
    with_image = 0
    with_price = 0
    filtered_out = 0
    duplicates = 0

    context = ET.iterparse(TMP_XML_PATH, events=("end",))

    for _, elem in context:
        if elem.tag != "Product":
            continue

        total_products += 1

        name = extract(elem, ["Name", "Title"])
        brand = extract(elem, ["Brand"])
        url = extract(elem, ["Url", "URL", "Product_URL", "ProductUrl"])
        image = extract(elem, ["Images", "Image", "Image_URL", "ImageUrl"])
        nature = extract(elem, ["Product_Nature", "Nature", "Category"])

        # probamos más nombres posibles de precio
        price = None
        for tag in [
            "Sale_Price", "Current_Price", "Price", "Final_Price", "Promo_Price",
            "Offer_Price", "Best_Price", "Discount_Price", "Price_Sale"
        ]:
            price = safe_float(extract(elem, [tag]))
            if price is not None:
                break

        old_price = None
        for tag in [
            "Retail_Price", "Original_Price", "Old_Price", "OldPrice",
            "Price_Before", "Regular_Price", "List_Price", "Price_Original"
        ]:
            old_price = safe_float(extract(elem, [tag]))
            if old_price is not None:
                break

        if name:
            with_title += 1
        if url:
            with_url += 1
        if image:
            with_image += 1
        if price is not None:
            with_price += 1

        text = f"{name} {brand} {nature}"

        if not is_cycling(text):
            elem.clear()
            continue

        cycling_products += 1

        key = url or name
        if key in seen:
            duplicates += 1
            elem.clear()
            continue
        seen.add(key)

        discount_pct = 0
        if price is not None and old_price and old_price > 0 and price <= old_price:
            discount_pct = round((old_price - price) / old_price * 100)

        product = {
            "id": key,
            "title": name,
            "brand": brand,
            "category": "ciclismo",
            "category_hint": nature,
            "image": image,
            "url": url,
            "affiliate_url": url,
            "source": "decathlon",
            "source_label": "Decathlon",
            "price": price,
            "old_price": old_price,
            "discount_pct": discount_pct,
            "recomendacion": discount_pct if discount_pct else (price or 0),
            "detail_enabled": False,
        }

        if quality_filter(product):
            products.append(product)
        else:
            filtered_out += 1

        elem.clear()

    log(f"[INFO] Productos XML totales: {total_products}")
    log(f"[INFO] Productos con título: {with_title}")
    log(f"[INFO] Productos con URL: {with_url}")
    log(f"[INFO] Productos con imagen: {with_image}")
    log(f"[INFO] Productos con precio detectado: {with_price}")
    log(f"[INFO] Productos ciclismo detectados: {cycling_products}")
    log(f"[INFO] Duplicados descartados: {duplicates}")
    log(f"[INFO] Productos descartados por quality_filter: {filtered_out}")
    log(f"[INFO] Productos válidos antes de limitar: {len(products)}")

    products.sort(
        key=lambda x: (
            x.get("discount_pct", 0),
            x.get("price") or 0
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