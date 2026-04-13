from __future__ import annotations
import json
import re
import unicodedata
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://www.chollobici.com"
DEALS_PATH = ROOT / "data" / "generated_deals.json"
OUTPUT_DIR = ROOT / "producto"

def slugify(text: str) -> str:
    value = str(text or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"&", " y ", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")

def short_product_slug(title: str, pid: str, max_prefix: int = 42) -> str:
    prefix = slugify(title)[:max_prefix].rstrip("-")
    pid = slugify(str(pid))
    return f"{prefix}-{pid}" if prefix else pid

def get_deal_id(deal: dict, index: int) -> str:
    return str(deal.get("id") or deal.get("asin") or deal.get("url") or deal.get("title") or index)

def build_product_slug(deal: dict, index: int) -> str:
    return short_product_slug(deal.get("title", ""), get_deal_id(deal, index))

def format_price(value) -> str:
    try:
        amount = float(value)
        return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "Ver en tienda"

def to_text(value, fallback: str) -> str:
    text = str(value or "").strip()
    return text if text else fallback

def schema_safe_name(text: str, max_length: int = 150) -> str:
    clean = " ".join(str(text or "").split()).strip()
    if not clean:
        return "Producto ciclista"
    return clean[: max_length - 1].rstrip() + "…" if len(clean) > max_length else clean

def build_description(deal: dict) -> str:
    title = to_text(deal.get("title"), "Producto ciclista")
    category = to_text(deal.get("category"), "ciclismo")
    store = to_text(deal.get("source_label") or deal.get("store"), "tienda")
    price = format_price(deal.get("price")) if deal.get("price") not in (None, "") else "precio disponible en tienda"
    discount = int(round(float(deal.get("discount_pct") or 0)))
    sales = deal.get("sales")
    rating = deal.get("rating")
    parts = [f"{title}.", f"Oferta dentro de la categoría {category.lower()} en {store}."]
    if deal.get("price") not in (None, ""):
        parts.append(f"Precio actual: {price}.")
    if discount:
        parts.append(f"Descuento visible del {discount}% frente al precio anterior.")
    if sales:
        try:
            parts.append(f"Más de {int(sales):,}".replace(",", ".") + " ventas registradas.")
        except Exception:
            pass
    if rating:
        parts.append(f"Valoración visible de {rating}.")
    return " ".join(parts)

def build_reason_paragraphs(deal: dict) -> list[str]:
    category = to_text(deal.get("category"), "ciclismo").lower()
    store = to_text(deal.get("source_label") or deal.get("store"), "tienda")
    discount = int(round(float(deal.get("discount_pct") or 0)))
    sales = deal.get("sales")
    rating = deal.get("rating")
    price = format_price(deal.get("price")) if deal.get("price") not in (None, "") else "precio disponible en tienda"
    paragraphs = [
        f"Esta ficha reúne la información principal de la oferta para que puedas valorar rápido si encaja con lo que buscas dentro de {category}. Hemos dejado visible el precio actual, el acceso directo a la tienda y los datos básicos para comparar mejor antes de comprar.",
        f"El producto está publicado en {store} y actualmente aparece con un precio de {price}{f' y un descuento del {discount}%' if discount else ''}. Esto no significa necesariamente que sea la mejor opción para todo el mundo, pero sí que merece una revisión si estabas buscando algo similar y querías detectar una bajada de precio sin perder tiempo."
    ]
    extra = []
    if sales:
        try:
            extra.append(f"{int(sales):,}".replace(",", ".") + " ventas")
        except Exception:
            pass
    if rating:
        extra.append(f"valoración {rating}")
    if extra:
        paragraphs.append("Como referencia adicional, esta oferta cuenta con " + " y ".join(extra) + ", lo que puede ayudarte a priorizarla frente a otras alternativas.")
    else:
        paragraphs.append("Para decidir mejor, te recomendamos comparar también con otras ofertas relacionadas de la misma categoría que aparecen más abajo en esta página.")
    return paragraphs

def build_product_jsonld(safe_name, description, image, brand, store, price_value, affiliate, canonical, category, cat_slug, rating_value, sales_value):
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Inicio", "item": f"{BASE_URL}/"},
                    {"@type": "ListItem", "position": 2, "name": "Ofertas", "item": f"{BASE_URL}/ofertas"},
                    {"@type": "ListItem", "position": 3, "name": category, "item": f"{BASE_URL}/ofertas/{cat_slug}"},
                    {"@type": "ListItem", "position": 4, "name": safe_name, "item": canonical}
                ]
            },
            {
                "@type": "Product",
                "name": safe_name,
                "image": [image],
                "description": description,
                "brand": {"@type": "Brand", "name": brand},
                "offers": {
                    "@type": "Offer",
                    "priceCurrency": "EUR",
                    "price": str(price_value or ""),
                    "availability": "https://schema.org/InStock",
                    "url": affiliate,
                    "shippingDetails": {
                        "@type": "OfferShippingDetails",
                        "shippingRate": {"@type": "MonetaryAmount", "value": 0, "currency": "EUR"},
                        "shippingDestination": {"@type": "DefinedRegion", "addressCountry": "ES"},
                        "deliveryTime": {
                            "@type": "ShippingDeliveryTime",
                            "handlingTime": {"@type": "QuantitativeValue", "minValue": 0, "maxValue": 1, "unitCode": "DAY"},
                            "transitTime": {"@type": "QuantitativeValue", "minValue": 2, "maxValue": 5, "unitCode": "DAY"}
                        }
                    },
                    "hasMerchantReturnPolicy": {
                        "@type": "MerchantReturnPolicy",
                        "applicableCountry": "ES",
                        "returnPolicyCategory": "https://schema.org/MerchantReturnFiniteReturnWindow",
                        "merchantReturnDays": 14,
                        "returnFees": "https://schema.org/FreeReturn",
                        "returnMethod": "https://schema.org/ReturnByMail"
                    }
                }
            }
        ]
    }
    if rating_value:
        data["@graph"][1]["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": rating_value,
            "reviewCount": sales_value or 1,
            "ratingCount": sales_value or 1,
            "bestRating": 100,
            "worstRating": 0
        }
        data["@graph"][1]["review"] = [{
            "@type": "Review",
            "reviewRating": {"@type": "Rating", "ratingValue": rating_value, "bestRating": 100, "worstRating": 0},
            "author": {"@type": "Organization", "name": store},
            "reviewBody": f"Valoración visible del producto en {store}."
        }]
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))

def main():
    deals = json.loads(DEALS_PATH.read_text(encoding="utf-8"))
    if OUTPUT_DIR.exists():
        for path in sorted(OUTPUT_DIR.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
    OUTPUT_DIR.mkdir(exist_ok=True)

    for idx, deal in enumerate(deals):
        slug = build_product_slug(deal, idx)
        page_dir = OUTPUT_DIR / slug
        page_dir.mkdir(parents=True, exist_ok=True)

        title = to_text(deal.get("title"), "Oferta ciclista")
        safe_name = schema_safe_name(title)
        category = to_text(deal.get("category"), "Ciclismo")
        cat_slug = slugify(category)
        brand = to_text(deal.get("brand"), "Selección destacada")
        store = to_text(deal.get("source_label") or deal.get("store"), "Tienda")
        image = to_text(deal.get("image"), "/assets/chollobici-logo.png")
        affiliate = to_text(deal.get("affiliate_url") or deal.get("url"), "#")
        canonical = f"{BASE_URL}/producto/{slug}/"
        description = build_description(deal)
        price = format_price(deal.get("price")) if deal.get("price") not in (None, "") else "Ver en tienda"
        old_price = format_price(deal.get("old_price")) if deal.get("old_price") not in (None, "") else ""
        discount = int(round(float(deal.get("discount_pct") or 0)))
        checked = to_text(deal.get("last_checked") or deal.get("updated_at"), "sin fecha")
        rating_value = deal.get("rating")
        sales_value = int(deal.get("sales") or 0) if str(deal.get("sales") or "").strip() else 0

        same_category = [(j, d) for j, d in enumerate(deals) if j != idx and str(d.get("category") or "").strip().lower() == str(deal.get("category") or "").strip().lower()]
        if len(same_category) < 4:
            extras = [(j, d) for j, d in enumerate(deals) if j != idx and (j, d) not in same_category]
            same_category.extend(extras)
        related = same_category[:4]

        related_html = []
        for j, rel in related:
            rel_slug = build_product_slug(rel, j)
            rel_title = to_text(rel.get("title"), "Oferta relacionada")
            rel_desc = build_description(rel)
            rel_price = format_price(rel.get("price")) if rel.get("price") not in (None, "") else "Ver en tienda"
            related_html.append(f'''
              <article class="related-card">
                <span class="badge">{escape(to_text(rel.get("category"), "Ciclismo"))}</span>
                <h3><a href="/producto/{escape(rel_slug)}/">{escape(rel_title)}</a></h3>
                <div class="related-price">{escape(rel_price)}</div>
                <p>{escape(rel_desc[:120].rstrip())}{"..." if len(rel_desc) > 120 else ""}</p>
                <a href="/producto/{escape(rel_slug)}/">Ver ficha →</a>
              </article>
            ''')

        reason_html = "".join(f"<p>{escape(par)}</p>" for par in build_reason_paragraphs(deal))
        schema = build_product_jsonld(safe_name, description, image, brand, store, deal.get("price"), affiliate, canonical, category, cat_slug, rating_value, sales_value)

        html_content = f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} al mejor precio | CholloBici</title>
  <meta name="description" content="{escape(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="product">
  <meta property="og:title" content="{escape(title)} al mejor precio | CholloBici">
  <meta property="og:description" content="{escape(description)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{escape(image)}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)} al mejor precio | CholloBici">
  <meta name="twitter:description" content="{escape(description)}">
  <meta name="twitter:image" content="{escape(image)}">
  <link rel="icon" type="image/png" href="/assets/favicon-chollobici.png">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/static-product.css">
  <script type="application/ld+json">{schema}</script>
</head>
<body>
  <header class="site-top">
    <div class="wrap site-top-inner">
      <a href="/"><img src="/assets/chollobici-logo.png" alt="CholloBici" class="site-logo"></a>
      <nav class="site-top-nav" aria-label="Navegación principal">
        <a href="/">Inicio</a>
        <a href="/ofertas">Ofertas</a>
        <a href="/ofertas/{cat_slug}">Más de {escape(category)}</a>
      </nav>
    </div>
  </header>

  <main class="wrap">
    <nav class="breadcrumbs" aria-label="Migas de pan">
      <a href="/">Inicio</a><span class="sep">·</span>
      <a href="/ofertas">Ofertas</a><span class="sep">·</span>
      <a href="/ofertas/{cat_slug}">{escape(category)}</a><span class="sep">·</span>
      <span>{escape(title)}</span>
    </nav>

    <article class="product-card">
      <div class="product-layout">
        <div class="media-card">
          <img src="{escape(image)}" alt="{escape(title)}" loading="eager">
        </div>
        <div class="product-copy">
          <div class="meta-row">
            <span class="badge">{escape(category)}</span>
            <span class="badge">{escape(store)}</span>
          </div>
          <h1>{escape(title)}</h1>
          <div class="price-row">
            <span class="price-main">{escape(price)}</span>
            {"<span class='price-old'>" + escape(old_price) + "</span>" if old_price else ""}
          </div>
          <div class="metric-row">
            {f"<span class='metric discount'>Descuento {discount}%</span>" if discount else ""}
            <span class="metric store">Tienda: {escape(store)}</span>
            <span class="metric review">Revisado: {escape(checked)}</span>
          </div>
          {reason_html}
          <div class="cta-row">
            <a class="btn btn-primary" href="{escape(affiliate)}" target="_blank" rel="noopener sponsored nofollow">Ver oferta en {escape(store)}</a>
            <a class="btn btn-light" href="/ofertas/{cat_slug}">Más ofertas de {escape(category)}</a>
          </div>
        </div>
      </div>
    </article>

    <section class="section">
      <h2>Por qué puede merecer la pena</h2>
      <p>Esta página está pensada para ofrecer una ficha clara y directa del producto, con datos visibles de precio, descuento y acceso a tienda. Así Google puede rastrear mejor el contenido y tú puedes comparar rápido antes de salir a comprar.</p>
      <p>Si estás revisando varias alternativas, lo más útil suele ser comparar esta oferta con otros productos de la misma categoría. Por eso enlazamos opciones similares justo debajo para facilitar la navegación y el descubrimiento de nuevos chollos.</p>
    </section>

    <section class="section">
      <h2>Productos relacionados</h2>
      <div class="related-grid">
        {''.join(related_html)}
      </div>
    </section>

    <p class="footer-note">Aviso: los precios y descuentos pueden cambiar con el tiempo. Comprueba siempre el importe final antes de completar la compra en la tienda de destino.</p>
  </main>
</body>
</html>'''
        (page_dir / "index.html").write_text(html_content, encoding="utf-8")

    print(f"Páginas HTML de producto generadas: {len(deals)}")

if __name__ == "__main__":
    main()
