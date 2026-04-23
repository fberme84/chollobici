
BLACKLIST = ["futbol","pesca","yoga","baloncesto","running","camping","moto","coche","gimnasio","boxeo"]
WHITELIST = ["bici","bicicleta","ciclismo","mtb","xco","carretera","gravel","casco","culotte","maillot","pedales","sillin","inflador","portabidon","gafas"]

def is_valid_product(title):
    t = title.lower()
    if any(b in t for b in BLACKLIST):
        return False
    if any(w in t for w in WHITELIST):
        return True
    return True

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from aliexpress_api import AliExpressApiError, generate_affiliate_links, product_query


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KEYWORDS_FILE = DATA_DIR / "aliexpress_keywords.json"
OUTPUT_FILE = DATA_DIR / "aliexpress_products.json"

TRACKING_ID = (os.getenv("ALIEXPRESS_TRACKING_ID") or "").strip()


BLOCKED_TERMS = [
    "peluca", "pelucas", "peluquin",
    "maquillaje", "uñas",
    "coche", "moto", "motocicleta"
]


def load_keywords() -> List[Dict[str, str]]:
    if not KEYWORDS_FILE.exists():
        return [
            {"keyword": "casco ciclismo mtb", "category": "Cascos"},
            {"keyword": "gafas ciclismo polarizadas", "category": "Gafas"},
            {"keyword": "maillot ciclismo hombre", "category": "Ropa"},
            {"keyword": "culotte ciclismo hombre", "category": "Ropa"},
            {"keyword": "bolsa manillar bicicleta", "category": "Bolsas"},
            {"keyword": "multiherramienta bicicleta", "category": "Herramientas"},
            {"keyword": "bomba bicicleta", "category": "Herramientas"},
            {"keyword": "luz bicicleta usb", "category": "Luces"},
        ]

    with KEYWORDS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    result: List[Dict[str, str]] = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.strip():
                result.append({"keyword": item.strip(), "category": ""})
            elif isinstance(item, dict):
                kw = str(item.get("keyword") or "").strip()
                cat = str(item.get("category") or "").strip()
                if kw:
                    result.append({"keyword": kw, "category": cat})

    return result


def is_relevant_product(product: Dict[str, Any], expected_category: str = "") -> bool:
    title = (product.get("product_title") or "").lower()
    category = (product.get("second_level_category_name") or "").lower()
    first_cat = (product.get("first_level_category_name") or "").lower()
    text = f"{title} {category} {first_cat}"

    if any(term in text for term in BLOCKED_TERMS):
        return False

    return True


def dedupe_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []

    for p in products:
        key = str(p.get("product_id") or "")
        if not key:
            key = (p.get("product_title") or "").strip().lower()

        if key in seen:
            continue

        seen.add(key)
        out.append(p)

    return out


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return default


def product_score(product: Dict[str, Any]) -> float:
    discount = to_float(product.get("discount"), 0.0)
    volume = to_float(product.get("lastest_volume"), 0.0)
    commission = to_float(product.get("commission_rate"), 0.0)

    return discount * 2 + min(volume / 1000, 20) + commission


def canonical_aliexpress_url(url: str) -> str:
    if not url:
        return ""

    m = re.search(r"(https://[a-z]{2}\.aliexpress\.com/item/\d+\.html)", url)
    if m:
        return m.group(1)

    m = re.search(r"(https://www\.aliexpress\.com/item/\d+\.html)", url)
    if m:
        return m.group(1)

    return url.split("?", 1)[0].strip()


def normalize_product(product: Dict[str, Any], affiliate_map: Dict[str, str], fallback_category: str = "") -> Dict[str, Any]:
    raw_detail_url = product.get("product_detail_url") or ""
    detail_url = canonical_aliexpress_url(raw_detail_url)

    affiliate_url = affiliate_map.get(detail_url) or product.get("promotion_link") or detail_url

    image = (
        product.get("product_main_image_url")
        or (product.get("product_small_image_urls") or [""])[0]
        or ""
    )

    price = product.get("target_sale_price") or product.get("sale_price") or ""
    old_price = product.get("target_original_price") or product.get("original_price") or ""
    currency = product.get("target_sale_price_currency") or product.get("sale_price_currency") or "EUR"

    return {
        "id": str(product.get("product_id") or ""),
        "title": product.get("product_title") or "",
        "url": affiliate_url,
        "affiliate_url": affiliate_url,
        "product_detail_url": detail_url,
        "image": image,
        "price": str(price),
        "old_price": str(old_price),
        "currency": currency,
        "discount": product.get("discount") or "",
        "source": "aliexpress",
        "source_label": "AliExpress",
        "category": fallback_category or product.get("second_level_category_name") or product.get("first_level_category_name") or "",
        "shop_name": product.get("shop_name") or "",
        "rating": product.get("evaluate_rate") or "",
        "sales": product.get("lastest_volume") or 0,
        "commission_rate": product.get("commission_rate") or "",
    }


def chunked(seq: List[str], size: int):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    keyword_items = load_keywords()
    if not keyword_items:
        raise SystemExit("No hay keywords válidas en data/aliexpress_keywords.json")

    all_products: List[Dict[str, Any]] = []
    category_by_product_id: Dict[str, str] = {}

    print(f"Tracking ID configurado: {'sí' if TRACKING_ID else 'no'}")

    for item in keyword_items:
        keyword = item["keyword"]
        expected_category = item.get("category", "")

        print(f"Buscando en AliExpress: {item}")

        try:
            products = product_query(
                keywords=keyword,
                page_no=1,
                page_size=20,
                target_currency="EUR",
                target_language="ES",
                ship_to_country="ES",
            )
        except AliExpressApiError as exc:
            print(f"ERROR API con keyword '{keyword}': {exc}")
            continue
        except Exception as exc:
            print(f"ERROR inesperado con keyword '{keyword}': {exc}")
            continue

        if not products:
            print("  Sin resultados")
            continue

        sample = products[0]
        print(f"  Ejemplo título: {(sample.get('product_title') or '')[:120]}")
        print(f"  Ejemplo categoría 1: {sample.get('first_level_category_name')}")
        print(f"  Ejemplo categoría 2: {sample.get('second_level_category_name')}")

        filtered = [p for p in products if is_relevant_product(p, expected_category)]

        print(f"  Productos recibidos: {len(products)} | filtrados: {len(filtered)}")

        for p in filtered:
            pid = str(p.get("product_id") or "")
            if pid and expected_category and pid not in category_by_product_id:
                category_by_product_id[pid] = expected_category

        filtered.sort(key=product_score, reverse=True)
        all_products.extend(filtered[:5])

    all_products = dedupe_products(all_products)
    all_products.sort(key=product_score, reverse=True)
    all_products = all_products[:40]

    detail_urls = []
    for p in all_products:
        url = canonical_aliexpress_url(p.get("product_detail_url") or "")
        if url:
            detail_urls.append(url)

    detail_urls = list(dict.fromkeys(detail_urls))[:40]

    affiliate_map: Dict[str, str] = {}
    if detail_urls and TRACKING_ID:
        total_batches = 0
        failed_batches = 0

        for batch in chunked(detail_urls, 1):
            try:
                batch_map = generate_affiliate_links(batch, tracking_id=TRACKING_ID)
                affiliate_map.update(batch_map)
                total_batches += 1
            except Exception as exc:
                failed_batches += 1
                print(f"ERROR generando affiliate links para lote {batch}: {exc}")

        print(f"Links afiliados generados: {len(affiliate_map)} en {total_batches} lotes; fallidos: {failed_batches}")
    else:
        print("Sin TRACKING_ID o sin URLs; se usarán promotion_link/product_detail_url")

    normalized = []
    for p in all_products:
        pid = str(p.get("product_id") or "")
        fallback_category = category_by_product_id.get(pid, "")
        normalized.append(normalize_product(p, affiliate_map, fallback_category=fallback_category))

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_FILE} con {len(normalized)} productos")


if __name__ == "__main__":
    main()
