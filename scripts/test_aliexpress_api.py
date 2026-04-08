from __future__ import annotations

import json
import os

from aliexpress_api import AliExpressApiError, generate_affiliate_links, product_query


def main() -> None:
    tracking_id = os.getenv("ALIEXPRESS_TRACKING_ID", "").strip()
    print("Probando conexión con AliExpress API...")
    print(f"Tracking ID configurado: {'sí' if tracking_id else 'no'}")

    try:
        products = product_query(
            keywords="ciclismo",
            page_no=1,
            page_size=3,
            tracking_id=tracking_id,
            target_currency=os.getenv("ALIEXPRESS_TARGET_CURRENCY", "EUR"),
            target_language=os.getenv("ALIEXPRESS_TARGET_LANGUAGE", "ES"),
            ship_to_country=os.getenv("ALIEXPRESS_SHIP_TO_COUNTRY", "ES"),
        )
    except AliExpressApiError as exc:
        print(f"ERROR API: {exc}")
        raise SystemExit(1)

    print(f"Productos devueltos: {len(products)}")
    preview = products[:3]
    print(json.dumps(preview, ensure_ascii=False, indent=2)[:4000])

    if tracking_id and preview:
        urls = []
        for item in preview:
            url = item.get("product_detail_url") or item.get("productUrl") or item.get("promotion_link")
            if url:
                urls.append(url)
        if urls:
            try:
                links = generate_affiliate_links(urls[:1], tracking_id=tracking_id)
                print("Ejemplo link afiliado:")
                print(json.dumps(links, ensure_ascii=False, indent=2))
            except AliExpressApiError as exc:
                print(f"WARN link.generate: {exc}")


if __name__ == "__main__":
    main()
