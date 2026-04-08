import json
import os
from pathlib import Path
from typing import Any, Dict, List

from aliexpress_api import AliExpressApiError, generate_affiliate_links, product_query


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
KEYWORDS_FILE = DATA_DIR / "aliexpress_keywords.json"
OUTPUT_FILE = DATA_DIR / "aliexpress_products.json"

TRACKING_ID = (os.getenv("ALIEXPRESS_TRACKING_ID") or "").strip()


BLOCKED_TERMS = [
    "zapato", "zapatos", "plantilla", "plantillas", "sandalia", "sandalias",
    "running", "baloncesto", "futbol", "tenis", "yoga", "gym", "fitness mujer",
    "peluca", "pelucas", "peluquin", "maquillaje", "uñas", "smartwatch",
    "telefono", "movil", "tablet", "coche", "moto", "motocicleta"
]

BOOST_TERMS = [
    "bicicleta", "ciclismo", "mtb", "bike", "bici", "carretera",
    "casco", "culotte", "maillot", "pedales", "portabidon", "bidon",
    "manillar", "sillin", "cubierta", "camara", "parches", "bomba",
    "luz", "guantes", "chaleco", "chaqueta", "cinta", "calas",
    "herramienta", "multiherramienta", "soporte movil"
]

ALLOWED_CATEGORY_TERMS = [
    "deportes", "sport", "sports", "ciclismo", "bike", "bicycle", "bicicleta"
]


def load_keywords() -> List[str]:
    if not KEYWORDS_FILE.exists():
        return [
            "casco ciclismo mtb",
            "gafas ciclismo polarizadas",
            "maillot ciclismo hombre",
            "culotte ciclismo hombre",
            "bolsa manillar bicicleta",
            "multiherramienta bicicleta",
            "bomba bicicleta",
            "luz bicicleta usb",
        ]

    with KEYWORDS_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]

    return []


def is_relevant_product(product: Dict[str, Any]) -> bool:
    title = (product.get("product_title") or "").lower()
    category = (product.get("second_level_category_name") or "").lower()
    first_cat = (product.get("first_level_category_name") or "").lower()
    text = f"{title} {category} {first_cat}"

    if any(term in text for term in BLOCKED_TERMS):
        return False

    score = sum(1 for term in BOOST_TERMS if term in text)
    return score >= 1


def category_ok(product: Dict[str, Any]) -> bool:
    first_cat = (product.get("first_level_category_name") or "").lower()
    second_cat = (product.get("second_level_category_name") or "").lower()
    text = f"{first_cat} {second_cat}"

    if not text.strip():
        return True

    return any(term in text for term in ALLOWED_CATEGORY_TERMS)


def dedupe_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []

    for p in products:
        key = (
            str(p.get("product_id") or ""),
            (p.get("product_title") or "").strip().lower(),
        )
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


def normalize_product(product: Dict[str, Any], affiliate_map: Dict[str, str]) -> Dict[str, Any]:
    detail_url = product.get("product_detail_url") or ""
    affiliate_url = affiliate_map.get(detail_url, product.get("promotion_link") or detail_url)

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
        "category": product.get("second_level_category_name") or product.get("first_level_category_name") or "",
        "shop_name": product.get("shop_name") or "",
        "rating": product.get("evaluate_rate") or "",
        "sales": product.get("lastest_volume") or 0,
        "commission_rate": product.get("commission_rate") or "",
    }


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    keywords = load_keywords()
    if not keywords:
        raise SystemExit("No hay keywords en data/aliexpress_keywords.json")

    all_products: List[Dict[str, Any]] = []

    for keyword in keywords:
        print(f"Buscando en AliExpress: {keyword}")
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

        filtered = [
            p for p in products
            if is_relevant_product(p) and category_ok(p)
        ]

        print(f"  Productos recibidos: {len(products)} | filtrados: {len(filtered)}")
        all_products.extend(filtered)

    all_products = dedupe_products(all_products)
    all_products.sort(key=product_score, reverse=True)
    all_products = all_products[:30]

    detail_urls = [
        p.get("product_detail_url")
        for p in all_products
        if p.get("product_detail_url")
    ]

    affiliate_map: Dict[str, str] = {}
    if detail_urls and TRACKING_ID:
        try:
            affiliate_map = generate_affiliate_links(detail_urls, tracking_id=TRACKING_ID)
            print(f"Links afiliados generados: {len(affiliate_map)}")
        except AliExpressApiError as exc:
            print(f"ERROR generando affiliate links: {exc}")
        except Exception as exc:
            print(f"ERROR inesperado generando affiliate links: {exc}")
    else:
        print("Sin TRACKING_ID o sin URLs; se usarán promotion_link/product_detail_url")

    normalized = [normalize_product(p, affiliate_map) for p in all_products]

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"Guardado {OUTPUT_FILE} con {len(normalized)} productos")


if __name__ == "__main__":
    main()