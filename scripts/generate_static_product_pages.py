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


def build_product_description(product: dict) -> str:
    title = str(product.get("title") or "Producto ciclista").strip()
    brand = str(product.get("brand") or "").strip()
    category_hint = str(product.get("category_hint") or product.get("category") or "").strip()
    price = format_price(product.get("price"))
    old_price = format_price(product.get("old_price"))
    store = get_store_label(product)

    parts = [title]
    if brand:
        parts.append(f"de {brand}")
    if category_hint:
        parts.append(f"en la categoría {category_hint}")
    if price:
        parts.append(f"por {price}")
    if old_price and old_price != price:
        parts.append(f"antes {old_price}")
    parts.append(f"en {store}")

    text = " ".join(parts)
    return re.sub(r"\s+", " ", text).strip()


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
    title = str(product.get("title") or "Producto ciclista").strip()
    image = str(product.get("image") or "").strip()
    description = build_product_description(product)
    price = product.get("price")
    store = get_store_label(product)

    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": title,
        "description": description,
        "url": canonical,
        "brand": {"@type": "Brand", "name": str(product.get("brand") or store or "CholloBici")},
    }

    if image:
        schema["image"] = image

    if price not in (None, ""):
        schema["offers"] = {
            "@type": "Offer",
            "priceCurrency": "EUR",
            "price": str(price),
            "availability": "https://schema.org/InStock",
            "url": str(product.get("affiliate_url") or product.get("url") or canonical),
            "seller": {"@type": "Organization", "name": store},
        }

    return json.dumps(schema, ensure_ascii=False)


def build_html(product: dict, slug: str) -> str:
    title = str(product.get("title") or "Producto ciclista").strip()
    canonical = build_canonical(slug)
    description = build_product_description(product)
    image = str(product.get("image") or "").strip()
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

    og_image = ""
    if image:
        og_image = f'<meta property="og:image" content="{html.escape(image, quote=True)}">'

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(title)} | CholloBici</title>
  <meta name="description" content="{html.escape(description)}">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{html.escape(canonical, quote=True)}">
  <meta property="og:title" content="{html.escape(title)} | CholloBici">
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
    """
    Regla crítica:
    - si detail_enabled es False, NO se genera ficha
    - esto evita rutas largas innecesarias y fichas poco fiables
    """
    return bool(product.get("detail_enabled"))


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