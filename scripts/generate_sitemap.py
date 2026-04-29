from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import OrderedDict
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape


BASE_URL = "https://www.chollobici.com"
ROOT = Path(__file__).resolve().parents[1]
DEALS_PATH = ROOT / "data" / "generated_deals.json"
SEO_PAGES_PATH = ROOT / "data" / "seo_pages.json"
SITEMAP_PATH = ROOT / "sitemap.xml"


def slugify(text: str) -> str:
    value = str(text or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"&", " y ", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def build_product_slug(deal: dict, index: int) -> str:
    title = str(deal.get("title") or "producto").strip()
    base = slugify(title)[:70].rstrip("-") or "producto"
    unique_source = (
        str(deal.get("product_id") or "")
        or str(deal.get("id") or "")
        or str(deal.get("affiliate_url") or "")
        or str(deal.get("url") or "")
        or title
        or str(index)
    )
    unique_hash = hashlib.md5(unique_source.encode("utf-8")).hexdigest()[:10]
    return f"{base}-{unique_hash}"


def parse_positive_float(value) -> float:
    try:
        if value in (None, ""):
            return 0.0
        return float(str(value).replace(",", "."))
    except Exception:
        return 0.0


def calculate_discount_pct(price, old_price) -> int:
    try:
        p = float(price)
        o = float(old_price)
        if o > 0 and p <= o:
            return round((o - p) / o * 100)
    except Exception:
        pass
    return 0


def has_real_image(deal: dict) -> bool:
    image = str(deal.get("image") or "").strip().lower()
    if not image:
        return False
    if "placeholder" in image or image.endswith("placeholder-product.svg"):
        return False
    return image.startswith("http://") or image.startswith("https://") or image.startswith("/")


def get_effective_discount(deal: dict) -> int:
    discount = deal.get("discount_pct") or deal.get("discount")
    try:
        discount_value = int(float(discount))
    except Exception:
        discount_value = 0
    if discount_value <= 0:
        discount_value = calculate_discount_pct(deal.get("price"), deal.get("old_price"))
    return max(0, discount_value)


def is_indexable_product(deal: dict) -> bool:
    """Misma puerta SEO que generate_static_product_pages.py.

    El sitemap solo debe incluir páginas que realmente se generan y que tienen
    calidad mínima para indexarse.
    """
    title = re.sub(r"\s+", " ", str(deal.get("title") or "").strip())
    url = str(deal.get("affiliate_url") or deal.get("url") or "").strip()
    price = parse_positive_float(deal.get("price"))
    source = str(deal.get("source") or deal.get("store") or "").strip().lower()
    discount = get_effective_discount(deal)

    return bool(
        18 <= len(title) <= 140
        and (url.startswith("http://") or url.startswith("https://"))
        and price > 0
        and source
        and has_real_image(deal)
        and (discount > 0 or deal.get("editor_pick"))
    )


def add_url(urls: "OrderedDict[str, dict]", path: str, changefreq: str, priority: str, lastmod: str = "") -> None:
    full_url = f"{BASE_URL}{path}"
    if full_url not in urls:
        urls[full_url] = {
            "loc": full_url,
            "changefreq": changefreq,
            "priority": priority,
            "lastmod": lastmod or "",
        }


def main() -> None:
    deals = json.loads(DEALS_PATH.read_text(encoding="utf-8")) if DEALS_PATH.exists() else []
    seo_pages = json.loads(SEO_PAGES_PATH.read_text(encoding="utf-8")) if SEO_PAGES_PATH.exists() else []

    urls: "OrderedDict[str, dict]" = OrderedDict()
    today = date.today().isoformat()

    add_url(urls, "/", "daily", "1.0", today)

    for page in seo_pages:
        slug = str(page.get("slug") or "").strip("/")
        if slug:
            add_url(urls, f"/{slug}/", "weekly", "0.8", today)

    generated_products = 0
    skipped_products = 0
    for idx, deal in enumerate(deals):
        if not is_indexable_product(deal):
            skipped_products += 1
            continue
        slug = build_product_slug(deal, idx)
        priority = "0.7" if deal.get("is_price_drop") or deal.get("is_recent_min_price") else "0.6"
        add_url(urls, f"/producto/{slug}/", "weekly", priority, today)
        generated_products += 1

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for item in urls.values():
        lines.append("  <url>")
        lines.append(f"    <loc>{xml_escape(item['loc'])}</loc>")
        if item["lastmod"]:
            lines.append(f"    <lastmod>{xml_escape(item['lastmod'])}</lastmod>")
        lines.append(f"    <changefreq>{item['changefreq']}</changefreq>")
        lines.append(f"    <priority>{item['priority']}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    SITEMAP_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Sitemap generado correctamente con {len(urls)} URLs: {SITEMAP_PATH}")
    print(f"Productos SEO en sitemap: {generated_products}")
    print(f"Productos omitidos del sitemap por calidad SEO: {skipped_products}")


if __name__ == "__main__":
    main()
