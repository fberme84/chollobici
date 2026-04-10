from __future__ import annotations

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
    return value.strip("-")


def get_deal_id(deal: dict, index: int) -> str:
    return str(
        deal.get("id")
        or deal.get("asin")
        or deal.get("url")
        or deal.get("title")
        or index
    )


def build_product_slug(deal: dict, index: int) -> str:
    return slugify(f"{deal.get('title', '')}-{get_deal_id(deal, index)}")


def add_url(urls: "OrderedDict[str, dict]", path: str, changefreq: str, priority: str, lastmod: str = "") -> None:
    full_url = f"{BASE_URL}{path}"
    if full_url not in urls:
        urls[full_url] = {
            "loc": full_url,
            "changefreq": changefreq,
            "priority": priority,
            "lastmod": lastmod or ""
        }


def main() -> None:
    deals = json.loads(DEALS_PATH.read_text(encoding="utf-8"))
    seo_pages = json.loads(SEO_PAGES_PATH.read_text(encoding="utf-8"))

    urls: "OrderedDict[str, dict]" = OrderedDict()

    add_url(urls, "/", "daily", "1.0")
    add_url(urls, "/ofertas", "daily", "0.9")

    for page in seo_pages:
        slug = str(page.get("slug") or "").strip("/")
        if slug:
            add_url(urls, f"/{slug}", "weekly", "0.8")

    categories = sorted({str(deal.get("category") or "").strip() for deal in deals if str(deal.get("category") or "").strip()})
    for category in categories:
        add_url(urls, f"/ofertas/{slugify(category)}", "daily", "0.8")

    for index, deal in enumerate(deals):
        product_slug = build_product_slug(deal, index)
        if not product_slug:
            continue
        lastmod = str(deal.get("updated_at") or deal.get("last_checked") or "").strip()
        add_url(urls, f"/producto/{product_slug}", "daily", "0.7", lastmod)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
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
