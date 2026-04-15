from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DECATHLON_PATH = DATA_DIR / "decathlon_products.json"
ALIEXPRESS_PATH = DATA_DIR / "aliexpress_products.json"
AMAZON_PATH = DATA_DIR / "amazon_products.json"
OUTPUT_PATH = DATA_DIR / "generated_deals.json"
SUMMARY_PATH = DATA_DIR / "merge_summary.json"

MAX_DECATHLON = 140
MAX_ALIEXPRESS = 80
MAX_TOTAL = 220


def load_json(path: Path):
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def to_float(value, default=0.0):
    try:
        if value in (None, ''):
            return default
        return float(str(value).replace('%', '').replace(',', '.'))
    except Exception:
        return default


def normalize_decathlon(item: dict) -> dict | None:
    title = str(item.get('title') or '').strip()
    url = str(item.get('affiliate_url') or item.get('url') or '').strip()
    image = str(item.get('image') or '').strip()
    price = to_float(item.get('price'), default=0.0)
    if not title or not url or not image or price <= 0:
        return None

    old_price = to_float(item.get('old_price'), default=price)
    discount_pct = int(round(to_float(item.get('discount_pct'), default=0)))
    if discount_pct < 0:
        discount_pct = 0

    normalized = {
        'id': str(item.get('id') or item.get('product_id') or url),
        'title': title,
        'brand': str(item.get('brand') or '').strip(),
        'category': str(item.get('category') or 'ciclismo').strip() or 'ciclismo',
        'category_hint': str(item.get('category_hint') or '').strip(),
        'price': price,
        'old_price': old_price if old_price > 0 else price,
        'discount_pct': discount_pct,
        'url': url,
        'affiliate_url': url,
        'image': image,
        'source': 'decathlon',
        'source_label': 'Decathlon',
        'detail_enabled': False,
        'recomendacion': float(item.get('recomendacion') or (discount_pct * 1000 - price)),
    }
    return normalized


def normalize_aliexpress(item: dict) -> dict | None:
    title = str(item.get('title') or '').strip()
    url = str(item.get('affiliate_url') or item.get('url') or '').strip()
    image = str(item.get('image') or '').strip()
    price = to_float(item.get('price'), default=0.0)
    if not title or not url or not image or price <= 0:
        return None

    old_price = to_float(item.get('old_price'), default=price)
    discount_pct = int(round(to_float(item.get('discount_pct') or item.get('discount'), default=0)))
    if discount_pct == 0 and old_price > price > 0:
        discount_pct = int(round((old_price - price) / old_price * 100))
    if discount_pct < 0:
        discount_pct = 0

    normalized = {
        'id': str(item.get('id') or url),
        'title': title,
        'brand': str(item.get('brand') or item.get('shop_name') or '').strip(),
        'category': str(item.get('category') or 'Accesorios').strip() or 'Accesorios',
        'category_hint': str(item.get('category') or '').strip(),
        'price': price,
        'old_price': old_price if old_price > 0 else price,
        'discount_pct': discount_pct,
        'url': url,
        'affiliate_url': url,
        'image': image,
        'source': 'aliexpress',
        'source_label': 'AliExpress',
        'detail_enabled': False,
        'sales': int(float(item.get('sales') or 0)) if str(item.get('sales') or '0').replace('.', '', 1).isdigit() else 0,
        'recomendacion': (discount_pct * 1000) + min(int(float(item.get('sales') or 0)), 50000) - price,
    }
    return normalized


def dedupe_by_title_and_source(items: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for item in items:
        key = (item['source'], item['title'].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def main() -> None:
    decathlon_raw = load_json(DECATHLON_PATH)
    aliexpress_raw = load_json(ALIEXPRESS_PATH)
    amazon_raw = load_json(AMAZON_PATH)

    decathlon = [x for x in (normalize_decathlon(item) for item in decathlon_raw) if x]
    aliexpress = [x for x in (normalize_aliexpress(item) for item in aliexpress_raw) if x]

    decathlon.sort(key=lambda x: (x.get('discount_pct', 0), -(x.get('price') or 0)), reverse=True)
    aliexpress.sort(key=lambda x: (x.get('discount_pct', 0), x.get('sales', 0)), reverse=True)

    decathlon = dedupe_by_title_and_source(decathlon)[:MAX_DECATHLON]
    aliexpress = dedupe_by_title_and_source(aliexpress)[:MAX_ALIEXPRESS]

    merged = decathlon + aliexpress
    merged.sort(key=lambda x: (x.get('recomendacion', 0), x.get('discount_pct', 0)), reverse=True)
    merged = merged[:MAX_TOTAL]

    OUTPUT_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding='utf-8')

    summary = {
        'decathlon_read': len(decathlon_raw),
        'aliexpress_read': len(aliexpress_raw),
        'amazon_read': len(amazon_raw),
        'decathlon_published': len(decathlon),
        'aliexpress_published': len(aliexpress),
        'amazon_published': 0,
        'total_published': len(merged),
        'stores': sorted({item['source_label'] for item in merged}),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"Productos Decathlon leídos: {len(decathlon_raw)}")
    print(f"Productos AliExpress leídos: {len(aliexpress_raw)}")
    print(f"Productos Amazon leídos: {len(amazon_raw)}")
    print(f"Productos Decathlon publicados: {len(decathlon)}")
    print(f"Productos AliExpress publicados: {len(aliexpress)}")
    print(f"Productos Amazon publicados: 0")
    print(f"Ofertas publicadas: {len(merged)}")


if __name__ == '__main__':
    main()
