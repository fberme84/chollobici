from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEALS_FILE = DATA_DIR / "generated_deals.json"
HISTORY_FILE = DATA_DIR / "history.json"
AMAZON_PRODUCTS_FILE = DATA_DIR / "amazon_products.json"
ALIEXPRESS_PRODUCTS_FILE = DATA_DIR / "aliexpress_products.json"

AMAZON_TAG = os.getenv("AMAZON_PARTNER_TAG", "").strip()
TODAY_UTC = datetime.now(timezone.utc)
TODAY_DATE = TODAY_UTC.date().isoformat()
NOW_ISO = TODAY_UTC.replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def add_amazon_tag(url: str, tag: str) -> str:
    if not url or not tag:
        return url

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["tag"] = tag

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            urlencode(query),
            parsed.fragment,
        )
    )


def load_catalog_products(path: Path, *, default_store: str, tag_amazon: bool = False) -> list[dict]:
    raw_items = load_json(path, [])
    products: list[dict] = []

    for item in raw_items:
        product_id = item.get("id")
        title = item.get("title")
        category = item.get("category", default_store)
        url = item.get("url")
        image = item.get("image", "")
        source = item.get("source", "manual")
        last_checked = item.get("last_checked") or TODAY_DATE
        editor_pick = bool(item.get("editor_pick", False))

        if not product_id or not title or not url:
            continue

        try:
            price = float(item.get("price"))
        except (TypeError, ValueError):
            continue

        try:
            old_price = float(item["old_price"]) if item.get("old_price") not in (None, "") else None
        except (TypeError, ValueError):
            old_price = None

        manual_visibility = bool(item.get("manual_visibility", False))
        suspicious_price = False
        suspicious_reason = None
        if price <= 0:
            if not manual_visibility:
                suspicious_price = True
                suspicious_reason = "Precio no válido"
        elif old_price and old_price > 0 and price < old_price * 0.4:
            suspicious_price = True
            suspicious_reason = "Precio sospechosamente bajo frente al anterior"

        discount_pct = 0
        if old_price and old_price > price:
            discount_pct = round((old_price - price) / old_price * 100)

        products.append(
            {
                "id": product_id,
                "title": title,
                "store": item.get("store", default_store),
                "category": category,
                "price": round(price, 2),
                "old_price": round(old_price, 2) if old_price else None,
                "discount_pct": discount_pct,
                "url": url,
                "affiliate_url": add_amazon_tag(url, AMAZON_TAG) if tag_amazon else item.get("affiliate_url", url),
                "image": image,
                "updated_at": NOW_ISO,
                "last_checked": last_checked,
                "source": source,
                "editor_pick": editor_pick,
                "manual_visibility": manual_visibility,
                "status": "hot" if discount_pct >= 20 else "normal",
                "suspicious_price": suspicious_price,
                "suspicious_reason": suspicious_reason,
                "reason": item.get("reason"),
            }
        )

    return products


def update_history(history: dict[str, list[dict]], products: list[dict]) -> dict[str, list[dict]]:
    for product in products:
        product_id = product["id"]
        history.setdefault(product_id, [])

        if history[product_id] and history[product_id][-1]["date"] == TODAY_DATE:
            history[product_id][-1]["price"] = product["price"]
        else:
            history[product_id].append({"date": TODAY_DATE, "price": product["price"]})

        history[product_id] = history[product_id][-30:]

    return history


def build_deals(products: list[dict], history: dict[str, list[dict]]) -> list[dict]:
    deals: list[dict] = []
    suspicious_count = 0

    for product in products:
        if product.get("suspicious_price"):
            suspicious_count += 1
            print(f"[WARN] {product['title']}: {product['suspicious_reason']}")
            continue

        points = history.get(product["id"], [])
        previous_price = points[-2]["price"] if len(points) >= 2 else None
        drop_vs_previous_pct = 0

        if previous_price and previous_price > product["price"]:
            drop_vs_previous_pct = round((previous_price - product["price"]) / previous_price * 100)

        visible_discount = product.get("discount_pct", 0) or 0
        publish = visible_discount >= 15 or drop_vs_previous_pct >= 10
        price_missing = not product.get("price") or float(product.get("price", 0)) <= 0

        if price_missing and product.get("manual_visibility"):
            publish = True

        if not publish:
            continue

        if price_missing:
            reason = product.get("reason") or "Enlace añadido manualmente. Precio pendiente de revisión."
        elif drop_vs_previous_pct >= visible_discount and drop_vs_previous_pct > 0:
            reason = f"Precio {drop_vs_previous_pct}% por debajo del último valor guardado."
        else:
            reason = f"Descuento visible del {visible_discount}% frente al precio anterior."

        recomendacion = (visible_discount * 2) + (drop_vs_previous_pct * 4) + (10 if product.get("editor_pick") else 0)
        if price_missing:
            recomendacion = max(recomendacion, 35 + (10 if product.get("editor_pick") else 0))
        recomendacion = max(0, min(recomendacion, 100))

        enriched = {
            **product,
            "previous_price": previous_price,
            "drop_vs_previous_pct": drop_vs_previous_pct,
            "status": "hot" if max(visible_discount, drop_vs_previous_pct) >= 20 else "normal",
            "reason": reason,
            "recomendacion": recomendacion,
        }
        deals.append(enriched)

    deals.sort(
        key=lambda x: (x.get("recomendacion", 0), x.get("price", 0)),
        reverse=True,
    )

    print(f"Productos descartados por precio sospechoso: {suspicious_count}")
    return deals


def main() -> None:
    history = load_json(HISTORY_FILE, {})
    products = []
    products.extend(load_catalog_products(AMAZON_PRODUCTS_FILE, default_store="Amazon", tag_amazon=True))
    products.extend(load_catalog_products(ALIEXPRESS_PRODUCTS_FILE, default_store="AliExpress", tag_amazon=False))
    history = update_history(history, products)
    deals = build_deals(products, history)

    save_json(DEALS_FILE, deals)
    save_json(HISTORY_FILE, history)

    amazon_count = len(load_json(AMAZON_PRODUCTS_FILE, []))
    aliexpress_count = len(load_json(ALIEXPRESS_PRODUCTS_FILE, []))
    print(f"Productos Amazon leídos: {amazon_count}")
    print(f"Productos AliExpress leídos: {aliexpress_count}")
    print(f"Productos totales procesados: {len(products)}")
    print(f"Ofertas publicadas: {len(deals)}")


if __name__ == "__main__":
    main()
