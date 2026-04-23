import json
import re
from pathlib import Path

DATA_DIR = Path("data")
ALIEXPRESS_PATH = DATA_DIR / "aliexpress_products.json"
DECATHLON_PATH = DATA_DIR / "decathlon_products.json"
AMAZON_PATH = DATA_DIR / "amazon_products.json"
OUTPUT_PATH = DATA_DIR / "generated_deals.json"
MERGE_SUMMARY_PATH = DATA_DIR / "merge_summary.json"

MAX_TOTAL = 40
MAX_PER_SOURCE = 18
PLACEHOLDER_IMAGE = "/assets/placeholder-product.svg"


def load_json(path: Path):
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def clean_text(value):
    text = str(value or "").strip()
    if "<" in text:
        text = text.split("<", 1)[0].strip()
    return text


def clean_url(value):
    text = clean_text(value)
    if text.startswith("http://") or text.startswith("https://"):
        return text
    return ""


def parse_number(value):
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    text = text.replace("€", "").replace("EUR", "").replace("%", "").replace("\xa0", " ").strip()
    text = re.sub(r"[^0-9,.-]", "", text)
    if text.count(",") and text.count("."):
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        return float(text)
    except Exception:
        return 0.0


def normalize_source(value):
    source = clean_text(value).lower()
    if source in ("manual", "amazon"):
        return "amazon", "Amazon"
    if "deca" in source:
        return "decathlon", "Decathlon"
    if "ali" in source:
        return "aliexpress", "AliExpress"
    if source:
        return source, source.title()
    return "otros", "Tienda"


def compute_discount_pct(product):
    explicit = parse_number(product.get("discount_pct") or product.get("discount"))
    if explicit > 0:
        return round(explicit)
    price = parse_number(product.get("price"))
    old_price = parse_number(product.get("old_price"))
    if price > 0 and old_price > price:
        return round(((old_price - price) / old_price) * 100)
    return 0


def get_image(product):
    image = clean_text(product.get("image"))
    if image.startswith("http://") or image.startswith("https://"):
        return image
    return PLACEHOLDER_IMAGE


def compute_score(product):
    price = parse_number(product.get("price"))
    old_price = parse_number(product.get("old_price"))
    discount_pct = compute_discount_pct(product)
    sales = parse_number(product.get("sales"))
    title = clean_text(product.get("title")).lower()
    score = 0.0

    score += discount_pct * 1.4

    if price > 0:
        if price <= 20:
            score += 18
        elif price <= 50:
            score += 12
        elif price <= 100:
            score += 8
        elif price <= 250:
            score += 5

    if old_price > price > 0:
        score += 6

    if product.get("image") and product.get("image") != PLACEHOLDER_IMAGE:
        score += 4

    if sales > 0:
        score += min(sales / 250, 8)

    useful_terms = [
        "casco", "maillot", "culotte", "guantes", "luz", "luces", "zapatillas",
        "pedal", "pedales", "cadena", "cubierta", "camara", "cámara", "bidon",
        "bidón", "herramienta", "rodillo", "gafas", "bomba", "soporte", "sillin", "sillín"
    ]
    if any(term in title for term in useful_terms):
        score += 5

    if product.get("editor_pick"):
        score += 6

    return max(0, round(score))


def normalize_product(product, fallback_source=None):
    source, source_label = normalize_source(product.get("source") or fallback_source)
    title = clean_text(product.get("title"))
    url = clean_url(product.get("affiliate_url") or product.get("url"))
    price = parse_number(product.get("price"))
    if not title or not url or price <= 0:
        return None

    old_price = parse_number(product.get("old_price"))
    if old_price <= price:
        old_price = 0.0

    normalized = {
        "id": clean_text(product.get("id") or product.get("asin") or url or title),
        "title": title,
        "brand": clean_text(product.get("brand") or product.get("shop_name")),
        "category": clean_text(product.get("category")),
        "category_hint": clean_text(product.get("category_hint") or product.get("category")),
        "price": round(price, 2),
        "old_price": round(old_price, 2) if old_price > 0 else 0,
        "discount_pct": compute_discount_pct({**product, "price": price, "old_price": old_price}),
        "url": url,
        "affiliate_url": url,
        "image": get_image(product),
        "source": source,
        "source_label": source_label,
        "detail_enabled": bool(product.get("detail_enabled", True)),
        "sales": int(parse_number(product.get("sales"))) if parse_number(product.get("sales")) > 0 else 0,
    }
    normalized["recomendacion"] = compute_score(normalized)
    return normalized


def dedupe_products(products):
    seen = set()
    result = []
    for p in products:
        key = (p.get("source"), p.get("url") or p.get("title"))
        if key in seen:
            continue
        seen.add(key)
        result.append(p)
    return result


def round_robin_merge(grouped, max_total):
    result = []
    source_order = [src for src, items in grouped if items]
    idx = {src: 0 for src, _ in grouped}
    while len(result) < max_total and source_order:
        next_order = []
        for src, items in grouped:
            i = idx[src]
            if i < len(items) and len(result) < max_total:
                result.append(items[i])
                idx[src] += 1
            if idx[src] < len(items):
                next_order.append(src)
        if not next_order:
            break
        source_order = next_order
    return result[:max_total]


def main():
    raw_sources = {
        "aliexpress": load_json(ALIEXPRESS_PATH),
        "decathlon": load_json(DECATHLON_PATH),
        "amazon": load_json(AMAZON_PATH),
    }

    normalized_by_source = {}
    read_summary = {}
    for source_name, items in raw_sources.items():
        read_summary[f"{source_name}_read"] = len(items)
        normalized = [normalize_product(item, source_name) for item in items]
        normalized = [p for p in normalized if p is not None]
        normalized = dedupe_products(normalized)
        normalized.sort(key=lambda x: (x.get("recomendacion", 0), x.get("discount_pct", 0), -x.get("price", 0)), reverse=True)
        normalized_by_source[source_name] = normalized[:MAX_PER_SOURCE]

    grouped = [
        ("decathlon", normalized_by_source.get("decathlon", [])),
        ("amazon", normalized_by_source.get("amazon", [])),
        ("aliexpress", normalized_by_source.get("aliexpress", [])),
    ]
    deals = round_robin_merge(grouped, MAX_TOTAL)

    if len(deals) < MAX_TOTAL:
        used = {(p.get("source"), p.get("url")) for p in deals}
        leftovers = []
        for src in ["decathlon", "amazon", "aliexpress"]:
            for p in normalized_by_source.get(src, [])[MAX_PER_SOURCE:]:
                key = (p.get("source"), p.get("url"))
                if key not in used:
                    leftovers.append(p)
        deals.extend(leftovers[: MAX_TOTAL - len(deals)])

    summary = {**read_summary, "total_published": len(deals)}
    for src in ["decathlon", "amazon", "aliexpress"]:
        summary[f"{src}_published"] = sum(1 for d in deals if d.get("source") == src)

    OUTPUT_PATH.write_text(json.dumps(deals, ensure_ascii=False, indent=2), encoding="utf-8")
    MERGE_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Publicados: {len(deals)}")
    print(summary)


if __name__ == "__main__":
    main()
