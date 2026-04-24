import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import unicodedata

DATA_DIR = Path("data")
DECATHLON_PATH = DATA_DIR / "decathlon_products.json"
ALIEXPRESS_PATH = DATA_DIR / "aliexpress_products.json"
AMAZON_PATH = DATA_DIR / "amazon_products.json"
OUTPUT_PATH = DATA_DIR / "generated_deals.json"
MERGE_SUMMARY_PATH = DATA_DIR / "merge_summary.json"
DECATHLON_PRICE_HISTORY_PATH = DATA_DIR / "decathlon_price_history.json"

MAX_TOTAL = 48
TARGET_PER_SOURCE = 18
TODAY = datetime.now(timezone.utc).date().isoformat()


def normalize_str(value) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text


def safe_float(x):
    try:
        if x is None or x == "":
            return 0.0
        return float(str(x).replace("€", "").replace("%", "").replace(",", ".").strip())
    except Exception:
        return 0.0


def money(value):
    value = safe_float(value)
    return round(value, 2) if value > 0 else 0.0


def compute_discount_pct(product):
    explicit = product.get("discount_pct")
    if explicit not in (None, "", 0, "0"):
        try:
            return int(float(str(explicit).replace("%", "").replace(",", ".").strip()))
        except Exception:
            pass

    raw_discount = str(product.get("discount") or "").replace("%", "").replace(",", ".").strip()
    if raw_discount:
        try:
            return int(float(raw_discount))
        except Exception:
            pass

    price = safe_float(product.get("price"))
    old = safe_float(product.get("old_price"))

    if old > 0 and price > 0 and price <= old:
        return round((old - price) / old * 100)
    return 0


def clean_image_url(url: str) -> str:
    text = str(url or "").strip()
    if "<" in text:
        text = text.split("<", 1)[0].strip()
    if not text:
        return "/assets/placeholder-product.svg"
    return text


def clean_text(value: str) -> str:
    text = str(value or "").strip()
    if "<" in text:
        text = text.split("<", 1)[0].strip()
    return text


def get_source(product: dict) -> str:
    text = normalize_str(product.get("source") or product.get("store") or product.get("source_label"))
    if "amazon" in text or text == "manual":
        return "amazon"
    if "decathlon" in text:
        return "decathlon"
    if "aliexpress" in text or "ali express" in text:
        return "aliexpress"
    return text or "desconocido"


def is_bike_product(title: str) -> bool:
    text = f" {normalize_str(title)} "
    return any(term in text for term in [
        " bici ", " bicicleta", " mtb", " gravel", " carretera", " rockrider",
        " triban", " van rysel", " ebike", " e-bike", " xco ", " xc ", " road bike"
    ])


def relevance_score(product: dict) -> int:
    title = normalize_str(product.get("title"))
    category_hint = normalize_str(product.get("category_hint") or product.get("category"))
    text = f"{title} {category_hint}"

    strong_terms = [
        "ciclismo", "bicicleta", "bici", "mtb", "xco", "xc", "carretera", "gravel",
        "casco", "maillot", "culotte", "guantes", "pedal", "pedales", "calas",
        "sillin", "sillín", "bidon", "bidón", "portabidon", "portabidón", "gafas",
        "cadena", "cubierta", "camara", "cámara", "freno", "rueda", "bomba",
        "inflador", "multiherramienta", "herramienta", "luz", "luces", "rodillo",
        "manillar"
    ]
    medium_terms = [
        "zapatillas", "calcetines", "bolsa", "soporte", "guardabarros", "gps",
        "ciclocomputador", "soporte movil", "portaequipajes", "retrovisor", "botella"
    ]
    weak_negative = [
        "running", "fitness", "gym", "gimnasio", "senderismo", "trekking",
        "pesca", "futbol", "baloncesto", "yoga", "boxeo", "coche", "moto"
    ]

    score = 0
    if any(term in text for term in strong_terms):
        score += 14
    if any(term in text for term in medium_terms):
        score += 6
    if is_bike_product(title):
        score += 10
    if any(term in text for term in weak_negative):
        score -= 25

    return score


def passes_base_filter(product: dict) -> bool:
    title = clean_text(product.get("title"))
    price = safe_float(product.get("price"))
    url = clean_text(product.get("affiliate_url") or product.get("url"))

    if not title or len(title) < 6:
        return False
    if price <= 0:
        return False
    if not url:
        return False
    if relevance_score(product) < 0:
        return False
    return True


def passes_decathlon_filter(product: dict) -> bool:
    if not passes_base_filter(product):
        return False

    title = normalize_str(product.get("title"))
    price = safe_float(product.get("price"))

    premium_terms = [
        "s-works", "pinarello", "cervélo", "cervelo", "dogma", "super record",
        " dura-ace ", " etap ", " axs ", " factory "
    ]
    if any(term in f" {title} " for term in premium_terms):
        return False

    if is_bike_product(title):
        return price <= 1800

    return price <= 350


def load_json(path, default=None):
    default = [] if default is None else default
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def decathlon_history_key(product: dict) -> str:
    """
    Clave estable para historial Decathlon.
    Prioridad: sku > id > url real > affiliate_url > título normalizado.
    """
    key = (
        product.get("sku")
        or product.get("id")
        or product.get("url")
        or product.get("affiliate_url")
        or normalize_str(product.get("title"))
    )
    return str(key).strip()


def history_prices(entry: dict) -> list[dict]:
    prices = entry.get("prices")
    return prices if isinstance(prices, list) else []


def previous_price_from_history(entry: dict, today: str = TODAY) -> float:
    previous = [
        item for item in history_prices(entry)
        if item.get("date") and item.get("date") < today and safe_float(item.get("price")) > 0
    ]
    if not previous:
        return 0.0
    previous.sort(key=lambda item: item.get("date"))
    return money(previous[-1].get("price"))


def min_price_from_history(entry: dict, days: int = 30, today: str = TODAY) -> float:
    try:
        cutoff = (datetime.fromisoformat(today).date() - timedelta(days=days)).isoformat()
    except Exception:
        cutoff = today

    candidates = [
        money(item.get("price"))
        for item in history_prices(entry)
        if item.get("date") and item.get("date") >= cutoff and safe_float(item.get("price")) > 0
    ]
    return min(candidates) if candidates else 0.0


def enrich_decathlon_price_history(products: list[dict]) -> tuple[list[dict], dict]:
    """
    Añade señales de histórico a productos Decathlon y actualiza data/decathlon_price_history.json.

    Campos añadidos al producto cuando aplica:
    - previous_price
    - price_drop_eur
    - price_drop_pct
    - min_price_30d
    - is_price_drop
    - price_trend_label
    """
    history = load_json(DECATHLON_PRICE_HISTORY_PATH, default={})
    if not isinstance(history, dict):
        history = {}

    enriched = []
    drops_detected = 0

    for product in products:
        p = dict(product)
        source = get_source(p)

        if source != "decathlon":
            enriched.append(p)
            continue

        current_price = money(p.get("price"))
        key = decathlon_history_key(p)
        if not key or current_price <= 0:
            enriched.append(p)
            continue

        entry = history.get(key, {})
        prev_price = previous_price_from_history(entry)
        min_30d_before_update = min_price_from_history(entry, days=30)

        if prev_price > 0:
            p["previous_price"] = prev_price

            if current_price < prev_price:
                drop_eur = round(prev_price - current_price, 2)
                drop_pct = round((drop_eur / prev_price) * 100)
                p["price_drop_eur"] = drop_eur
                p["price_drop_pct"] = drop_pct
                p["is_price_drop"] = True
                p["price_trend_label"] = f"Baja {drop_eur:.2f} €"
                drops_detected += 1
            elif current_price > prev_price:
                p["price_increase_eur"] = round(current_price - prev_price, 2)
                p["is_price_drop"] = False
                p["price_trend_label"] = "Precio sube"
            else:
                p["is_price_drop"] = False
                p["price_trend_label"] = "Precio estable"

        if min_30d_before_update > 0:
            p["min_price_30d"] = min(min_30d_before_update, current_price)
            if current_price <= min_30d_before_update:
                p["is_recent_min_price"] = True

        prices = history_prices(entry)
        # Si el workflow se ejecuta varias veces el mismo día, actualiza el registro del día.
        if prices and prices[-1].get("date") == TODAY:
            prices[-1]["price"] = current_price
        else:
            prices.append({"date": TODAY, "price": current_price})

        # Limitar histórico para que el JSON no crezca sin control.
        prices = prices[-120:]

        history[key] = {
            "source": "decathlon",
            "id": str(p.get("id") or ""),
            "sku": str(p.get("sku") or ""),
            "title": p.get("title") or "",
            "url": p.get("url") or p.get("affiliate_url") or "",
            "last_price": current_price,
            "last_seen": TODAY,
            "prices": prices,
        }

        enriched.append(p)

    save_json(DECATHLON_PRICE_HISTORY_PATH, history)

    summary = {
        "history_items": len(history),
        "drops_detected": drops_detected,
    }
    return enriched, summary


def compute_recommendation(product: dict) -> int:
    price = safe_float(product.get("price"))
    discount_pct = compute_discount_pct(product)
    rel = relevance_score(product)
    source = get_source(product)

    score = 0.0
    score += rel
    score += min(discount_pct, 70) * 1.05

    # Premiar bajadas reales detectadas por historial Decathlon.
    if product.get("is_price_drop"):
        score += min(safe_float(product.get("price_drop_pct")) * 1.2, 18)
        score += min(safe_float(product.get("price_drop_eur")) / 3, 10)

    if product.get("is_recent_min_price"):
        score += 5

    if price > 0:
        if price <= 15:
            score += 20
        elif price <= 30:
            score += 16
        elif price <= 50:
            score += 13
        elif price <= 80:
            score += 10
        elif price <= 120:
            score += 8
        elif price <= 200:
            score += 5
        elif price <= 350:
            score += 3
        elif price <= 800:
            score += 1

    if clean_image_url(product.get("image")):
        score += 2
    if clean_text(product.get("brand")):
        score += 2
    if clean_text(product.get("category_hint") or product.get("category")):
        score += 2

    sales = product.get("sales") or product.get("lastest_volume")
    try:
        sales_value = int(float(str(sales).replace(".", "").replace(",", ".")))
    except Exception:
        sales_value = 0
    score += min(sales_value / 1500, 5)

    rating = safe_float(product.get("rating") or product.get("evaluation_rating"))
    if rating:
        if rating >= 4.7:
            score += 4
        elif rating >= 4.4:
            score += 2

    if source == "amazon":
        score += 4
    elif source == "decathlon":
        score += 3
    elif source == "aliexpress":
        score += 1

    if is_bike_product(product.get("title")) and price > 1200:
        score -= 8

    return max(0, round(score))


def normalize_product(product: dict) -> dict:
    p = dict(product)
    p["title"] = clean_text(p.get("title", ""))
    p["brand"] = clean_text(p.get("brand", ""))
    p["category_hint"] = clean_text(p.get("category_hint") or p.get("category") or "")
    p["image"] = clean_image_url(p.get("image", ""))
    p["price"] = money(p.get("price"))
    old_price = money(p.get("old_price"))
    p["old_price"] = old_price if old_price > 0 else ""
    p["discount_pct"] = compute_discount_pct(p)
    p["source"] = get_source(p)
    if p["source"] == "amazon":
        p["source_label"] = "Amazon"
    elif p["source"] == "decathlon":
        p["source_label"] = "Decathlon"
    elif p["source"] == "aliexpress":
        p["source_label"] = "AliExpress"
    else:
        p["source_label"] = p.get("source_label") or p["source"].capitalize()
    return p


def sort_key(product):
    return (
        product.get("recomendacion", 0),
        relevance_score(product),
        product.get("discount_pct", 0),
        -safe_float(product.get("price"))
    )


def interleave_sources(source_map, max_total):
    pools = {k: list(v) for k, v in source_map.items()}
    order = ["amazon", "decathlon", "aliexpress"]
    result = []

    while len(result) < max_total and any(pools.values()):
        progress = False
        for source in order:
            if pools.get(source):
                result.append(pools[source].pop(0))
                progress = True
                if len(result) >= max_total:
                    break
        if not progress:
            break

    return result[:max_total]


def unique_key(product):
    return str(
        product.get("id")
        or product.get("product_id")
        or product.get("sku")
        or product.get("affiliate_url")
        or product.get("url")
        or product.get("title")
    )


def main():
    decathlon = load_json(DECATHLON_PATH)
    aliexpress = load_json(ALIEXPRESS_PATH)
    amazon = load_json(AMAZON_PATH)

    decathlon_filtered = [normalize_product(p) for p in decathlon if passes_decathlon_filter(p)]
    aliexpress_filtered = [normalize_product(p) for p in aliexpress if passes_base_filter(p)]
    amazon_filtered = [normalize_product(p) for p in amazon if passes_base_filter(p)]

    decathlon_filtered, history_summary = enrich_decathlon_price_history(decathlon_filtered)

    # Recalcular recomendación después de enriquecer histórico de Decathlon.
    for p in decathlon_filtered + aliexpress_filtered + amazon_filtered:
        p["recomendacion"] = compute_recommendation(p)

    decathlon_sorted = sorted(decathlon_filtered, key=sort_key, reverse=True)
    aliexpress_sorted = sorted(aliexpress_filtered, key=sort_key, reverse=True)
    amazon_sorted = sorted(amazon_filtered, key=sort_key, reverse=True)

    primary = interleave_sources(
        {
            "amazon": amazon_sorted[:TARGET_PER_SOURCE],
            "decathlon": decathlon_sorted[:TARGET_PER_SOURCE],
            "aliexpress": aliexpress_sorted[:TARGET_PER_SOURCE],
        },
        MAX_TOTAL
    )

    used = {unique_key(p) for p in primary}
    remaining = []
    for pool in (amazon_sorted[TARGET_PER_SOURCE:], decathlon_sorted[TARGET_PER_SOURCE:], aliexpress_sorted[TARGET_PER_SOURCE:]):
        for p in pool:
            if unique_key(p) not in used:
                remaining.append(p)
                used.add(unique_key(p))

    deals = (primary + remaining)[:MAX_TOTAL]

    summary = {
        "decathlon_read": len(decathlon),
        "aliexpress_read": len(aliexpress),
        "amazon_read": len(amazon),
        "decathlon_published": sum(1 for d in deals if d.get("source") == "decathlon"),
        "aliexpress_published": sum(1 for d in deals if d.get("source") == "aliexpress"),
        "amazon_published": sum(1 for d in deals if d.get("source") == "amazon"),
        "total_published": len(deals),
        "decathlon_price_history_items": history_summary.get("history_items", 0),
        "decathlon_price_drops_detected": history_summary.get("drops_detected", 0),
    }

    save_json(OUTPUT_PATH, deals)
    save_json(MERGE_SUMMARY_PATH, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
