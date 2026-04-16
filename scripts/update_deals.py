from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DECATHLON_PATH = ROOT / "data" / "decathlon_products.json"
ALIEXPRESS_PATH = ROOT / "data" / "aliexpress_products.json"
OUTPUT_PATH = ROOT / "data" / "generated_deals.json"
SUMMARY_PATH = ROOT / "data" / "merge_summary.json"

MAX_DECATHLON = 100
MAX_ALIEXPRESS = 60
MAX_TOTAL = 160


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception as exc:
        print(f"[WARN] No se pudo leer {path.name}: {exc}")
        return []


def safe_float(value) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(str(value).replace("%", "").replace(",", "."))
    except Exception:
        return 0.0


def compute_discount_pct(product: dict) -> int:
    explicit = product.get("discount_pct")
    try:
        explicit_num = int(float(explicit))
        if explicit_num > 0:
            return explicit_num
    except Exception:
        pass

    # Para AliExpress el campo suele venir como "discount"
    ali_discount = product.get("discount")
    try:
        ali_discount_num = int(float(str(ali_discount).replace("%", "").replace(",", ".")))
        if ali_discount_num > 0:
            return ali_discount_num
    except Exception:
        pass

    price = safe_float(product.get("price"))
    old_price = safe_float(product.get("old_price"))
    if old_price > 0 and price > 0 and old_price >= price:
        return round((old_price - price) / old_price * 100)

    return 0


def normalize_store_label(product: dict, default_store: str) -> dict:
    product["source"] = default_store.lower()
    product["source_label"] = default_store
    return product


def normalize_product(product: dict, default_store: str) -> dict:
    p = dict(product)

    normalize_store_label(p, default_store)

    p["title"] = str(p.get("title") or "").strip()
    p["brand"] = str(p.get("brand") or p.get("shop_name") or "").strip()
    p["category"] = str(p.get("category") or "ciclismo").strip()
    p["category_hint"] = str(p.get("category_hint") or p.get("category") or "").strip()
    p["image"] = str(p.get("image") or "").strip()
    p["url"] = str(p.get("url") or "").strip()
    p["affiliate_url"] = str(p.get("affiliate_url") or p.get("url") or "").strip()
    p["price"] = safe_float(p.get("price"))
    p["old_price"] = safe_float(p.get("old_price"))
    p["discount_pct"] = compute_discount_pct(p)
    p["detail_enabled"] = bool(p.get("detail_enabled", False))

    if not p.get("id"):
        p["id"] = (
            p.get("product_id")
            or p.get("sku")
            or p.get("affiliate_url")
            or p.get("url")
            or p["title"]
        )

    return p


def is_valid_product(product: dict) -> bool:
    title = (product.get("title") or "").lower()
    category_hint = (product.get("category_hint") or "").lower()
    text = f"{title} {category_hint}"

    blocked_terms = [
        "futbol",
        "fútbol",
        "yoga",
        "baloncesto",
        "beisbol",
        "béisbol",
        "natacion",
        "natación",
        "pesca",
        "padel",
        "pádel",
        "boxeo",
        "judo",
        "voleibol",
        "running",
        "esqui",
        "esquí",
        "surf",
        "bikini",
        "peluca",
        "pelucas",
        "peluquin",
        "maquillaje",
        "uñas",
        "coche",
        "moto",
        "motocicleta",
    ]

    if any(term in text for term in blocked_terms):
        return False

    if not product.get("title"):
        return False
    if not product.get("image"):
        return False
    if not product.get("affiliate_url"):
        return False
    if product.get("price", 0) <= 0:
        return False

    return True


def dedupe_products(products: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []

    for product in products:
        key = str(
            product.get("id")
            or product.get("affiliate_url")
            or product.get("url")
            or product.get("title")
        ).strip()

        if not key or key in seen:
            continue

        seen.add(key)
        result.append(product)

    return result


def sort_products(products: list[dict]) -> list[dict]:
    return sorted(
        products,
        key=lambda x: (
            x.get("discount_pct", 0),     # más descuento arriba
            -safe_float(x.get("price")),  # empate: algo de preferencia a precio más alto
        ),
        reverse=True,
    )


def main() -> None:
    decathlon_raw = load_json(DECATHLON_PATH)
    aliexpress_raw = load_json(ALIEXPRESS_PATH)

    decathlon_products = [
        normalize_product(item, "Decathlon")
        for item in decathlon_raw
    ]
    aliexpress_products = [
        normalize_product(item, "AliExpress")
        for item in aliexpress_raw
    ]

    decathlon_products = [p for p in decathlon_products if is_valid_product(p)]
    aliexpress_products = [p for p in aliexpress_products if is_valid_product(p)]

    decathlon_products = dedupe_products(decathlon_products)
    aliexpress_products = dedupe_products(aliexpress_products)

    decathlon_products = sort_products(decathlon_products)[:MAX_DECATHLON]
    aliexpress_products = sort_products(aliexpress_products)[:MAX_ALIEXPRESS]

    all_products = decathlon_products + aliexpress_products
    all_products = dedupe_products(all_products)
    all_products = sort_products(all_products)[:MAX_TOTAL]

    OUTPUT_PATH.write_text(
        json.dumps(all_products, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    summary = {
        "decathlon_loaded": len(decathlon_raw),
        "aliexpress_loaded": len(aliexpress_raw),
        "decathlon_published": len(decathlon_products),
        "aliexpress_published": len(aliexpress_products),
        "total_published": len(all_products),
    }

    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Productos Decathlon publicados: {len(decathlon_products)}")
    print(f"Productos AliExpress publicados: {len(aliexpress_products)}")
    print(f"Ofertas publicadas: {len(all_products)}")


if __name__ == "__main__":
    main()