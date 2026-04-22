print("🚨🚨🚨 SCRIPT NUEVO DECATHLON 🚨🚨🚨")
raise SystemExit("STOP")

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
    "ciclismo", "bicicleta", "bicicletas", "bici", "bicis", "mtb", "gravel", "carretera",
    "maillot", "culotte", "casco", "pedal", "pedales", "sillin", "sillín",
    "manillar", "zapatillas ciclismo", "gafas ciclismo", "luces bici",
    "bidon", "bidón", "portabidon", "portabidón", "cadena bici", "freno bici",
    "herramienta bici", "rueda bici", "cubierta bici", "cubiertas bici", "cámara bici",
    "cubrezapatillas", "portabultos", "guardabarros", "calas", "look keo",
    "rockrider", "triban", "van rysel", "btwin", "b'twin", "rodillo", "rodillos",
    "portabicis", "gps ciclismo", "ciclocomputador", "camelbak", "bikepacking"
]

EXCLUDE_KEYWORDS = [
    "fútbol", "running", "pesca", "yoga", "voleibol", "baloncesto",
    "béisbol", "bikini", "esquí", "pádel", "boxeo", "judo", "natación",
    "golf", "tenis", "surf", "kayak", "piragua", "camping", "senderismo",
    "musculación", "crossfit", "pilates"
]

BRAND_MARKERS = [
    "DECATHLON", "ROCKRIDER", "TRIBAN", "VAN RYSEL", "BTWIN", "B'TWIN",
    "KIPRUN", "PUMA", "ADIDAS", "SHIMANO", "KALENJI", "ELOPS", "RIVERSIDE",
    "OXELO", "FOUGANZA", "KIPSTA", "DOMYOS", "QUECHUA", "WEDZE", "ARTENGO"
]


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

            DEBUG_RAW_PATH.write_text(text[:50000], encoding="utf-8")
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


def canonical_url_from_affiliate(affiliate_url: str) -> str:
    affiliate_url = normalize(affiliate_url)
    if not affiliate_url:
        return ""

    try:
        parsed = urllib.parse.urlparse(affiliate_url)
        qs = urllib.parse.parse_qs(parsed.query)
        real = qs.get("url", [""])[0]
        real = normalize(real)
        if real.startswith("http://") or real.startswith("https://"):
            return real
    except Exception:
        pass

    return ""


def find_price_before_affiliate(text: str, affiliate_url: str) -> Optional[float]:
    before = text
    if affiliate_url and affiliate_url in text:
        before = text.split(affiliate_url, 1)[0]

    matches = re.findall(r"(?<!\d)(\d{1,4}[.,]\d{2})(?!\d)", before)
    if not matches:
        return None

    # coge el último decimal antes de la URL de afiliación, que en este feed suele ser el precio.
    return safe_float(matches[-1])


def clean_title(raw_title: str) -> str:
    title = normalize(raw_title)
    if not title:
        return ""

    title = re.sub(r"\b\d{7,8}\b", "", title)
    title = re.sub(r"\b(Talla única|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL)\b$", "", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" -|")
    return title


def extract_title(block: str, image_url: str, affiliate_url: str, sku: str) -> str:
    work = normalize(block)

    if image_url and image_url in work:
        after_image = work.split(image_url, 1)[1].strip()
    else:
        after_image = work

    if affiliate_url and affiliate_url in after_image:
        before_aff = after_image.split(affiliate_url, 1)[0].strip()
    else:
        before_aff = after_image

    if sku:
        before_aff = re.sub(rf"\b{re.escape(sku)}\b", " ", before_aff)
        # A veces aparece el SKU dos veces.
        before_aff = re.sub(rf"\b{re.escape(sku)}\b", " ", before_aff)

    # Intenta cortar por categorías/tienda/talla típicas del feed.
    cut_markers = [
        r"\bDecathlon\b",
        r"\bTalla única\b",
        r"\bXS\b", r"\bS\b", r"\bM\b", r"\bL\b", r"\bXL\b", r"\bXXL\b", r"\bXXXL\b",
        r"\b[0-9]{1,3}-[0-9]{1,3}cm\b",
        r"\b[0-9]{1,2}-[0-9]{1,2}A\b",
    ]
    for marker in cut_markers:
        parts = re.split(marker, before_aff, maxsplit=1, flags=re.I)
        if parts:
            before_aff = parts[0].strip()

    # Busca una secuencia razonable tras el SKU.
    title = before_aff.strip()

    # Si hay demasiada basura delante, intenta quedarte con la parte final útil.
    pieces = [p.strip(" -|") for p in re.split(r"\s{2,}| \| ", title) if p.strip(" -|")]
    if pieces:
        # normalmente el último fragmento largo es el nombre del producto
        pieces_sorted = sorted(pieces, key=len, reverse=True)
        candidate = pieces_sorted[0]
        if len(candidate) >= 8:
            title = candidate

    title = clean_title(title)

    if len(title) < 8:
        # último recurso: intentar reconstruir desde URL real
        real = canonical_url_from_affiliate(affiliate_url)
        if real:
            slug = urllib.parse.urlparse(real).path.rstrip("/").split("/")[-1]
            slug = re.sub(r"^[a-z]\d+[a-z0-9]*$", "", slug, flags=re.I)
            title = clean_title(slug.replace("-", " "))

    return title


def extract_brand(block: str) -> str:
    upper = normalize(block).upper()
    for brand in BRAND_MARKERS:
        if upper.startswith(brand):
            return brand
    for brand in BRAND_MARKERS:
        if f" {brand} " in f" {upper} ":
            return brand
    return "DECATHLON"


def split_blocks(raw: str):
    text = raw.replace("\r", " ").replace("\n", " ")
    text = normalize(text)

    # El feed nuevo concatena productos en una sola línea usando la URL de afiliación
    # como delimitador de cierre de bloque.
    aff_pattern = re.compile(r"https://afiliacion\.decathlon\.es/tracking/clk\?[^\s<]+", re.I)

    matches = list(aff_pattern.finditer(text))
    if not matches:
        return []

    blocks = []
    start = 0
    for m in matches:
        end = m.end()
        block = text[start:end].strip()
        if block:
            blocks.append(block)
        start = end

    # Si queda cola con otro producto incompleto, la ignoramos.
    return blocks


def parse_feed(raw):
    products = []
    seen = set()

    blocks = split_blocks(raw)

    total_blocks = len(blocks)
    with_title = 0
    with_url = 0
    with_image = 0
    with_price = 0
    cycling_products = 0
    filtered_out = 0
    duplicates = 0

    for block in blocks:
        affiliate_match = re.search(r"https://afiliacion\.decathlon\.es/tracking/clk\?[^\s<]+", block, re.I)
        image_match = re.search(r"https://contents\.mediadecathlon\.com/[^\s<]+", block, re.I)
        sku_match = re.search(r"\b(\d{7,8})\b", block)

        affiliate_url = normalize(affiliate_match.group(0)) if affiliate_match else ""
        image = normalize(image_match.group(0)) if image_match else ""
        sku = sku_match.group(1) if sku_match else ""

        url = canonical_url_from_affiliate(affiliate_url)
        price = find_price_before_affiliate(block, affiliate_url)
        title = extract_title(block, image, affiliate_url, sku)
        brand = extract_brand(block)

        if title:
            with_title += 1
        if url:
            with_url += 1
        if image:
            with_image += 1
        if price is not None:
            with_price += 1

        text_for_filter = f"{title} {brand} {block}"

        if not is_cycling(text_for_filter):
            continue

        cycling_products += 1

        key = url or affiliate_url or title
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)

        product = {
            "id": key,
            "title": title,
            "brand": brand,
            "category": "ciclismo",
            "category_hint": "",
            "image": image,
            "url": url,
            "affiliate_url": affiliate_url or url,
            "source": "decathlon",
            "source_label": "Decathlon",
            "price": price,
            "old_price": None,
            "discount_pct": 0,
            "recomendacion": 0,
            "detail_enabled": False,
        }

        if quality_filter(product):
            # Puntúa mejor lo barato si no hay descuento explícito.
            product["recomendacion"] = round(max(0, 100 - (product["price"] or 0)), 2)
            products.append(product)
        else:
            filtered_out += 1

    log(f"[INFO] Bloques detectados en feed plano: {total_blocks}")
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
            x.get("recomendacion", 0),
            -(x.get("price") or 0)
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
