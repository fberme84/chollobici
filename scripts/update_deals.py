
import json
import html
import re
import urllib.parse
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
PLACEHOLDER_IMAGE = "/assets/placeholder-product.svg"


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def parse_number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    text = html.unescape(text)
    text = text.replace("€", "").replace("EUR", "").replace(",", ".")
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text or text in {"-", ".", "-."}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def parse_discount(product):
    explicit = parse_number(product.get("discount_pct"))
    if explicit and explicit > 0:
        return round(explicit, 2)

    explicit = parse_number(product.get("discount"))
    if explicit and explicit > 0:
        return round(explicit, 2)

    price = parse_number(product.get("price"))
    old_price = parse_number(product.get("old_price"))
    if price and old_price and old_price > price > 0:
        return round(((old_price - price) / old_price) * 100, 2)

    return 0.0


def clean_title(value):
    text = html.unescape(str(value or ""))
    text = urllib.parse.unquote(text)
    text = re.sub(r"</?[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -|")
    if text.startswith("s://"):
        text = text[4:]
    if text.startswith("s:/"):
        text = text[3:]
    if text.lower().startswith("http"):
        slug = urllib.parse.urlparse(text).path.rstrip("/").split("/")[-1]
        slug = urllib.parse.unquote(slug)
        slug = re.sub(r"[-_]+", " ", slug).strip()
        if slug:
            text = slug
    return text[:180]


def clean_url(*values):
    for value in values:
        raw = html.unescape(str(value or "")).strip()
        if not raw:
            continue
        raw = raw.replace(" ", "%20")
        if raw.startswith("https://") or raw.startswith("http://"):
            return raw
    return ""


def clean_image(value):
    raw = html.unescape(str(value or "")).strip()
    if raw.startswith("https://") or raw.startswith("http://"):
        return raw
    return PLACEHOLDER_IMAGE


def normalize_source(product):
    source = str(product.get("source") or "").strip().lower()
    if source == "manual":
        return "amazon"
    return source or "otros"


def get_source_label(source):
    labels = {
        "aliexpress": "AliExpress",
        "decathlon": "Decathlon",
        "amazon": "Amazon",
    }
    return labels.get(source, source.title() if source else "Tienda")


def should_keep(product, source):
    price = parse_number(product.get("price"))
    if not price or price <= 0:
        return False

    title = clean_title(product.get("title"))
    url = clean_url(product.get("affiliate_url"), product.get("url"))
    if not title or not url:
        return False

    if source == "decathlon":
        return True

    discount = parse_discount(product)
    return discount > 0


def score_product(product):
    score = 0.0
    discount = product["discount_pct"]
    price = product["price"]
    sales = parse_number(product.get("sales")) or 0
    rating = parse_number(product.get("rating")) or 0
    source = product["source"]

    if discount > 0:
        score += min(discount, 70) * 2.0

    if price < 20:
        score += 18
    elif price < 50:
        score += 10
    elif price < 100:
        score += 5

    if product["image"] != PLACEHOLDER_IMAGE:
        score += 10
    else:
        score -= 20

    if product.get("old_price"):
        score += 5

    if sales > 0:
        score += min(sales / 50.0, 20)

    if rating > 0:
        score += min(rating * 2.5, 12)

    if source == "decathlon":
        score += 8
        if discount <= 0:
            score -= 10

    if source == "amazon":
        score += 4

    return round(score, 2)


def normalize_product(product):
    source = normalize_source(product)
    if not should_keep(product, source):
        return None

    price = parse_number(product.get("price"))
    old_price = parse_number(product.get("old_price"))
    discount = parse_discount(product)

    normalized = dict(product)
    normalized["source"] = source
    normalized["source_label"] = product.get("source_label") or get_source_label(source)
    normalized["title"] = clean_title(product.get("title"))
    normalized["url"] = clean_url(product.get("url"), product.get("affiliate_url"))
    normalized["affiliate_url"] = clean_url(product.get("affiliate_url"), product.get("url"))
    normalized["image"] = clean_image(product.get("image"))
    normalized["price"] = round(price, 2) if price is not None else None
    normalized["old_price"] = round(old_price, 2) if old_price is not None and old_price > price else None
    normalized["discount_pct"] = round(discount, 2) if discount > 0 else 0
    normalized["discount"] = round(discount, 2) if discount > 0 else 0
    normalized["score"] = 0
    normalized["recomendacion"] = 0
    normalized["id"] = (
        product.get("id")
        or normalized["affiliate_url"]
        or normalized["url"]
        or normalized["title"]
    )
    return normalized


def diversify(products):
    by_source = defaultdict(list)
    for product in products:
        by_source[product["source"]].append(product)

    for source in by_source:
        by_source[source].sort(key=lambda x: x["score"], reverse=True)

    order = ["decathlon", "aliexpress", "amazon"]
    result = []

    while any(by_source.values()):
        picked = False
        for source in order:
            if by_source[source]:
                result.append(by_source[source].pop(0))
                picked = True
        if not picked:
            break

    for remaining in by_source.values():
        result.extend(remaining)

    return result


def main():
    inputs = [
        DATA_DIR / "aliexpress_products.json",
        DATA_DIR / "decathlon_products.json",
        DATA_DIR / "amazon_products.json",
    ]

    seen = set()
    normalized = []
    source_stats = defaultdict(int)
    source_kept = defaultdict(int)

    for path in inputs:
        items = load_json(path, [])
        if not isinstance(items, list):
            continue
        for item in items:
            source = normalize_source(item)
            source_stats[source] += 1
            clean = normalize_product(item)
            if not clean:
                continue
            key = clean["affiliate_url"] or clean["url"] or clean["title"]
            if key in seen:
                continue
            seen.add(key)
            clean["score"] = score_product(clean)
            clean["recomendacion"] = clean["score"]
            normalized.append(clean)
            source_kept[source] += 1

    normalized.sort(key=lambda x: x["score"], reverse=True)
    diversified = diversify(normalized)

    with open(DATA_DIR / "generated_deals.json", "w", encoding="utf-8") as f:
        json.dump(diversified, f, ensure_ascii=False, indent=2)

    summary = {
        "input_counts": dict(source_stats),
        "published_counts": dict(source_kept),
        "total_published": len(diversified),
    }
    with open(DATA_DIR / "merge_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("Resumen merge:", summary, flush=True)


if __name__ == "__main__":
    main()
