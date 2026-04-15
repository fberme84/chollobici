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

CYCLING_KEYWORDS = [
    "ciclismo", "bicicleta", "bici", "mtb", "gravel", "carretera", "road bike",
    "maillot", "culotte", "casco", "pedal", "pedales", "sillin", "sillín",
    "manillar", "cubrezapatillas", "zapatillas de ciclismo", "gafas ciclismo",
    "luces bici", "luz trasera bicicleta", "bidon", "bidón", "portabidon", "portabidón",
    "puños", "rueda bici", "cubierta bici", "camara bici", "cámara bici",
    "herramienta bici", "cadena bici", "freno bici", "btt", "endura", "spiuk",
    "siroko", "ergon", "look keo", "calas", "guardabarros bici", "grips", "sillin bici",
    "portaherramientas", "triatlon", "triatlón", "bikepacking", "portabultos bici",
]

EXCLUDE_KEYWORDS = [
    "fútbol", "running", "pesca", "yoga", "voleibol", "baloncesto", "béisbol",
    "bikini", "esquí", "pádel", "boxeo", "judo", "natación", "snow", "surf",
]

BAD_WORDS = [
    "calcetines fútbol", "futbol", "fútbol", "pesca", "yoga", "voleibol",
    "baloncesto", "béisbol", "bikini", "esquí", "pádel", "boxeo", "judo",
]

MIN_PRICE = 5.0
MIN_DISCOUNT_PCT = 10
MAX_PRODUCTS = 200

def log(msg: str) -> None:
    print(msg, flush=True)

def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

def safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("€", "").replace("EUR", "").replace(",", ".").strip()
    try:
        return float(text)
    except ValueError:
        return None

def normalize_space(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()

def extract_text(product: ET.Element, names: list[str]) -> str:
    for name in names:
        node = product.find(name)
        if node is not None and node.text:
            return normalize_space(node.text)
    return ""

def is_valid_xml_payload(text: str) -> bool:
    sample = (text or "").lstrip()[:200]
    return sample.startswith("<?xml") or sample.startswith("<Products>") or sample.startswith("<Products ")

def fetch_feed() -> Optional[str]:
    log(f"[INFO] DECATHLON_FEED_URL configurado: {'sí' if FEED_URL else 'no'}")
    if not FEED_URL:
        log("[WARN] No hay URL de Decathlon")
        return None

    ensure_dirs()
    backoffs = [5, 15, 30]

    for attempt in range(3):
        try:
            log(f"[INFO] Intento {attempt + 1} descarga Decathlon")
            resp = requests.get(
                FEED_URL,
                timeout=(20, 180),
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; CholloBiciBot/1.0)",
                    "Accept": "*/*",
                },
            )
            text = resp.text or ""
            DEBUG_RAW_PATH.write_text(text[:20000], encoding="utf-8", errors="ignore")

            log(f"[INFO] Status code: {resp.status_code}")
            log(f"[INFO] Content-Type: {resp.headers.get('Content-Type')}")
            log(f"[INFO] Bytes recibidos: {len(text)}")
            sample = text[:500].replace("\n", " ").replace("\r", " ")
            log(f"[INFO] Muestra: {sample}")

            if resp.status_code == 200 and len(text) > 1000 and is_valid_xml_payload(text):
                TMP_XML_PATH.write_text(text, encoding="utf-8", errors="ignore")
                log("[INFO] Feed XML válido recibido")
                return text

            log("[WARN] Respuesta sospechosa, reintentando...")
        except Exception as exc:
            log(f"[ERROR] Error descargando Decathlon: {exc}")

        time.sleep(backoffs[attempt])

    log("[ERROR] No se pudo obtener feed válido de Decathlon")
    return None

def infer_cycling(product_text: str) -> bool:
    text = product_text.lower()
    has_positive = any(k in text for k in CYCLING_KEYWORDS)
    has_negative = any(k in text for k in EXCLUDE_KEYWORDS)
    return has_positive and not has_negative

def build_product_record(product: ET.Element) -> dict:
    sku = extract_text(product, ["Sku", "SKU"])
    product_id = extract_text(product, ["Product_ID", "ProductId", "ProductID"])
    name = extract_text(product, ["Name", "Title"])
    brand = extract_text(product, ["Brand"])
    nature = extract_text(product, ["Product_Nature", "Nature", "Category"])
    image = extract_text(product, ["Images", "Image", "Image_URL", "ImageUrl"])
    url = extract_text(product, ["Url", "URL", "Product_URL", "ProductUrl"])
    size = extract_text(product, ["Size", "Variant", "Talla"])
    currency = extract_text(product, ["Currency"]) or "EUR"

    old_price = None
    for tag in ["Retail_Price", "Original_Price", "Old_Price", "OldPrice", "Price_Before"]:
        value = safe_float(extract_text(product, [tag]))
        if value is not None:
            old_price = value
            break

    price = None
    for tag in ["Sale_Price", "Current_Price", "Price", "Final_Price", "Promo_Price"]:
        value = safe_float(extract_text(product, [tag]))
        if value is not None:
            price = value
            break

    if price is None:
        price = old_price
    if old_price is None:
        old_price = price

    discount_pct = 0
    if price is not None and old_price and old_price > 0 and price <= old_price:
        discount_pct = round((old_price - price) / old_price * 100)

    title = normalize_space(name)
    category_hint = normalize_space(nature)
    combined = " | ".join([title, brand, category_hint, size])

    return {
        "id": product_id or sku or title,
        "sku": sku,
        "product_id": product_id,
        "title": title,
        "brand": brand,
        "category": "ciclismo",
        "category_hint": category_hint,
        "image": image,
        "url": url,
        "affiliate_url": url,
        "source": "decathlon",
        "source_label": "Decathlon",
        "price": price,
        "old_price": old_price,
        "discount_pct": discount_pct,
        "size": size,
        "currency": currency,
        "detail_enabled": False,
        "catalog_excluded": False,
        "recomendacion": discount_pct,
        "_combined_text": combined,
    }

def should_keep_product(record: dict) -> bool:
    text = (record.get("title") or "").lower()
    combined = (record.get("_combined_text") or "").lower()

    if any(bad in text for bad in BAD_WORDS):
        return False

    price = record.get("price")
    if price is None or price <= MIN_PRICE:
        return False

    discount_pct = record.get("discount_pct") or 0
    if discount_pct < MIN_DISCOUNT_PCT:
        return False

    if not record.get("image") or not record.get("url"):
        return False

    if any(bad in combined for bad in EXCLUDE_KEYWORDS):
        return False

    return True

def parse_feed(raw_text: str) -> list[dict]:
    log("[INFO] Inicio parseo feed Decathlon")
    if not raw_text:
        log("[WARN] Texto vacío, no se puede parsear")
        return []

    if not is_valid_xml_payload(raw_text):
        log("[WARN] La respuesta no parece XML válido")
        return []

    products: list[dict] = []
    candidates = 0
    cycling = 0
    duplicates = 0
    filtered_out = 0
    seen_ids: set[str] = set()

    try:
        context = ET.iterparse(TMP_XML_PATH, events=("end",))
        for _, elem in context:
            if elem.tag != "Product":
                continue

            candidates += 1
            record = build_product_record(elem)
            elem.clear()

            if not record["title"] or not record["url"]:
                continue

            if not infer_cycling(record["_combined_text"]):
                continue

            cycling += 1
            dedupe_key = record["product_id"] or record["sku"] or record["url"]
            if dedupe_key in seen_ids:
                duplicates += 1
                continue
            seen_ids.add(dedupe_key)

            if not should_keep_product(record):
                filtered_out += 1
                continue

            record.pop("_combined_text", None)
            products.append(record)

    except Exception as exc:
        log(f"[ERROR] Fallo parseando XML de Decathlon: {exc}")
        return []

    products.sort(
        key=lambda x: (
            x.get("discount_pct", 0),
            x.get("recomendacion", 0),
            -(x.get("price") or 0)
        ),
        reverse=True,
    )
    products = products[:MAX_PRODUCTS]

    log(f"[INFO] Registros candidatos XML Decathlon detectados: {candidates}")
    log(f"[INFO] Registros Decathlon ciclismo antes de deduplicar: {cycling}")
    log(f"[INFO] Duplicados Decathlon descartados: {duplicates}")
    log(f"[INFO] Productos Decathlon descartados por filtros de calidad: {filtered_out}")
    log(f"[INFO] Registros Decathlon ciclismo tras filtros y límite: {len(products)}")
    return products

def save_products(products: list[dict]) -> None:
    ensure_dirs()
    tmp_path = OUTPUT_PATH.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(OUTPUT_PATH)

def main() -> None:
    raw = fetch_feed()
    if not raw:
        log("[WARN] No se ha podido obtener feed Decathlon")
        return

    products = parse_feed(raw)
    excluded_count = len([p for p in products if p.get("catalog_excluded")])
    log(f"Productos Decathlon excluidos por redirección/listing: {excluded_count}")

    save_products(products)
    log(f"Productos Decathlon ciclismo guardados: {len(products)}")

if __name__ == "__main__":
    main()
