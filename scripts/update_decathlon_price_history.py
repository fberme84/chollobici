import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

DATA_DIR = Path("data")
PRODUCTS_FILE = DATA_DIR / "decathlon_products.json"
HISTORY_FILE = DATA_DIR / "decathlon_price_history.json"
CHANGES_FILE = DATA_DIR / "decathlon_price_changes.json"
MAX_DAYS = 120


def safe_float(value):
    if value is None or value == "":
        return None
    try:
        text = str(value).replace("€", "").replace("%", "").replace("\u00a0", " ").strip()
        # Formatos habituales: 1.299,99 / 1299,99 / 1299.99
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
        return round(float(text), 2)
    except Exception:
        return None


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data
    except Exception as exc:
        print(f"⚠️ No se pudo leer {path}: {exc}")
        return default


def product_key(product):
    return str(
        product.get("sku")
        or product.get("product_id")
        or product.get("id")
        or product.get("url")
        or product.get("affiliate_url")
    ).strip()


def normalize_history_entry(entry):
    """Compatibilidad con formatos previos: prices[] o history[]."""
    if not isinstance(entry, dict):
        return []
    prices = entry.get("prices")
    if prices is None:
        prices = entry.get("history", [])
    normalized = []
    for item in prices or []:
        if not isinstance(item, dict):
            continue
        price = safe_float(item.get("price"))
        date = str(item.get("date") or "").strip()
        if date and price is not None:
            normalized.append({"date": date, "price": price})
    normalized.sort(key=lambda x: x["date"])
    return normalized[-MAX_DAYS:]


def pct_change(old, new):
    if not old:
        return None
    return round((new - old) / old * 100, 2)


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    products = load_json(PRODUCTS_FILE, [])
    history = load_json(HISTORY_FILE, {})

    if not isinstance(products, list):
        raise SystemExit("❌ data/decathlon_products.json no contiene una lista de productos")
    if not isinstance(history, dict):
        history = {}

    changes = []
    stats = {
        "date": today,
        "products_read": len(products),
        "products_with_price": 0,
        "new_products": 0,
        "price_drops": 0,
        "price_rises": 0,
        "unchanged": 0,
        "updated_same_day": 0,
    }

    for product in products:
        key = product_key(product)
        if not key or key.lower() == "none":
            continue

        price = safe_float(product.get("price"))
        if price is None or price <= 0:
            continue
        stats["products_with_price"] += 1

        existing = history.get(key, {})
        prices = normalize_history_entry(existing)
        previous_price = prices[-1]["price"] if prices else None
        previous_date = prices[-1]["date"] if prices else None

        change_type = "new" if previous_price is None else "same"
        change_abs = None
        change_pct = None

        if previous_price is None:
            stats["new_products"] += 1
        else:
            change_abs = round(price - previous_price, 2)
            change_pct = pct_change(previous_price, price)
            if price < previous_price:
                change_type = "drop"
                stats["price_drops"] += 1
            elif price > previous_price:
                change_type = "rise"
                stats["price_rises"] += 1
            else:
                stats["unchanged"] += 1

        # Un punto por día. Si se ejecuta dos veces el mismo día, actualiza el valor del día.
        if prices and prices[-1]["date"] == today:
            if prices[-1]["price"] != price:
                stats["updated_same_day"] += 1
            prices[-1]["price"] = price
        else:
            prices.append({"date": today, "price": price})
        prices = prices[-MAX_DAYS:]

        all_values = [p["price"] for p in prices]
        values_30d = [p["price"] for p in prices[-30:]]
        min_price_30d = min(values_30d) if values_30d else price
        min_price_all = min(all_values) if all_values else price

        history[key] = {
            "source": "decathlon",
            "id": product.get("id") or product.get("url"),
            "sku": product.get("sku"),
            "title": product.get("title"),
            "url": product.get("url"),
            "affiliate_url": product.get("affiliate_url"),
            "image": product.get("image"),
            "last_price": price,
            "previous_price": previous_price,
            "last_seen": today,
            "min_price_30d": round(min_price_30d, 2),
            "min_price_all": round(min_price_all, 2),
            "avg_price_30d": round(mean(values_30d), 2) if values_30d else price,
            "is_recent_min_price": price <= min_price_30d,
            "prices": prices,
        }

        if change_type in {"drop", "rise"}:
            changes.append({
                "date": today,
                "type": change_type,
                "id": product.get("id") or key,
                "sku": product.get("sku"),
                "title": product.get("title"),
                "url": product.get("url"),
                "affiliate_url": product.get("affiliate_url"),
                "image": product.get("image"),
                "previous_date": previous_date,
                "previous_price": previous_price,
                "new_price": price,
                "change_abs": change_abs,
                "change_pct": change_pct,
                "min_price_30d": round(min_price_30d, 2),
                "min_price_all": round(min_price_all, 2),
                "is_recent_min_price": price <= min_price_30d,
            })

    changes.sort(key=lambda x: (x["type"] != "drop", abs(x.get("change_pct") or 0)), reverse=False)
    # Mejor: bajadas primero y mayor % de bajada antes.
    changes = sorted(changes, key=lambda x: (0 if x["type"] == "drop" else 1, x.get("change_pct") or 0))

    output = {
        "summary": stats,
        "changes": changes,
        "drops": [c for c in changes if c["type"] == "drop"],
        "rises": [c for c in changes if c["type"] == "rise"],
    }

    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
    CHANGES_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    print("===== DECATHLON PRICE HISTORY =====")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print(f"Histórico actualizado: {HISTORY_FILE}")
    print(f"Cambios del día guardados en: {CHANGES_FILE}")

    if not changes:
        print("➖ No se han detectado cambios de precio respecto al último valor guardado.")
    else:
        print("===== CAMBIOS DE PRECIO DETECTADOS =====")
        for change in changes[:50]:
            icon = "🔻 BAJADA" if change["type"] == "drop" else "🔺 SUBIDA"
            print(
                f"{icon}: {change.get('title')} | "
                f"{change.get('previous_price')}€ → {change.get('new_price')}€ "
                f"({change.get('change_pct')}%)"
            )
        if len(changes) > 50:
            print(f"... y {len(changes) - 50} cambios más. Ver {CHANGES_FILE}")
    print("====================================")


if __name__ == "__main__":
    main()
