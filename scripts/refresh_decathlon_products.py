from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data'
OUTPUT_PATH = DATA_DIR / 'decathlon_products.json'
CONFIG_PATH = DATA_DIR / 'decathlon_feed_url.txt'
RAW_CACHE_PATH = DATA_DIR / 'decathlon_feed_latest.txt'
TIMEOUT = (20, 120)
MAX_ATTEMPTS = 3
MIN_VALID_PRODUCTS = 20
VALIDATE_PRODUCT_LINKS = os.getenv('DECATHLON_VALIDATE_LINKS', '1').strip() != '0'
VALIDATION_TIMEOUT = (15, 45)


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
    'cycology', 'ixs', 'zwheel', 'airbici', 'attabo', 'northwave', 'race face', 'shimano',
]

CYCLING_EXCLUDE_KEYWORDS = [
    'nevera portátil', 'esquí', 'snowboard', 'fútbol', 'baloncesto', 'judo', 'bikini',
]


def normalize_decathlon_code(code: str) -> str:
    raw = str(code or '').strip().lower()
    return re.sub(r'([._]c\d+.*)$', '', raw)


def looks_like_product_page(url: str, expected_code: str = '') -> bool:
    parsed = urllib.parse.urlparse(str(url or ''))
    path = urllib.parse.unquote(parsed.path).lower()
    query = urllib.parse.unquote(parsed.query).lower()
    if '/es/p/' not in path:
        return False
    if '/_/r-p-' not in path:
        return False
    normalized_code = normalize_decathlon_code(expected_code)
    if not normalized_code:
        return True
    return normalized_code in path or normalized_code in query


def looks_like_listing_page(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url or ''))
    path = urllib.parse.unquote(parsed.path).lower()
    listing_markers = ['/es/c/', '/es/browse/', '/all-sports/', '/landing/', '/search']
    if any(marker in path for marker in listing_markers):
        return True
    if '/es/p/' not in path:
        return True
    if '/_/r-p-' not in path:
        return True
    return False


def validate_product_link(session: requests.Session, item: dict) -> dict:
    affiliate_url = item.get('affiliate_url') or item.get('url') or ''
    expected_code = item.get('feed_code') or ''
    if not affiliate_url:
        return {
            'link_validation_status': 'missing_url',
            'detail_enabled': False,
            'catalog_excluded': False,
            'final_affiliate_url': '',
        }

    try:
        response = session.get(affiliate_url, timeout=VALIDATION_TIMEOUT, allow_redirects=True, stream=True)
        final_url = response.url or affiliate_url
        response.close()

        if looks_like_product_page(final_url, expected_code):
            return {
                'link_validation_status': 'ok',
                'detail_enabled': True,
                'catalog_excluded': False,
                'final_affiliate_url': final_url,
            }

        if looks_like_listing_page(final_url):
            return {
                'link_validation_status': 'redirects_to_listing',
                'detail_enabled': False,
                'catalog_excluded': True,
                'final_affiliate_url': final_url,
            }

        return {
            'link_validation_status': 'unknown_target',
            'detail_enabled': False,
            'catalog_excluded': False,
            'final_affiliate_url': final_url,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            'link_validation_status': f'validation_error:{exc.__class__.__name__}',
            'detail_enabled': False,
            'catalog_excluded': False,
            'final_affiliate_url': affiliate_url,
        }


def validate_items(items: list[dict]) -> list[dict]:
    if not VALIDATE_PRODUCT_LINKS or not items:
        for item in items:
            item.setdefault('link_validation_status', 'not_checked')
            item.setdefault('detail_enabled', False)
            item.setdefault('catalog_excluded', False)
            item.setdefault('final_affiliate_url', item.get('affiliate_url') or item.get('url') or '')
        return items

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (compatible; CholloBiciBot/1.0; +https://www.chollobici.com)',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    })

    validated: list[dict] = []
    excluded = 0
    enabled = 0
    for idx, item in enumerate(items, start=1):
        result = validate_product_link(session, item)
        item.update(result)
        if item.get('catalog_excluded'):
            excluded += 1
        if item.get('detail_enabled'):
            enabled += 1
        if idx % 20 == 0 or idx == len(items):
            print(f'Validación enlaces Decathlon: {idx}/{len(items)} procesados · fichas activas {enabled} · excluidos {excluded}')
        validated.append(item)
    return validated


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
        'feed_code': data['code'],
        'last_checked': datetime.now(timezone.utc).date().isoformat(),
        'editor_pick': False,
        'availability_hint': int(data['metric_1']),
        'size': (data.get('size') or '').strip(),
        'reason': 'Importado desde feed de Decathlon y refrescado automáticamente.',
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


def dedupe_items(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        key = item.get('affiliate_url') or item.get('url') or item.get('id')
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def atomic_write(path: Path, text: str) -> None:
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(text, encoding='utf-8')
    tmp_path.replace(path)


def fetch_feed_text(feed_url: str) -> str:
    last_error: Exception | None = None
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (compatible; CholloBiciBot/1.0; +https://www.chollobici.com)',
        'Accept': 'text/plain,text/html,application/octet-stream,*/*',
    })

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f'Intento {attempt}/{MAX_ATTEMPTS} descargando feed de Decathlon...')
            response = session.get(feed_url, timeout=TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            response.encoding = response.encoding or 'utf-8'
            text = response.text.strip()
            if len(text) < 1000:
                raise ValueError('La respuesta del feed es demasiado corta para ser válida.')
            return text
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            print(f'Intento {attempt} fallido: {exc}')
            if attempt < MAX_ATTEMPTS:
                sleep_seconds = 10 * attempt
                print(f'Esperando {sleep_seconds}s antes de reintentar...')
                time.sleep(sleep_seconds)

    raise RuntimeError(f'No se pudo descargar el feed de Decathlon tras {MAX_ATTEMPTS} intentos.') from last_error


def parse_feed_text(text: str) -> tuple[list[dict], int]:
    parsed: list[dict] = []
    failed = 0
    for record in split_records(text):
        item = parse_record(record)
        if item is None:
            failed += 1
            continue
        if is_cycling(item):
            parsed.append(item)
    return dedupe_items(parsed), failed


def load_existing_catalog() -> list[dict]:
    if not OUTPUT_PATH.exists():
        return []
    try:
        return json.loads(OUTPUT_PATH.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return []


def main() -> None:
    feed_url = get_feed_url()
    existing_catalog = load_existing_catalog()

    if not feed_url:
        print('Feed de Decathlon no configurado. Se mantiene el catálogo existente.')
        if not OUTPUT_PATH.exists():
            atomic_write(OUTPUT_PATH, '[]\n')
        return

    try:
        text = fetch_feed_text(feed_url)
        parsed, failed = parse_feed_text(text)

        if len(parsed) < MIN_VALID_PRODUCTS:
            raise RuntimeError(
                f'El feed descargado solo devolvió {len(parsed)} productos válidos de ciclismo. Se considera respuesta sospechosa.'
            )

        validated = validate_items(parsed)
        public_items = [item for item in validated if not item.get('catalog_excluded')]

        if len(public_items) < MIN_VALID_PRODUCTS:
            raise RuntimeError(
                f'La validación de enlaces dejó solo {len(public_items)} productos publicables de Decathlon. Se conserva el catálogo anterior.'
            )

        atomic_write(RAW_CACHE_PATH, text)
        atomic_write(OUTPUT_PATH, json.dumps(public_items, ensure_ascii=False, indent=2) + '\n')
        print(f'Productos Decathlon ciclismo guardados: {len(public_items)}')
        print(f'Registros Decathlon no parseados: {failed}')
        print(f'Productos Decathlon excluidos por redirección/listing: {len([i for i in validated if i.get('catalog_excluded')])}')
        print(f'Productos Decathlon con ficha local activada: {len([i for i in validated if i.get('detail_enabled')])}')
    except Exception as exc:  # noqa: BLE001
        print(f'No se pudo refrescar el feed de Decathlon: {exc}')
        if existing_catalog:
            print(f'Se conserva el último catálogo válido existente ({len(existing_catalog)} productos).')
            return
        raise


if __name__ == '__main__':
    main()
