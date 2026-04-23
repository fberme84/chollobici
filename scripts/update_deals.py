import json
from pathlib import Path

DATA_DIR = Path("data")
DECATHLON_PATH = DATA_DIR / "decathlon_products.json"
ALIEXPRESS_PATH = DATA_DIR / "aliexpress_products.json"
OUTPUT_PATH = DATA_DIR / "generated_deals.json"
MERGE_SUMMARY_PATH = DATA_DIR / "merge_summary.json"

MAX_TOTAL = 40
TARGET_PER_SOURCE = 20


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def compute_discount_pct(product):
    explicit = product.get("discount_pct")
    if explicit not in (None, "", 0, "0"):
        try:
            return int(float(explicit))
        except Exception:
            pass

    raw_discount = str(product.get("discount") or "").replace("%", "").strip()
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


def is_decathlon(product):
    return str(product.get("source") or "").lower() == "decathlon"


def clean_image_url(url: str) -> str:
    text = str(url or "").strip()
    if "<" in text:
        text = text.split("<", 1)[0].strip()
    return text


def clean_text(value: str) -> str:
    text = str(value or "").strip()
    if "<" in text:
        text = text.split("<", 1)[0].strip()
    return text


def is_bike_product(title: str) -> bool:
    text = f" {str(title or '').lower()} "
    return any(term in text for term in [
        " bici ", " bicicleta", " mtb", " gravel", " carretera", " rockrider",
        " triban", " van rysel", " cervélo", " cervelo", " ebike", " e-bike"
    ])


def passes_decathlon_filter(product: dict) -> bool:
    title = (product.get("title") or "").lower()
    text = f" {title} "

    price = safe_float(product.get("price"))
    if not price:
        return False

    premium_terms = [
        "s-works", "pinarello", "cervélo", "cervelo", "dogma", "super record",
        " dura-ace ", " etap ", " axs ", " factory "
    ]
    if any(term in text for term in premium_terms):
        return False

    if is_bike_product(title):
        return price <= 1500

    return price <= 300


def load_json(path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def compute_recommendation(product: dict) -> int:
    price = safe_float(product.get("price"))
    discount_pct = compute_discount_pct(product)
    title = (product.get("title") or "").lower()
    category_hint = (product.get("category_hint") or "").lower()
    text = f"{title} {category_hint}"

    score = 0.0
    score += discount_pct * 1.3

    if price > 0:
        if price <= 15:
            score += 22
        elif price <= 30:
            score += 18
        elif price <= 50:
            score += 15
        elif price <= 80:
            score += 12
        elif price <= 120:
            score += 9
        elif price <= 200:
            score += 6
        elif price <= 300:
            score += 3
        elif price <= 600:
            score += 1

    useful_terms = [
        "casco", "maillot", "culotte", "guantes", "luz", "luces", "zapatillas",
        "pedal", "pedales", "cadena", "cubierta", "camara", "cámara", "bidon",
        "bidón", "portabidon", "portabidón", "herramienta", "rodillo",
        "sillin", "sillín", "gafas", "bomba", "inflador", "soporte"
    ]
    if any(term in text for term in useful_terms):
        score += 6

    if is_bike_product(title):
        if price <= 600:
            score += 5
        elif price <= 1000:
            score += 2
        else:
            score -= 8

    sales = product.get("sales")
    try:
        sales_value = int(float(sales))
    except Exception:
        sales_value = 0
    score += min(sales_value / 500, 8)

    return max(0, round(score))


def normalize_product(product: dict) -> dict:
    p = dict(product)
    p["image"] = clean_image_url(p.get("image", ""))
    p["category_hint"] = clean_text(p.get("category_hint", ""))
    p["discount_pct"] = compute_discount_pct(p)
    p["recomendacion"] = compute_recommendation(p)
    return p


def strict_interleave(a, b, max_total=40):
    result = []
    limit = max(len(a), len(b))
    for i in range(limit):
        if i < len(a) and len(result) < max_total:
            result.append(a[i])
        if i < len(b) and len(result) < max_total:
            result.append(b[i])
    return result[:max_total]


def main():
    decathlon = load_json(DECATHLON_PATH)
    aliexpress = load_json(ALIEXPRESS_PATH)

    print(f"Decathlon leídos: {len(decathlon)}")
    print(f"AliExpress leídos: {len(aliexpress)}")

    decathlon_filtered = [normalize_product(p) for p in decathlon if passes_decathlon_filter(p)]
    aliexpress_normalized = [normalize_product(p) for p in aliexpress]

    print(f"Decathlon tras filtro: {len(decathlon_filtered)}")

    decathlon_sorted = sorted(decathlon_filtered, key=lambda x: (x.get("recomendacion", 0), -safe_float(x.get("price"))), reverse=True)
    aliexpress_sorted = sorted(aliexpress_normalized, key=lambda x: (x.get("recomendacion", 0), -safe_float(x.get("price"))), reverse=True)

    deals = strict_interleave(aliexpress_sorted[:TARGET_PER_SOURCE], decathlon_sorted[:TARGET_PER_SOURCE], max_total=MAX_TOTAL)

    if len(deals) < MAX_TOTAL:
        used_ids = {str(p.get("id")) for p in deals}
        remaining = [
            p for p in (aliexpress_sorted[TARGET_PER_SOURCE:] + decathlon_sorted[TARGET_PER_SOURCE:])
            if str(p.get("id")) not in used_ids
        ]
        deals.extend(remaining[:MAX_TOTAL - len(deals)])

    decathlon_deals = sum(1 for d in deals if is_decathlon(d))
    print(f"TOTAL DEALS FINAL: {len(deals)}")
    print(f"DECATHLON DEALS FINAL: {decathlon_deals}")

    summary = {
        "decathlon_read": len(decathlon),
        "aliexpress_read": len(aliexpress),
        "decathlon_published": decathlon_deals,
        "aliexpress_published": len(deals) - decathlon_deals,
        "total_published": len(deals),
    }

    OUTPUT_PATH.write_text(json.dumps(deals, indent=2, ensure_ascii=False), encoding="utf-8")
    MERGE_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
