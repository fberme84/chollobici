from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "generated_deals.json"
PRODUCT_DIR = ROOT / "producto"


def slugify(value: str) -> str:
    value = str(value or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"&", " y ", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def build_safe_product_slug(product: dict) -> str:
    """
    Genera un slug corto, estable y seguro:
    - usa solo el título (recortado)
    - añade un hash corto de url/id para evitar duplicados
    - nunca mete la URL completa en el nombre de carpeta
    """
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

    if not base:
        base = "producto"

    return f"{base}-{unique_hash}"


def format_price(value) -> str:
    if value is None or value == "":
        return ""
    try:
        amount = float(value)
        return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return ""


def calculate_discount_pct(price, old_price) -> int:
    try:
        p = float(price)
        o = float(old_price)
        if o > 0 and p <= o:
            return round((o - p) / o * 100)
    except Exception:
        pass
    return 0


def get_store_label(product: dict) -> str:
    return str(
        product.get("source_label")
        or product.get("store")
        or product.get("source")
        or "Tienda"
    )


def build_canonical(slug: str) -> str:
    return f"https://www.chollobici.com/producto/{slug}/"


def clean_text(value: str, max_len: int = 160) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0].rstrip(" ,.;:-") + "…"


def build_meta_title(title: str, store: str) -> str:
    base = clean_text(title, 72)
    suffix = f" | {store} | CholloBici" if store else " | CholloBici"
    if len(base + suffix) > 90:
        base = clean_text(base, max(40, 90 - len(suffix)))
    return base + suffix


def get_abs_image_url(image: str) -> str:
    image = str(image or "").strip()
    if not image:
        return "https://www.chollobici.com/assets/placeholder-product.svg"
    if image.startswith("//"):
        return "https:" + image
    if image.startswith("http://") or image.startswith("https://"):
        return image
    if image.startswith("/"):
        return "https://www.chollobici.com" + image
    return image


def build_product_description(product: dict) -> str:
    title = str(product.get("title") or "Producto ciclista").strip()
    brand = str(product.get("brand") or "").strip()
    category_hint = str(product.get("category_hint") or product.get("category") or "").strip().lower()
    price = format_price(product.get("price"))
    old_price = format_price(product.get("old_price"))
    store = get_store_label(product)
    discount = product.get("discount_pct")
    try:
        discount = int(float(discount))
    except Exception:
        discount = calculate_discount_pct(product.get("price"), product.get("old_price"))

    category_map = {
        "cascos": "casco de ciclismo",
        "gafas": "gafas de ciclismo",
        "ropa": "ropa de ciclismo",
        "luces": "luces para bici",
        "herramientas": "herramientas para bici",
        "componentes": "componentes de bicicleta",
        "taller": "accesorios de taller para bici",
        "accesorios": "accesorios de ciclismo",
        "bolsas": "bolsa o accesorio para bicicleta",
        "hidratación": "accesorio de hidratación para ciclismo",
        "hidratacion": "accesorio de hidratación para ciclismo",
        "electrónica": "electrónica para ciclismo",
        "electronica": "electrónica para ciclismo",
    }
    category_text = category_map.get(category_hint, category_hint or "producto de ciclismo")

    bits = []
    if brand:
        bits.append(f"{brand} {category_text}")
    else:
        bits.append(title)

    if price:
        bits.append(f"con precio actual de {price}")

    if discount:
        bits.append(f"y descuento aproximado del {discount}%")

    if old_price and old_price != price:
        bits.append(f"frente a un precio anterior de {old_price}")

    bits.append(f"disponible en {store}")
    bits.append("Oferta pensada para ciclistas que buscan una compra útil, económica y fácil de comparar antes de decidir")

    text = ". ".join(bit.strip().rstrip(".") for bit in bits if bit).strip()
    return re.sub(r"\s+", " ", text).strip() + "."


def render_price_block(product: dict) -> str:
    price = format_price(product.get("price"))
    old_price = format_price(product.get("old_price"))
    discount = product.get("discount_pct")
    if discount in (None, "", 0):
        discount = calculate_discount_pct(product.get("price"), product.get("old_price"))

    bits = []
    if old_price and old_price != price:
        bits.append(f'<span class="product-old-price">{html.escape(old_price)}</span>')
    if price:
        bits.append(f'<span class="product-price">{html.escape(price)}</span>')
    if discount:
        bits.append(f'<span class="product-discount">-{int(discount)}%</span>')

    if not bits:
        return ""

    return '<div class="product-price-row">' + "".join(bits) + "</div>"


def render_badges(product: dict) -> str:
    badges = []
    store = get_store_label(product)
    if store:
        badges.append(f'<span class="badge badge-store">{html.escape(store)}</span>')

    brand = str(product.get("brand") or "").strip()
    if brand:
        badges.append(f'<span class="badge">{html.escape(brand)}</span>')

    category_hint = str(product.get("category_hint") or "").strip()
    if category_hint:
        badges.append(f'<span class="badge">{html.escape(category_hint)}</span>')

    if not badges:
        return ""
    return '<div class="product-badges">' + "".join(badges) + "</div>"


def render_schema(product: dict, slug: str) -> str:
    canonical = build_canonical(slug)
    raw_title = str(product.get("title") or "Producto ciclista").strip()
    title = clean_text(raw_title, 120)
    image = get_abs_image_url(str(product.get("image") or ""))
    description = clean_text(build_product_description(product), 500)
    price = product.get("price")
    store = get_store_label(product)
    affiliate_url = str(product.get("affiliate_url") or product.get("url") or canonical)
    brand_name = clean_text(str(product.get("brand") or store or "CholloBici"), 80)

    graph = [
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Inicio", "item": "https://www.chollobici.com/"},
                {"@type": "ListItem", "position": 2, "name": "Productos", "item": "https://www.chollobici.com/producto/"},
                {"@type": "ListItem", "position": 3, "name": title, "item": canonical},
            ],
        },
        {
            "@type": "Product",
            "name": title,
            "description": description,
            "url": canonical,
            "image": [image],
            "brand": {"@type": "Brand", "name": brand_name},
            "offers": {
                "@type": "Offer",
                "priceCurrency": "EUR",
                "availability": "https://schema.org/InStock",
                "url": affiliate_url,
                "seller": {"@type": "Organization", "name": store},
                "itemCondition": "https://schema.org/NewCondition",
                "shippingDetails": {
                    "@type": "OfferShippingDetails",
                    "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "ES"},
                    "deliveryTime": {
                        "@type": "ShippingDeliveryTime",
                        "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 3, "unitCode": "DAY"},
                        "transitTime": {"@type": "QuantitativeValue", "minValue": 1, "maxValue": 10, "unitCode": "DAY"},
                    },
                },
                "hasMerchantReturnPolicy": {
                    "@type": "MerchantReturnPolicy",
                    "applicableCountry": "ES",
                    "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                    "merchantReturnDays": 14,
                    "returnMethod": "https://schema.org/ReturnByMail",
                    "returnFees": "https://schema.org/ReturnFeesCustomerResponsibility",
                },
            },
        },
    ]

    if price not in (None, ""):
        graph[1]["offers"]["price"] = str(price)

    # Solo publicamos valoraciones/reviews si vienen en el feed. Evitamos inventarlas.
    rating = product.get("rating") or product.get("aggregateRating")
    review_count = product.get("review_count") or product.get("reviews_count")
    try:
        rating_value = float(rating)
        count_value = int(float(review_count or 0))
        if rating_value > 0 and count_value > 0:
            graph[1]["aggregateRating"] = {
                "@type": "AggregateRating",
                "ratingValue": round(rating_value, 1),
                "reviewCount": count_value,
            }
    except Exception:
        pass

    return json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False, separators=(",", ":"))


def build_html(product: dict, slug: str) -> str:
    title = str(product.get("title") or "Producto ciclista").strip()
    canonical = build_canonical(slug)
    description = clean_text(build_product_description(product), 160)
    image = str(product.get("image") or "/assets/placeholder-product.svg").strip()
    affiliate_url = str(product.get("affiliate_url") or product.get("url") or "").strip()
    brand = str(product.get("brand") or "").strip()
    category_hint = str(product.get("category_hint") or product.get("category") or "").strip()
    size = str(product.get("size") or "").strip()
    store = get_store_label(product)

    detail_note = ""
    if product.get("source") == "decathlon":
        detail_note = (
            '<p class="product-note">Ficha simplificada. '
            'Para confirmar disponibilidad y precio actualizado, consulta la tienda.</p>'
        )

    details = []
    if brand:
        details.append(f"<li><strong>Marca:</strong> {html.escape(brand)}</li>")
    if category_hint:
        details.append(f"<li><strong>Categoría:</strong> {html.escape(category_hint)}</li>")
    if size:
        details.append(f"<li><strong>Variante:</strong> {html.escape(size)}</li>")
    details.append(f"<li><strong>Tienda:</strong> {html.escape(store)}</li>")

    image_block = ""
    if image:
        image_block = (
            f'<div class="product-media"><img src="{html.escape(image, quote=True)}" '
            f'alt="{html.escape(title)}" loading="eager"></div>'
        )

    cta_block = ""
    if affiliate_url:
        cta_block = (
            '<div class="product-actions">'
            f'<a class="btn-primary" href="{html.escape(affiliate_url, quote=True)}" '
            'target="_blank" rel="noopener sponsored nofollow">Ver en tienda</a>'
            '<a class="btn-secondary" href="/">Volver a ofertas</a>'
            "</div>"
        )
    else:
        cta_block = '<div class="product-actions"><a class="btn-secondary" href="/">Volver a ofertas</a></div>'

    meta_title = build_meta_title(title, store)
    og_image = f'<meta property="og:image" content="{html.escape(get_abs_image_url(image), quote=True)}">'

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(meta_title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{html.escape(canonical, quote=True)}">
  <meta property="og:title" content="{html.escape(meta_title)}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:type" content="product">
  <meta property="og:url" content="{html.escape(canonical, quote=True)}">
  {og_image}
  <meta name="twitter:card" content="summary_large_image">
  <link rel="stylesheet" href="/styles.css">
  <style>
    .product-page {{ max-width: 960px; margin: 0 auto; padding: 24px 16px 48px; }}
    .product-card {{ background:#fff; border:1px solid #e5e7eb; border-radius:18px; overflow:hidden; }}
    .product-layout {{ display:grid; grid-template-columns: minmax(260px, 380px) 1fr; gap:24px; padding:24px; }}
    .product-media img {{ width:100%; height:auto; display:block; border-radius:14px; background:#f8fafc; }}
    .product-content h1 {{ margin:0 0 12px; line-height:1.15; }}
    .product-badges {{ display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }}
    .badge {{ display:inline-block; padding:6px 10px; border-radius:999px; background:#eef2ff; font-size:13px; }}
    .badge-store {{ background:#ecfeff; }}
    .product-price-row {{ display:flex; gap:12px; align-items:center; margin:16px 0; flex-wrap:wrap; }}
    .product-old-price {{ text-decoration:line-through; color:#6b7280; }}
    .product-price {{ font-size:30px; font-weight:800; }}
    .product-discount {{ color:#065f46; background:#d1fae5; padding:6px 10px; border-radius:999px; font-weight:700; }}
    .product-details {{ margin:18px 0; padding-left:18px; }}
    .product-details li {{ margin:8px 0; }}
    .product-actions {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:22px; }}
    .btn-primary, .btn-secondary {{ text-decoration:none; padding:12px 16px; border-radius:12px; font-weight:700; display:inline-block; }}
    .btn-primary {{ background:#111827; color:#fff; }}
    .btn-secondary {{ background:#f3f4f6; color:#111827; }}
    .product-note {{ color:#6b7280; }}
    @media (max-width: 760px) {{
      .product-layout {{ grid-template-columns: 1fr; }}
    }}
  </style>
  <script type="application/ld+json">{render_schema(product, slug)}</script>
</head>
<body>
  <main class="product-page">
    <article class="product-card">
      <div class="product-layout">
        {image_block}
        <div class="product-content">
          {render_badges(product)}
          <h1>{html.escape(title)}</h1>
          <p>{html.escape(description)}</p>
          {render_price_block(product)}
          {detail_note}
          <ul class="product-details">
            {''.join(details)}
          </ul>
          {cta_block}
        </div>
      </div>
    </article>
  </main>
</body>
</html>
"""


def load_products() -> list[dict]:
    if not DATA_PATH.exists():
        print(f"No existe {DATA_PATH}")
        return []

    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error leyendo {DATA_PATH}: {exc}")
        return []


def should_generate_detail_page(product: dict) -> bool:
    """Genera ficha si hay datos mínimos.

    Antes dependía de detail_enabled=True, pero en generated_deals.json
    no se estaba informando y se quedaban carpetas /producto/* vacías.
    Con esta regla se generan páginas reales para productos con título, precio y URL.
    """
    title = str(product.get("title") or "").strip()
    url = str(product.get("affiliate_url") or product.get("url") or "").strip()
    price = product.get("price")
    return bool(title and url and price not in (None, ""))


def main() -> None:
    products = load_products()

    if PRODUCT_DIR.exists():
        shutil.rmtree(PRODUCT_DIR)
    PRODUCT_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0

    for product in products:
        if not should_generate_detail_page(product):
            skipped += 1
            continue

        slug = build_safe_product_slug(product)
        page_dir = PRODUCT_DIR / slug
        page_dir.mkdir(parents=True, exist_ok=True)

        html_text = build_html(product, slug)
        (page_dir / "index.html").write_text(html_text, encoding="utf-8")
        generated += 1

    print(f"Páginas HTML de producto generadas: {generated}")
    print(f"Productos omitidos sin ficha local: {skipped}")


if __name__ == "__main__":
    main()