from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEALS_FILE = DATA_DIR / "deals.json"
HISTORY_FILE = DATA_DIR / "history.json"


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


def fetch_products() -> list[dict]:
    """
    Sustituye esta función por llamadas reales a APIs de afiliación o feeds.
    De momento devuelve una muestra estable para probar el flujo end-to-end.
    """
    return [
        {
            "id": "amazon-shimano-pedales-xt",
            "title": "Pedales Shimano XT M8100",
            "store": "Amazon",
            "category": "Pedales",
            "price": 59.99,
            "url": "https://example.com/producto/shimano-xt",
            "affiliate_url": "https://example.com/afiliado/shimano-xt",
            "image": "https://placehold.co/640x400?text=Pedales+Shimano+XT",
        },
        {
            "id": "aliexpress-gafas-fotocromaticas-mtb",
            "title": "Gafas fotocromáticas MTB",
            "store": "AliExpress",
            "category": "Accesorios",
            "price": 18.49,
            "url": "https://example.com/producto/gafas-mtb",
            "affiliate_url": "https://example.com/afiliado/gafas-mtb",
            "image": "https://placehold.co/640x400?text=Gafas+MTB",
        },
        {
            "id": "bike-discount-casco-enduro",
            "title": "Casco Enduro Trail Pro",
            "store": "Bike-Discount",
            "category": "Cascos",
            "price": 74.95,
            "url": "https://example.com/producto/casco-enduro",
            "affiliate_url": "https://example.com/afiliado/casco-enduro",
            "image": "https://placehold.co/640x400?text=Casco+Enduro",
        },
    ]


def build_deals(products: list[dict], history: dict[str, list[dict]]) -> tuple[list[dict], dict[str, list[dict]]]:
    today = datetime.now(timezone.utc).date().isoformat()
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    deals = []

    for product in products:
        product_id = product["id"]
        price = float(product["price"])
        points = history.get(product_id, [])

        previous_price = points[-1]["price"] if points else price

        if not points or points[-1]["date"] != today:
            points.append({"date": today, "price": price})

        points = points[-30:]
        history[product_id] = points

        historical_prices = [float(p["price"]) for p in points[:-1]] or [previous_price]
        avg_7 = mean(historical_prices[-7:]) if historical_prices else price
        old_price = max(previous_price, price)

        drop_vs_previous = 0 if previous_price <= 0 else round((previous_price - price) / previous_price * 100)
        drop_vs_avg = 0 if avg_7 <= 0 else round((avg_7 - price) / avg_7 * 100)
        discount_pct = max(drop_vs_previous, drop_vs_avg, 0)

        is_hot = discount_pct >= 20
        if drop_vs_avg >= drop_vs_previous:
            reason = f"Precio {discount_pct}% por debajo de la media reciente."
        else:
            reason = f"Precio {discount_pct}% por debajo del último valor guardado."

        if discount_pct < 10:
            continue

        deals.append(
            {
                **product,
                "old_price": round(old_price, 2),
                "discount_pct": int(discount_pct),
                "updated_at": now_iso,
                "status": "hot" if is_hot else "normal",
                "reason": reason,
            }
        )

    deals.sort(key=lambda x: (x["discount_pct"], -x["price"]), reverse=True)
    return deals, history


def main() -> None:
    history = load_json(HISTORY_FILE, {})
    products = fetch_products()
    deals, history = build_deals(products, history)
    save_json(DEALS_FILE, deals)
    save_json(HISTORY_FILE, history)
    print(f"Ofertas guardadas: {len(deals)}")


if __name__ == "__main__":
    main()
