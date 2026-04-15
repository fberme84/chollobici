from __future__ import annotations

import json
import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
OUTPUT_PATH = DATA_DIR / 'decathlon_products.json'
CONFIG_PATH = DATA_DIR / 'decathlon_feed_url.txt'
TIMEOUT = 60

RECORD_START_RE = re.compile(
    r'(?<!\S)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\s+[0-9a-f]{8}-'
)

RECORD_RE = re.compile(
    r'^(?P<id>[0-9a-f-]{36})\s+'
    r'(?P<code>\S+)\s+'
    r'(?P<head>.*?)\s+'
    r'(?P<image>https://contents\.mediadecathlon\.com/\S+)\s+'
    r'(?P<affiliate_url>https://afiliacion\.decathlon\.es/tracking/clk\?\S+)\s+'
    r'(?P<price_old>\d+(?:\.\d+)?)\s+'
    r'(?P<price>\d+(?:\.\d+)?)\s+'
    r'(?P<metric_1>\d+)\s+'
    r'(?P<metric_2>\d+)'
    r'(?:\s+(?P<size>.+?))?$',
    re.S,
)

CYCLING_INCLUDE_KEYWORDS = [
    'cicl', 'bici', 'biciclet', 'mtb', 'gravel', 'carretera', 'road', 'bike', 'cycling',
    'maillot', 'culotte', 'cuissard', 'casco', 'cubrezapat', 'pedal', 'sillin', 'manillar',
    'piñon', 'cassette', 'cadena', 'rueda', 'llanta', 'cubierta', 'neumatic', 'cámara',
    'camara', 'bidon', 'portabidon', 'zapatillas de ciclismo', 'gafas ciclismo', 'puños',
    'empuñadura', 'guardabarros', 'portaequipajes', 'portabultos', 'tija', 'potencia',
    'rodillo', 'bikepacking', 'bmx', 'endura', 'spiuk', 'siroko', 'ergon', 'sportful',
    'cycology', 'ixs', 'zwheel', 'airbici', 'attabo',
]

CYCLING_EXCLUDE_KEYWORDS = [
    'nevera portátil',
]


def get_feed_url() -> str:
    env_value = os.getenv('DECATHLON_FEED_URL', '').strip()
    if env_value:
        return env_value
    if CONFIG_PATH.exists():
        return CONFIG_PATH.read_text(encoding='utf-8').strip()
    return ''


def split_records(text: str) -> list[str]:
    starts = [m.start() for m in RECORD_START_RE.finditer(text)]
    records: list[str] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        records.append(text[start:end].strip())
    return records


def parse_record(record: str) -> dict | None:
    match = RECORD_RE.match(record)
    if not match:
        return None

    data = match.groupdict()
    affiliate_url = data['affiliate_url']
    query = urllib.parse.parse_qs(urllib.parse.urlparse(affiliate_url).query)

    pca = urllib.parse.unquote(query.get('pca', [''])[0])
    pca_parts = pca.split('|')
    title = pca_parts[1].strip() if len(pca_parts) >= 2 else data['head'].strip()
    product_url = urllib.parse.unquote(query.get('url', [''])[0])

    meta_tail = data['head']
    if title and meta_tail.startswith(title + ' '):
        meta_tail = meta_tail[len(title) + 1 :]

    brand_slug = ''
    brand_match = re.search(r'/mp/([^/]+)/', product_url)
    if brand_match:
        brand_slug = brand_match.group(1)

    price_old = float(data['price_old'])
    price = float(data['price'])

    return {
        'id': f"decathlon_{data['id']}",
        'title': title,
        'category': meta_tail.strip() or 'Ciclismo',
        'price': price,
        'old_price': price_old,
        'url': product_url or affiliate_url,
        'affiliate_url': affiliate_url,
        'image': data['image'],
        'source': 'decathlon',
        'source_label': 'Decathlon',
        'store': 'Decathlon',
        'brand': brand_slug,
        'last_checked': datetime.now(timezone.utc).date().isoformat(),
        'editor_pick': False,
        'availability_hint': int(data['metric_1']),
        'size': (data.get('size') or '').strip(),
        'reason': 'Importado desde feed de Decathlon para pruebas de catálogo.',
    }


def is_cycling(item: dict) -> bool:
    haystack = ' '.join([
        item.get('title', ''),
        item.get('category', ''),
        item.get('url', ''),
        item.get('brand', ''),
    ]).lower()
    if any(keyword in haystack for keyword in CYCLING_EXCLUDE_KEYWORDS):
        return False
    return any(keyword in haystack for keyword in CYCLING_INCLUDE_KEYWORDS)


def main() -> None:
    feed_url = get_feed_url()
    if not feed_url:
        print('Feed de Decathlon no configurado. Se mantiene el catálogo existente.')
        if not OUTPUT_PATH.exists():
            OUTPUT_PATH.write_text('[]\n', encoding='utf-8')
        return

    response = requests.get(feed_url, timeout=TIMEOUT)
    response.raise_for_status()
    response.encoding = response.encoding or 'utf-8'
    text = response.text

    parsed: list[dict] = []
    failed = 0
    for record in split_records(text):
        item = parse_record(record)
        if item is None:
            failed += 1
            continue
        if is_cycling(item):
            parsed.append(item)

    OUTPUT_PATH.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Productos Decathlon ciclismo guardados: {len(parsed)}')
    print(f'Registros Decathlon no parseados: {failed}')


if __name__ == '__main__':
    main()
