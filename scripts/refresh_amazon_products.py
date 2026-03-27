from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AMAZON_PRODUCTS_FILE = DATA_DIR / "amazon_products.json"

TODAY_UTC = datetime.now(timezone.utc)
TODAY_DATE = TODAY_UTC.date().isoformat()


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def extract_asin(url: str) -> str | None:
    if not url:
        return None
    match = re.search(r"/(?:dp|gp/aw/d|aw/d)/([A-Z0-9]{10})", url)
    return match.group(1) if match else None


def canonical_amazon_url(url: str, partner_tag: str = "") -> str:
    asin = extract_asin(url)
    if not asin:
        return url

    clean = f"https://www.amazon.es/dp/{asin}"
    if not partner_tag:
        return clean

    parsed = urlparse(clean)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["tag"] = partner_tag
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query), parsed.fragment))


def refresh_products_with_api(items: list[dict]) -> list[dict]:
    """
    Placeholder for future Amazon PA-API integration.

    Expected env vars:
    - AMAZON_PAAPI_ACCESS_KEY
    - AMAZON_PAAPI_SECRET_KEY
    - AMAZON_PAAPI_PARTNER_TAG
    - AMAZON_PAAPI_REGION (e.g. eu-west-1)
    - AMAZON_PAAPI_HOST (e.g. webservices.amazon.es)

    For now this function keeps the catalog stable, normalizes URLs,
    preserves existing prices, and updates last_checked so the daily
    workflow remains ready for real API integration later.
    """
    access_key = os.getenv("AMAZON_PAAPI_ACCESS_KEY", "").strip()
    secret_key = os.getenv("AMAZON_PAAPI_SECRET_KEY", "").strip()
    partner_tag = os.getenv("AMAZON_PAAPI_PARTNER_TAG", "").strip() or os.getenv("AMAZON_PARTNER_TAG", "").strip()

    refreshed: list[dict] = []

    for item in items:
        item = dict(item)
        item["url"] = canonical_amazon_url(item.get("url", ""), partner_tag)
        if item.get("price") in ("", None):
            item["price"] = 0
        item["last_checked"] = TODAY_DATE

        # Real API enrichment intentionally pending until credentials are available.
        # When keys exist, replace this section with a PA-API lookup by ASIN and update:
        # title, image, price, old_price, availability, etc.
        if access_key and secret_key:
            # Stub branch kept explicit so the workflow is already wired for the future.
            # No network request is made in this template version.
            pass

        refreshed.append(item)

    return refreshed


def main() -> int:
    items = load_json(AMAZON_PRODUCTS_FILE, [])
    if not isinstance(items, list):
        print("amazon_products.json no contiene una lista válida.", file=sys.stderr)
        return 1

    refreshed = refresh_products_with_api(items)
    save_json(AMAZON_PRODUCTS_FILE, refreshed)
    print(f"Productos normalizados/actualizados: {len(refreshed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
