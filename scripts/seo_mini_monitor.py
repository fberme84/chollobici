from __future__ import annotations

import os
import re
import urllib.request
import xml.etree.ElementTree as ET


BASE_URL = os.getenv("CHOLLOBICI_BASE_URL", "https://www.chollobici.com").rstrip("/")
HOME_URL = f"{BASE_URL}/"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
MAX_PRODUCT_CHECKS = int(os.getenv("SEO_MONITOR_MAX_PRODUCT_CHECKS", "12"))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CholloBiciSeoMiniMonitor/1.0",
            "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def check_home() -> list[str]:
    errors: list[str] = []
    html = fetch_text(HOME_URL)

    title_match = re.search(r"<title>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    title = (title_match.group(1).strip() if title_match else "")
    if "CholloBici" not in title or "Amazon, AliExpress y Decathlon" not in title:
        errors.append(f"Home title unexpected: {title!r}")

    if 'property="og:image"' not in html:
        errors.append("Home missing og:image meta tag")

    if 'name="twitter:title"' not in html:
        errors.append("Home missing twitter:title meta tag")

    return errors


def parse_sitemap_locs(xml_text: str) -> list[str]:
    root = ET.fromstring(xml_text)
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [
        (node.text or "").strip()
        for node in root.findall("sm:url/sm:loc", ns)
        if (node.text or "").strip()
    ]


def check_sitemap() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    sitemap_xml = fetch_text(SITEMAP_URL)
    locs = parse_sitemap_locs(sitemap_xml)

    if len(locs) < 20:
        errors.append(f"Sitemap URL count too low: {len(locs)}")

    if not any("/producto/" in loc for loc in locs):
        errors.append("Sitemap has no product URLs")

    return errors, locs


def check_price_valid_until(product_urls: list[str]) -> list[str]:
    errors: list[str] = []
    for url in product_urls[:MAX_PRODUCT_CHECKS]:
        html = fetch_text(url)
        if "priceValidUntil" in html:
            errors.append(f"Found priceValidUntil in {url}")
    return errors


def main() -> int:
    all_errors: list[str] = []

    home_errors = check_home()
    all_errors.extend(home_errors)

    sitemap_errors, locs = check_sitemap()
    all_errors.extend(sitemap_errors)

    product_urls = [loc for loc in locs if "/producto/" in loc]
    price_errors = check_price_valid_until(product_urls)
    all_errors.extend(price_errors)

    print("SEO mini monitor summary")
    print(f"- base_url: {BASE_URL}")
    print(f"- sitemap_urls: {len(locs)}")
    print(f"- checked_product_pages: {min(len(product_urls), MAX_PRODUCT_CHECKS)}")

    if all_errors:
        print("\nFAIL")
        for err in all_errors:
            print(f"- {err}")
        return 1

    print("\nPASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
