from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEALS_FILE = DATA_DIR / "deals.json"
HISTORY_FILE = DATA_DIR / "history.json"
AMAZON_PRODUCTS_FILE = DATA_DIR / "amazon_products.json"

AMAZON_TAG = os.getenv("AMAZON_PARTNER_TAG", "").strip()


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


def load_amazon_products() -> list[dict]:
    raw_items = load_json(AMAZON_PRODUCTS_FILE, [])
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    products: list[dict] = []

    for item in raw_items:
        product_id = item.get("id")
        title = item.get("title")
        category = item.get("category", "Amazon")
        url = item.get("url")
        image = item.get("image", "")

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

        discount_pct = 0
        if old_price and old_price > price:
            discount_pct = round((old_price - price) / old_price * 100)

        products.append(
            {
                "id": product_id,
                "title": title,
                "store": "Amazon",
                "category": category,
                "price": round(price, 2),
                "old_price": round(old_price, 2) if old_price else None,
                "discount_pct": discount_pct,
                "url": url,
                "affiliate_url": add_amazon_tag(url, AMAZON_TAG),
                "image": image,
                "updated_at": now_iso,
                "status": "hot" if discount_pct >= 20 else "normal",
            }
        )

    return products


def update_history(history: dict[str, list[dict]], products: list[dict]) -> dict[str, list[dict]]:
    today = datetime.now(timezone.utc).date().isoformat()

    for product in products:
        product_id = product["id"]
        history.setdefault(product_id, [])

        if history[product_id] and history[product_id][-1]["date"] == today:
            history[product_id][-1]["price"] = product["price"]
        else:
            history[product_id].append({"date": today, "price": product["price"]})

        history[product_id] = history[product_id][-30:]

    return history


def build_deals(products: list[dict], history: dict[str, list[dict]]) -> list[dict]:
    deals: list[dict] = []

    for product in products:
        points = history.get(product["id"], [])
        previous_price = points[-2]["price"] if len(points) >= 2 else None
        drop_vs_previous_pct = 0

        if previous_price and previous_price > product["price"]:
            drop_vs_previous_pct = round((previous_price - product["price"]) / previous_price * 100)

        visible_discount = product.get("discount_pct", 0) or 0
        publish = visible_discount >= 15 or drop_vs_previous_pct >= 10

        if not publish:
            continue

        if drop_vs_previous_pct >= visible_discount:
            reason = f"Precio {drop_vs_previous_pct}% por debajo del último valor guardado."
        else:
            reason = f"Descuento visible del {visible_discount}% frente al precio anterior."

        enriched = {
            **product,
            "previous_price": previous_price,
            "drop_vs_previous_pct": drop_vs_previous_pct,
            "status": "hot" if max(visible_discount, drop_vs_previous_pct) >= 20 else "normal",
            "reason": reason,
        }
        deals.append(enriched)

    deals.sort(
        key=lambda x: (max(x.get("discount_pct", 0), x.get("drop_vs_previous_pct", 0)), x.get("price", 0)),
        reverse=True,
    )
    return deals


def main() -> None:
    history = load_json(HISTORY_FILE, {})
    products = load_amazon_products()
    history = update_history(history, products)
    deals = build_deals(products, history)

    save_json(DEALS_FILE, deals)
    save_json(HISTORY_FILE, history)

    print(f"Productos Amazon leídos: {len(products)}")
    print(f"Ofertas publicadas: {len(deals)}")


if __name__ == "__main__":
    main()
