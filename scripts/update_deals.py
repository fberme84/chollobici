import json
from pathlib import Path
import unicodedata

DATA_DIR = Path("data")
DECATHLON_PATH = DATA_DIR / "decathlon_products.json"
ALIEXPRESS_PATH = DATA_DIR / "aliexpress_products.json"
AMAZON_PATH = DATA_DIR / "amazon_products.json"
OUTPUT_PATH = DATA_DIR / "generated_deals.json"
MERGE_SUMMARY_PATH = DATA_DIR / "merge_summary.json"
DECATHLON_HISTORY_PATH = DATA_DIR / "decathlon_price_history.json"

MAX_TOTAL = 48
TARGET_PER_SOURCE = 18


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
        "s-works", "pinarello", "cervelo", "cervélo", "dogma", "super record",
        " dura-ace ", " etap ", " axs ", " factory "
    ]
    if any(term in f" {title} " for term in premium_terms):
        return False

    if is_bike_product(title):
        return price <= 1800

    return price <= 350


def load_json(path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def load_json_dict(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def decathlon_history_keys(product: dict):
    keys = []
    for value in (
        product.get("sku"),
        product.get("id"),
        product.get("url"),
        product.get("affiliate_url"),
    ):
        if value not in (None, ""):
            keys.append(str(value))
    return keys


def attach_decathlon_price_history(product: dict, history: dict) -> dict:
    if get_source(product) != "decathlon" or not history:
        return product

    entry = None
    for key in decathlon_history_keys(product):
        if key in history:
            entry = history[key]
            break

    if not isinstance(entry, dict):
        return product

    current_price = safe_float(product.get("price"))
    previous_price = safe_float(entry.get("previous_price"))
    min_price_30d = safe_float(entry.get("min_price_30d"))
    min_price_all = safe_float(entry.get("min_price_all"))
    avg_price_30d = safe_float(entry.get("avg_price_30d"))

    if previous_price > 0:
        product["previous_price"] = previous_price
        product["price_change_abs"] = round(current_price - previous_price, 2)
        product["price_change_pct"] = round((current_price - previous_price) / previous_price * 100, 2)
        product["is_price_drop"] = current_price > 0 and current_price < previous_price

    if min_price_30d > 0:
        product["min_price_30d"] = min_price_30d
        product["is_recent_min_price"] = current_price > 0 and current_price <= min_price_30d

    if min_price_all > 0:
        product["min_price_all"] = min_price_all

    if avg_price_30d > 0:
        product["avg_price_30d"] = avg_price_30d

    # Pequeño empujón al ranking si Decathlon baja de precio o está en mínimo reciente.
    bonus = 0
    if product.get("is_price_drop"):
        bonus += 14
    if product.get("is_recent_min_price"):
        bonus += 8
    if product.get("price_change_pct", 0) < 0:
        bonus += min(abs(product.get("price_change_pct", 0)) * 0.8, 12)
    if bonus:
        product["recomendacion"] = max(0, round(product.get("recomendacion", 0) + bonus))

    return product


def compute_recommendation(product: dict) -> int:
    price = safe_float(product.get("price"))
    discount_pct = compute_discount_pct(product)
    rel = relevance_score(product)
    source = get_source(product)

    score = 0.0
    score += rel
    score += min(discount_pct, 70) * 1.05

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
    p["price"] = safe_float(p.get("price"))
    old_price = safe_float(p.get("old_price"))
    p["old_price"] = old_price if old_price > 0 else ""
    p["discount_pct"] = compute_discount_pct(p)
    p["source"] = get_source(p)
    label_map = {"amazon": "Amazon", "decathlon": "Decathlon", "aliexpress": "AliExpress"}
    p["source_label"] = label_map.get(p["source"], p.get("source_label") or p["source"].capitalize())
    p["recomendacion"] = compute_recommendation(p)
    return p



def compute_chollometer(product: dict) -> dict:
    price = safe_float(product.get("price"))
    discount_pct = max(0, safe_float(product.get("discount_pct")))
    recommendation = max(0, safe_float(product.get("recomendacion")))
    source = get_source(product)

    score = min(recommendation, 55) * 0.75
    reasons = []

    if discount_pct >= 50:
        score += 22; reasons.append(f"-{round(discount_pct)}%")
    elif discount_pct >= 35:
        score += 17; reasons.append(f"-{round(discount_pct)}%")
    elif discount_pct >= 20:
        score += 11; reasons.append(f"-{round(discount_pct)}%")
    elif discount_pct >= 10:
        score += 6; reasons.append(f"-{round(discount_pct)}%")

    price_change_pct = safe_float(product.get("price_change_pct"))
    min_price_30d = safe_float(product.get("min_price_30d"))
    min_price_all = safe_float(product.get("min_price_all"))
    avg_price_30d = safe_float(product.get("avg_price_30d"))

    if product.get("is_price_drop") and price_change_pct < 0:
        score += min(abs(price_change_pct) * 1.6, 28)
        reasons.append(f"baja {abs(price_change_pct):.0f}%")

    if product.get("is_recent_min_price") and min_price_30d > 0:
        score += 14
        reasons.append("mínimo 30d")

    if min_price_all > 0 and price > 0 and price <= min_price_all:
        score += 8
        reasons.append("mínimo histórico")

    if avg_price_30d and price and price < avg_price_30d:
        below_avg = (avg_price_30d - price) / avg_price_30d * 100
        if below_avg >= 5:
            score += min(below_avg * 0.7, 12)
            reasons.append(f"{below_avg:.0f}% bajo media")

    sales = product.get("sales") or product.get("lastest_volume")
    try:
        sales_value = int(float(str(sales or 0).replace(".", "").replace(",", ".")))
    except Exception:
        sales_value = 0
    if sales_value >= 5000:
        score += 7; reasons.append("muy vendido")
    elif sales_value >= 1000:
        score += 4; reasons.append("vendido")

    rating = safe_float(product.get("rating") or product.get("evaluation_rating"))
    if rating >= 4.7:
        score += 5; reasons.append("valoración alta")
    elif rating >= 4.4:
        score += 3

    if source == "decathlon" and (product.get("is_price_drop") or product.get("is_recent_min_price")):
        score += 5
    elif source == "amazon":
        score += 3

    if price > 0:
        if is_bike_product(product.get("title")) and price > 1500 and not product.get("is_price_drop"):
            score -= 12
        elif price > 300 and discount_pct < 10 and not product.get("is_price_drop"):
            score -= 8

    score = max(0, min(100, round(score)))
    if score >= 85:
        label = "Chollo TOP"
    elif score >= 70:
        label = "Muy buen precio"
    elif score >= 55:
        label = "Buen precio"
    elif product.get("is_recent_min_price"):
        label = "Mínimo reciente"
    else:
        label = "Precio interesante"

    product["chollometer_score"] = score
    product["chollometer_label"] = label
    product["chollometer_reasons"] = list(dict.fromkeys([r for r in reasons if r]))[:3]
    product["recomendacion"] = max(int(product.get("recomendacion", 0) or 0), score)
    return product



def sort_key(product):
    return (
        product.get("chollometer_score", product.get("recomendacion", 0)),
        product.get("is_price_drop", False),
        product.get("is_recent_min_price", False),
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
        or product.get("asin")
        or product.get("affiliate_url")
        or product.get("url")
        or product.get("title")
    )


def main():
    decathlon = load_json(DECATHLON_PATH)
    aliexpress = load_json(ALIEXPRESS_PATH)
    amazon = load_json(AMAZON_PATH)
    decathlon_history = load_json_dict(DECATHLON_HISTORY_PATH)

    decathlon_filtered = [
        compute_chollometer(attach_decathlon_price_history(normalize_product(p), decathlon_history))
        for p in decathlon
        if passes_decathlon_filter(p)
    ]
    aliexpress_filtered = [compute_chollometer(normalize_product(p)) for p in aliexpress if passes_base_filter(p)]
    amazon_filtered = [compute_chollometer(normalize_product(p)) for p in amazon if passes_base_filter(p)]

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
        "decathlon_price_drops_published": sum(1 for d in deals if d.get("source") == "decathlon" and d.get("is_price_drop")),
        "decathlon_recent_min_published": sum(1 for d in deals if d.get("source") == "decathlon" and d.get("is_recent_min_price")),
        "chollometer_top_published": sum(1 for d in deals if d.get("chollometer_score", 0) >= 85),
        "chollometer_avg_score": round(sum(d.get("chollometer_score", 0) for d in deals) / len(deals), 2) if deals else 0,
        "aliexpress_published": sum(1 for d in deals if d.get("source") == "aliexpress"),
        "amazon_published": sum(1 for d in deals if d.get("source") == "amazon"),
        "total_published": len(deals),
    }

    OUTPUT_PATH.write_text(json.dumps(deals, indent=2, ensure_ascii=False), encoding="utf-8")
    MERGE_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
