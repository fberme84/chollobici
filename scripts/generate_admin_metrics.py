from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DEALS_PATH = DATA_DIR / "generated_deals.json"
SITEMAP_PATH = ROOT / "sitemap.xml"
OUTPUT_PATH = DATA_DIR / "admin_metrics.json"


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def count_sitemap_urls(path: Path) -> int:
    if not path.exists():
        return 0
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return len(root.findall("sm:url", ns))


def main() -> None:
    deals = load_json(DEALS_PATH) or []
    if not isinstance(deals, list):
        deals = []

    store_counter = Counter(
        (item.get("source_label") or item.get("store") or item.get("source") or "unknown")
        for item in deals
    )

    product_pages = sum(1 for item in deals if item.get("has_product_detail_page"))
    with_discount = sum(1 for item in deals if float(item.get("discount_pct") or 0) > 0)

    metrics = {
        "generated_at": datetime.now(UTC).isoformat(),
        "totals": {
            "offers": len(deals),
            "offers_with_discount": with_discount,
            "product_detail_pages": product_pages,
            "sitemap_urls": count_sitemap_urls(SITEMAP_PATH),
        },
        "stores": dict(sorted(store_counter.items())),
    }

    OUTPUT_PATH.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Admin metrics generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
