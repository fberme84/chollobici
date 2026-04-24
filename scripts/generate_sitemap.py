from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import OrderedDict
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


def build_safe_product_slug(product: dict) -> str:
    title = str(product.get("title") or "producto").strip()
    base = slugify(title)[:70].rstrip("-")
    unique_source = (
        str(product.get("product_id") or "")
        or str(product.get("id") or "")
        or str(product.get("affiliate_url") or "")
        or str(product.get("url") or "")
        or title
    )
    unique_hash = hashlib.md5(unique_source.encode("utf-8")).hexdigest()[:10]
    return f"{base or 'producto'}-{unique_hash}"


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


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
    deals = load_json(DEALS_PATH, [])
    seo_pages = load_json(SEO_PAGES_PATH, [])

    urls: "OrderedDict[str, dict]" = OrderedDict()
    add_url(urls, "/", "daily", "1.0")

    for page in seo_pages:
        slug = str(page.get("slug") or "").strip("/")
        if slug:
            add_url(urls, f"/{slug}/", "weekly", "0.8")

    for product in deals:
        if product.get("detail_enabled"):
            slug = build_safe_product_slug(product)
            if slug:
                add_url(urls, f"/producto/{slug}/", "weekly", "0.6")

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


if __name__ == "__main__":
    main()
