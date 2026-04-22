from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional

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


def normalize(text: Optional[str]) -> str:
    value = html.unescape(str(text or ""))
    value = urllib.parse.unquote(value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def local_name(tag: str) -> str:
    tag = str(tag or "")
    if "}" in tag:
        tag = tag.rsplit("}", 1)[-1]
    if ":" in tag:
        tag = tag.rsplit(":", 1)[-1]
    return tag.strip().lower()


def iter_texts(elem: ET.Element, names: Iterable[str]) -> Iterable[str]:
    wanted = {n.lower() for n in names}
    for node in elem.iter():
        if local_name(node.tag) not in wanted:
            continue
        text = normalize(node.text)
        if text:
            yield text
        for attr_name, attr_value in node.attrib.items():
            if local_name(attr_name) in {"href", "src", "url", "link"}:
                attr_text = normalize(attr_value)
                if attr_text:
                    yield attr_text


def extract_first(elem: ET.Element, names: Iterable[str], *, reject_url_like: bool = False) -> str:
    for value in iter_texts(elem, names):
        if reject_url_like and is_url_like(value):
            continue
        return value
    return ""


def extract_url(elem: ET.Element, names: Iterable[str]) -> str:
    for value in iter_texts(elem, names):
        if is_url_like(value):
            return value
    return ""


def is_url_like(value: str) -> bool:
    text = normalize(value).lower()
    return text.startswith(("http://", "https://", "//", "www.")) or "afiliacion.decathlon" in text or "decathlon.es" in text


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


def quality_filter(p):
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
        if local_name(elem.tag) != "product":
            continue

        total_products += 1

        name = extract_first(elem, ["Name", "Title", "Product_Name", "ProductName"], reject_url_like=True)
        brand = extract_first(elem, ["Brand", "Brand_Name", "BrandName"])
        url = extract_url(elem, ["Url", "URL", "Product_URL", "ProductUrl", "DeepLink", "TrackingUrl", "Link"])
        image = extract_url(elem, ["Images", "Image", "Image_URL", "ImageUrl", "ImageLink", "Picture", "PictureUrl"])
        nature = extract_first(elem, ["Product_Nature", "Nature", "Category", "Product_Category", "Google_Product_Category"])

        price = None
        for tag in [
            "Sale_Price", "Current_Price", "Price", "Final_Price", "Promo_Price",
            "Offer_Price", "Best_Price", "Discount_Price", "Price_Sale", "Amount"
        ]:
            price = safe_float(extract_first(elem, [tag]))
            if price is not None:
                break

        old_price = None
        for tag in [
            "Retail_Price", "Original_Price", "Old_Price", "OldPrice",
            "Price_Before", "Regular_Price", "List_Price", "Price_Original", "Recommended_Price"
        ]:
            old_price = safe_float(extract_first(elem, [tag]))
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
