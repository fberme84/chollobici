from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aliexpress_api import AliExpressApiError, generate_affiliate_links, product_query

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
KEYWORDS_FILE = DATA_DIR / "aliexpress_keywords.json"
PRODUCTS_FILE = DATA_DIR / "aliexpress_products.json"

TODAY_UTC = datetime.now(timezone.utc)
TODAY_DATE = TODAY_UTC.date().isoformat()

BLOCKED_TERMS = [
    "zapato", "zapatos", "plantilla", "plantillas", "sandalia", "sandalias",
    "running", "baloncesto", "futbol", "tenis", "yoga", "gym", "fitness mujer",
    "peluca", "pelucas", "peluquin", "maquillaje", "uñas", "smartwatch",
    "telefono", "movil", "tablet", "coche", "moto", "motocicleta",
]

BOOST_TERMS = [
    "bicicleta", "ciclismo", "mtb", "bike", "bici", "carretera",
    "casco", "culotte", "maillot", "pedales", "portabidon", "bidon",
    "manillar", "sillin", "cubierta", "camara", "parches", "bomba",
    "luz", "guantes", "chaleco", "chaqueta", "cinta", "calas",
]

ALLOWED_CATEGORY_TERMS = [
    "deportes", "sport", "sports", "ciclismo", "bike", "bicycle", "bicicleta",
    "accesorios para bicicletas", "cycling",
]


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")


def parse_price(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)

    text = str(value).strip()
    text = text.replace("€", "").replace("EUR", "").replace("US $", "").replace("$", "")
    text = text.replace("\xa0", " ").strip()

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif text.count(",") == 1 and text.count(".") == 0:
        text = text.replace(",", ".")

    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return round(float(match.group(0)), 2)


def first_non_empty(item: dict[str, Any], *keys: str):
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def is_relevant_product(item: dict[str, Any]) -> bool:
    title = str(first_non_empty(item, "product_title", "productTitle") or "").lower()
    category = str(first_non_empty(item, "second_level_category_name", "secondLevelCategoryName") or "").lower()
    first_cat = str(first_non_empty(item, "first_level_category_name", "firstLevelCategoryName") or "").lower()
    text = f"{title} {category} {first_cat}"

    if any(term in text for term in BLOCKED_TERMS):
        return False

    score = sum(1 for term in BOOST_TERMS if term in text)
    category_ok = any(term in f"{category} {first_cat}" for term in ALLOWED_CATEGORY_TERMS)
    return score >= 1 or category_ok


def product_score(item: dict[str, Any]) -> float:
    try:
        discount = float(str(item.get("discount") or "0").replace("%", ""))
    except Exception:
        discount = 0.0

    try:
        volume = float(item.get("lastest_volume") or item.get("ordersCount") or 0)
    except Exception:
        volume = 0.0

    try:
        commission = float(str(item.get("commission_rate") or "0").replace("%", ""))
    except Exception:
        commission = 0.0

    return (discount * 2) + min(volume / 1000, 20) + commission


def normalize_product(item: dict[str, Any], *, category: str, keyword: str, affiliate_url: str | None = None) -> dict[str, Any] | None:
    product_id = str(first_non_empty(item, "product_id", "productId", "item_id", "itemId") or "").strip()
    title = str(first_non_empty(item, "product_title", "productTitle") or "").strip()
    product_url = str(first_non_empty(item, "product_detail_url", "product_detail_url_https", "productUrl", "promotion_link", "promotionLink") or "").strip()
    image = str(first_non_empty(item, "product_main_image_url", "image_url", "imageUrl", "product_main_image_url_https") or "").strip()

    if not product_id or not title or not product_url:
        return None

    sale_price = parse_price(first_non_empty(item, "target_sale_price", "sale_price", "salePrice", "target_sale_price_amount", "targetSalePrice"))
    original_price = parse_price(first_non_empty(item, "target_original_price", "original_price", "originalPrice"))
    discount_pct = 0
    if original_price and sale_price and original_price > sale_price:
        discount_pct = round((original_price - sale_price) / original_price * 100)

    return {
        "id": f"ali-{product_id}",
        "title": title,
        "store": "AliExpress",
        "category": category,
        "keyword": keyword,
        "price": sale_price if sale_price is not None else 0,
        "old_price": original_price,
        "discount_pct": discount_pct,
        "url": product_url,
        "affiliate_url": affiliate_url or product_url,
        "image": image,
        "source": "aliexpress_api",
        "updated_at": TODAY_UTC.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "last_checked": TODAY_DATE,
        "editor_pick": False,
        "manual_visibility": False,
        "status": "hot" if discount_pct >= 20 else "normal",
        "suspicious_price": False,
        "suspicious_reason": None,
    }


def dedupe_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for item in products:
        key = (str(item.get("product_id") or ""), str(item.get("product_title") or "").strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def main() -> None:
    tracking_id = os.getenv("ALIEXPRESS_TRACKING_ID", "").strip()
    target_currency = os.getenv("ALIEXPRESS_TARGET_CURRENCY", "EUR").strip() or "EUR"
    target_language = os.getenv("ALIEXPRESS_TARGET_LANGUAGE", "ES").strip() or "ES"
    ship_to_country = os.getenv("ALIEXPRESS_SHIP_TO_COUNTRY", "ES").strip() or "ES"
    page_size = int(os.getenv("ALIEXPRESS_PAGE_SIZE", "12"))
    max_results = int(os.getenv("ALIEXPRESS_MAX_RESULTS", "30"))

    config = load_json(KEYWORDS_FILE, [])
    if not config:
        print("No hay keywords en data/aliexpress_keywords.json")
        save_json(PRODUCTS_FILE, [])
        return

    raw_products: list[dict[str, Any]] = []
    for entry in config:
        keyword = str(entry.get("keyword", "")).strip()
        category = str(entry.get("category", "AliExpress")).strip() or "AliExpress"
        if not keyword:
            continue

        try:
            products = product_query(
                keywords=keyword,
                page_no=1,
                page_size=page_size,
                tracking_id=tracking_id,
                target_currency=target_currency,
                target_language=target_language,
                ship_to_country=ship_to_country,
            )
            print(f"Keyword '{keyword}': {len(products)} productos")
            for product in products:
                product["__keyword"] = keyword
                product["__category"] = category
            raw_products.extend(products)
        except AliExpressApiError as exc:
            print(f"[ERROR] Keyword '{keyword}': {exc}")

    raw_products = dedupe_products(raw_products)
    filtered_raw = [item for item in raw_products if is_relevant_product(item)]
    filtered_raw.sort(key=product_score, reverse=True)
    filtered_raw = filtered_raw[:max_results]
    print(f"Productos tras filtrado: {len(filtered_raw)}")

    source_urls = []
    normalized: list[dict[str, Any]] = []
    for item in filtered_raw:
        norm = normalize_product(item, category=item.get("__category", "AliExpress"), keyword=item.get("__keyword", ""))
        if norm:
            normalized.append(norm)
            source_urls.append(norm["url"])

    affiliate_map = {}
    if normalized and tracking_id:
        try:
            affiliate_map = generate_affiliate_links(source_urls, tracking_id=tracking_id)
            print(f"Links de afiliado generados: {len(affiliate_map)}")
        except AliExpressApiError as exc:
            print(f"[WARN] No se pudieron generar links de afiliado: {exc}")

    dedup: dict[str, dict[str, Any]] = {}
    for item in normalized:
        if item["url"] in affiliate_map:
            item["affiliate_url"] = affiliate_map[item["url"]]
        current = dedup.get(item["id"])
        current_score = ((current or {}).get("discount_pct", 0), (current or {}).get("price") or 0)
        item_score = (item.get("discount_pct", 0), item.get("price") or 0)
        if current is None or item_score > current_score:
            dedup[item["id"]] = item

    products = list(dedup.values())
    products.sort(key=lambda x: (x.get("discount_pct", 0), x.get("price") or 0), reverse=True)
    save_json(PRODUCTS_FILE, products)
    print(f"Productos AliExpress guardados: {len(products)}")


if __name__ == "__main__":
    main()
