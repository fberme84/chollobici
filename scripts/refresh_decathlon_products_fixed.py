from __future__ import annotations

import html
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_PATH = DATA_DIR / "decathlon_products.json"
DEBUG_RAW_PATH = DATA_DIR / "debug_decathlon_raw.txt"
TMP_XML_PATH = DATA_DIR / "debug_decathlon_raw.xml"
DEBUG_SAMPLE_PATH = DATA_DIR / "debug_decathlon_samples.json"

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
    "rockrider", "triban", "van rysel", "btwin", "b'twin", "elops", "riverside",
    "siroko", "hutchinson", "shimano", "look", "zefal", "garmin", "wahoo",
]

EXCLUDE_KEYWORDS = [
    "fútbol", "running", "pesca", "yoga", "voleibol", "baloncesto",
    "béisbol", "bikini", "esquí", "pádel", "boxeo", "judo", "natación",
]

TITLE_FALLBACK_BLACKLIST = {
    "es", "p", "mp", "www", "decathlon", "tracking", "clk", "fid", "pca",
    "utm", "https", "http", "afiliacion", "shop", "producto", "product", "prd",
}

PREMIUM_TERMS = [
    "carbon", "cf", "sl", "pro", "racing", "team edition", "ultra", "factory",
]

DECATHLON_FILTERS = {
    "bike_max_price": 1500,
    "general_max_price": 300,
    "min_discount_percent": 10,
    "premium_terms": PREMIUM_TERMS,
}


def log(msg: str) -> None:
    print(msg, flush=True)


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def strip_ns(tag: str) -> str:
    if not tag:
        return ""
    if "}" in tag:
        tag = tag.split("}", 1)[1]
    if ":" in tag:
        tag = tag.split(":", 1)[1]
    return tag.strip().lower()


def normalize_space(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def decode_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    text = str(value)
    prev = None
    for _ in range(3):
        text = html.unescape(text)
        try:
            text = unquote(text)
        except Exception:
            pass
        if text == prev:
            break
        prev = text
    return normalize_space(text)


def safe_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = decode_value(value)
    if not text:
        return None
    text = text.replace("€", "").replace("EUR", "").replace(",", ".")
    text = re.sub(r"[^0-9.]", "", text)
    if text.count(".") > 1:
        first, *rest = text.split(".")
        text = first + "." + "".join(rest)
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


_URLISH_RE = re.compile(r"^(?:https?:)?//|^(?:https?|s):%3A%2F%2F|decathlon\.es|afiliacion\.decathlon\.es", re.I)
_IMAGE_RE = re.compile(r"\.(?:jpg|jpeg|png|webp)(?:\?|$)", re.I)


def looks_like_url(text: Optional[str]) -> bool:
    value = decode_value(text)
    return bool(value and _URLISH_RE.search(value))


def looks_like_image_url(text: Optional[str]) -> bool:
    value = decode_value(text)
    return bool(value and looks_like_url(value) and _IMAGE_RE.search(value))


def clean_tracking_url(value: Optional[str]) -> str:
    text = decode_value(value)
    if not text:
        return ""
    if text.startswith("s://"):
        text = "https://" + text[5:]
    elif text.startswith("s:%2F%2F"):
        text = decode_value(text)
    elif text.startswith("//"):
        text = "https:" + text
    if text.startswith("http//"):
        text = text.replace("http//", "http://", 1)
    if text.startswith("https//"):
        text = text.replace("https//", "https://", 1)
    return text.strip()


def normalize_text_for_match(text: str) -> str:
    text = decode_value(text).lower()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    text = text.replace("ü", "u")
    return text


def get_descendant_values(elem: ET.Element) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for child in elem.iter():
        tag = strip_ns(child.tag)
        text = decode_value(child.text)
        if text:
            values.append((tag, text))
        for attr_name, attr_value in child.attrib.items():
            attr_text = decode_value(attr_value)
            if attr_text:
                values.append((f"{tag}@{strip_ns(attr_name)}", attr_text))
    return values


def first_matching_value(values: Iterable[tuple[str, str]], tag_names: Iterable[str], *, want_url: bool = False, want_image: bool = False, reject_urlish: bool = False) -> str:
    wanted = {t.lower() for t in tag_names}
    candidates: list[str] = []
    for tag, value in values:
        base_tag = tag.split("@", 1)[0]
        if base_tag not in wanted and tag not in wanted:
            continue
        if reject_urlish and looks_like_url(value):
            continue
        if want_image and not looks_like_image_url(value):
            continue
        if want_url and not looks_like_url(value):
            continue
        candidates.append(value)
    return candidates[0] if candidates else ""


def collect_all_text(values: Iterable[tuple[str, str]]) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for _, value in values:
        if len(value) < 2:
            continue
        if looks_like_url(value) and not looks_like_image_url(value):
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        parts.append(value)
    return " ".join(parts)


def title_from_url(url: str) -> str:
    url = clean_tracking_url(url)
    if not url:
        return ""
    decoded = decode_value(url)
    m = re.search(r"/p(?:/[^/]+)?/([^/?#]+)", decoded, re.I)
    if not m:
        m = re.search(r"/(?:es/)?([^/?#]+)$", decoded, re.I)
    if not m:
        return ""
    slug = m.group(1)
    slug = re.sub(r"\.[a-z0-9]{2,5}$", "", slug, flags=re.I)
    words = [w for w in re.split(r"[-_]+", slug) if w]
    cleaned: list[str] = []
    for word in words:
        low = word.lower()
        if low in TITLE_FALLBACK_BLACKLIST:
            continue
        if re.fullmatch(r"[a-f0-9]{8,}", low):
            continue
        if re.fullmatch(r"\d+", low):
            continue
        cleaned.append(word)
    title = " ".join(cleaned[:12])
    title = re.sub(r"\b([a-z])\b", "", title, flags=re.I)
    return normalize_space(title).title()


def is_cycling(text: str) -> bool:
    value = normalize_text_for_match(text)
    return any(k in value for k in CYCLING_KEYWORDS) and not any(k in value for k in EXCLUDE_KEYWORDS)


def is_bike_product(text: str) -> bool:
    value = normalize_text_for_match(text)
    bike_terms = ["bicicleta", "bici", "mtb", "gravel", "carretera", "rockrider", "triban", "van rysel", "elops", "riverside"]
    return any(k in value for k in bike_terms)


def has_premium_terms(text: str) -> bool:
    value = normalize_text_for_match(text)
    return any(term in value for term in DECATHLON_FILTERS["premium_terms"])


def passes_decathlon_filter(title: str, price: Optional[float], discount_pct: int) -> bool:
    if price is None:
        return False
    if price < MIN_PRICE:
        return False
    if has_premium_terms(title):
        return False
    if discount_pct < DECATHLON_FILTERS["min_discount_percent"]:
        return False
    if is_bike_product(title):
        return price <= DECATHLON_FILTERS["bike_max_price"]
    return price <= DECATHLON_FILTERS["general_max_price"]


def quality_filter(product: dict) -> bool:
    if not product.get("title") or looks_like_url(product.get("title")):
        return False
    if not product.get("image") or not looks_like_image_url(product.get("image")):
        return False
    if not product.get("url") or not looks_like_url(product.get("url")):
        return False
    if product.get("price") is None:
        return False
    return True


def fetch_feed() -> Optional[str]:
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


def parse_feed(_: str) -> list[dict]:
    products: list[dict] = []
    samples: list[dict] = []
    seen: set[str] = set()

    total_products = 0
    cycling_products = 0
    with_title = 0
    with_url = 0
    with_image = 0
    with_price = 0
    filtered_out = 0
    duplicates = 0
    tag_counter: dict[str, int] = {}

    context = ET.iterparse(TMP_XML_PATH, events=("end",))

    for _, elem in context:
        tag = strip_ns(elem.tag)
        if tag not in {"product", "item", "entry"}:
            continue

        total_products += 1
        tag_counter[tag] = tag_counter.get(tag, 0) + 1

        values = get_descendant_values(elem)

        title = first_matching_value(
            values,
            [
                "name", "title", "productname", "product_name", "designation",
                "label", "libelle", "productlabel", "itemname",
            ],
            reject_urlish=True,
        )
        brand = first_matching_value(values, ["brand", "manufacturer", "marque", "vendor"])
        url = first_matching_value(
            values,
            [
                "url", "link", "product_url", "producturl", "deeplink",
                "tracking_url", "buyurl", "productlink", "aw_deep_link",
            ],
            want_url=True,
        )
        image = first_matching_value(
            values,
            [
                "image", "image_url", "imageurl", "image_link", "imagelink",
                "large_image", "small_image", "picture", "media", "medialink",
            ],
            want_image=True,
        )

        price = None
        for candidate in [
            first_matching_value(values, ["sale_price", "current_price", "price", "final_price", "promo_price", "offer_price", "best_price", "discount_price", "price_sale"]),
            first_matching_value(values, ["priceamount", "amount", "saleprice", "unit_price"]),
        ]:
            price = safe_float(candidate)
            if price is not None:
                break

        old_price = None
        for candidate in [
            first_matching_value(values, ["retail_price", "original_price", "old_price", "oldprice", "price_before", "regular_price", "list_price", "price_original"]),
            first_matching_value(values, ["crossed_price", "rrp", "recommended_price"]),
        ]:
            old_price = safe_float(candidate)
            if old_price is not None:
                break

        category_hint = first_matching_value(values, ["product_nature", "nature", "category", "categorie", "breadcrumb", "sport", "universe"])

        url = clean_tracking_url(url)
        image = clean_tracking_url(image)

        if not title:
            title = title_from_url(url)

        if title:
            with_title += 1
        if url:
            with_url += 1
        if image:
            with_image += 1
        if price is not None:
            with_price += 1

        text_for_detection = " ".join([title, brand, category_hint, collect_all_text(values)])
        if not is_cycling(text_for_detection):
            elem.clear()
            continue

        cycling_products += 1

        key = url or f"{title}|{price}"
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
            "recomendacion": discount_pct if discount_pct else (1000 - (price or 0)),
            "detail_enabled": False,
        }

        valid = quality_filter(product) and passes_decathlon_filter(title, price, discount_pct)
        if valid:
            products.append(product)
            if len(samples) < 10:
                samples.append(product)
        else:
            filtered_out += 1
            if len(samples) < 10:
                samples.append({
                    "debug_discarded": True,
                    "title": title,
                    "url": url,
                    "image": image,
                    "price": price,
                    "old_price": old_price,
                    "discount_pct": discount_pct,
                    "category_hint": category_hint,
                })

        elem.clear()

    DEBUG_SAMPLE_PATH.write_text(json.dumps({"samples": samples, "product_tags": tag_counter}, ensure_ascii=False, indent=2), encoding="utf-8")

    log(f"[INFO] Productos XML totales: {total_products}")
    log(f"[INFO] Productos con título: {with_title}")
    log(f"[INFO] Productos con URL: {with_url}")
    log(f"[INFO] Productos con imagen: {with_image}")
    log(f"[INFO] Productos con precio detectado: {with_price}")
    log(f"[INFO] Productos ciclismo detectados: {cycling_products}")
    log(f"[INFO] Duplicados descartados: {duplicates}")
    log(f"[INFO] Productos descartados por quality/filter: {filtered_out}")
    log(f"[INFO] Productos válidos antes de limitar: {len(products)}")

    products.sort(
        key=lambda x: (
            x.get("discount_pct", 0),
            -(x.get("price") or 0),
        ),
        reverse=True,
    )
    return products[:MAX_PRODUCTS]


def save(products: list[dict]) -> None:
    ensure_dirs()
    tmp = OUTPUT_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(OUTPUT_PATH)


def main() -> None:
    raw = fetch_feed()
    if not raw:
        log("[WARN] No se pudo obtener feed")
        return

    products = parse_feed(raw)
    save(products)
    log(f"Productos Decathlon finales: {len(products)}")


if __name__ == "__main__":
    main()
