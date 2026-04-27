from __future__ import annotations

import json
import re
import shutil
import unicodedata
from html import escape, unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_URL = 'https://www.chollobici.com'
SEO_PAGES_PATH = ROOT / 'data' / 'seo_pages.json'
DEALS_PATH = ROOT / 'data' / 'generated_deals.json'


def slugify(text: str) -> str:
    value = str(text or '').strip().lower()
    value = unicodedata.normalize('NFD', value)
    value = ''.join(ch for ch in value if unicodedata.category(ch) != 'Mn')
    value = re.sub(r'&', ' y ', value)
    value = re.sub(r'[^a-z0-9]+', '-', value)
    return value.strip('-')


def short_product_slug(title: str, pid: str, max_prefix: int = 42) -> str:
    prefix = slugify(title)[:max_prefix].rstrip('-')
    pid = slugify(str(pid))
    return f"{prefix}-{pid}" if prefix else pid


def get_deal_id(deal: dict, index: int) -> str:
    return str(deal.get('id') or deal.get('asin') or deal.get('url') or deal.get('title') or index)


def build_product_slug(deal: dict, index: int) -> str:
    return short_product_slug(deal.get('title', ''), get_deal_id(deal, index))


def format_price(value) -> str:
    try:
        amount = float(value)
        return f"{amount:,.2f} €".replace(',', 'X').replace('.', ',').replace('X', '.')
    except Exception:
        return ''


def get_store_label(deal: dict) -> str:
    return str(deal.get('source_label') or deal.get('store') or deal.get('source') or 'Tienda')


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def pick_related_deals(page: dict, deals: list[dict]) -> list[tuple[int, dict]]:
    category = str(page.get('category') or '').strip().lower()
    selected = [
        (idx, deal)
        for idx, deal in enumerate(deals)
        if not category or str(deal.get('category') or '').strip().lower() == category
    ]
    selected.sort(
        key=lambda item: ((item[1].get('recomendacion') or 0) + (item[1].get('discount_pct') or 0)),
        reverse=True,
    )
    return selected[:12]


def render_related_offer_list(related_deals: list[tuple[int, dict]]) -> str:
    if not related_deals:
        return ''
    items: list[str] = []
    for idx, deal in related_deals:
        slug = build_product_slug(deal, idx)
        product_href = f'/producto/{slug}/'
        shop_href = escape(deal.get('affiliate_url') or deal.get('url') or '#', quote=True)
        title = escape(deal.get('title') or 'Producto')
        meta_parts = [escape(deal.get('category') or 'Categoría'), escape(get_store_label(deal))]
        price = format_price(deal.get('price'))
        if price:
            meta_parts.append(price)
        meta_html = ' <span>·</span> '.join(f'<span>{part}</span>' for part in meta_parts)
        items.append(
            '<li class="guide-link-item">'
            f'<a href="{product_href}" class="guide-link-main">{title}</a>'
            f'<div class="guide-link-meta">{meta_html}</div>'
            '<div class="guide-link-actions">'
            f'<a href="{product_href}" class="guide-inline-link">Ver ficha</a>'
            f'<a href="{shop_href}" target="_blank" rel="noopener sponsored nofollow" class="guide-inline-link">Ver en tienda</a>'
            '</div>'
            '</li>'
        )
    return '<ul class="guide-links-list">' + ''.join(items) + '</ul>'


def render_featured_deals(related_deals: list[tuple[int, dict]]) -> str:
    if not related_deals:
        return ''
    cards: list[str] = []
    for idx, deal in related_deals[:2]:
        slug = build_product_slug(deal, idx)
        product_href = f'/producto/{slug}/'
        shop_href = escape(deal.get('affiliate_url') or deal.get('url') or '#', quote=True)
        title = escape(deal.get('title') or 'Producto recomendado')
        category = escape(deal.get('category') or 'Producto recomendado')
        image = escape(deal.get('image') or '/assets/chollobici-logo.png', quote=True)
        price = format_price(deal.get('price'))
        reason = escape(deal.get('reason') or '')

        price_html = f'<div class="guide-featured-price">{price}</div>' if price else ''
        reason_html = f'<p class="guide-featured-reason">{reason}</p>' if reason else ''

        cards.append(
            '<article class="guide-featured-card">'
            f'<a href="{product_href}" class="guide-featured-media"><img src="{image}" alt="{title}" loading="lazy"></a>'
            '<div class="guide-featured-content">'
            '<div class="guide-featured-top">'
            f'<span class="guide-featured-store">{escape(get_store_label(deal))}</span>'
            f'{price_html}'
            '</div>'
            f'<h3><a href="{product_href}">{title}</a></h3>'
            f'<p class="guide-featured-meta">{category}</p>'
            f'{reason_html}'
            '<div class="guide-featured-actions">'
            f'<a href="{product_href}" class="guide-inline-link">Ver ficha</a>'
            f'<a href="{shop_href}" target="_blank" rel="noopener sponsored nofollow" class="guide-inline-link">Ver en tienda</a>'
            '</div>'
            '</div>'
            '</article>'
        )
    return '<div class="guide-featured-grid">' + ''.join(cards) + '</div>'


def render_faq(page: dict) -> str:
    faq = page.get('faq') or []
    if not faq:
        return ''
    items = []
    for question, answer in faq:
        items.append(f'<details class="guide-faq-item"><summary>{escape(question)}</summary><p>{escape(answer)}</p></details>')
    return '<div class="guide-faq-block"><h3>Preguntas frecuentes</h3>' + ''.join(items) + '</div>'


def render_related_guides(current_slug: str, page: dict, all_pages: list[dict]) -> str:
    preferred = [slug for slug in (page.get('relatedGuideSlugs') or []) if slug and slug != current_slug]
    ordered: list[dict] = []
    for slug in preferred:
        match = next((p for p in all_pages if p.get('slug') == slug), None)
        if match and all(existing.get('slug') != slug for existing in ordered):
            ordered.append(match)
    for guide in all_pages:
        slug = guide.get('slug')
        if not slug or slug == current_slug or any(existing.get('slug') == slug for existing in ordered):
            continue
        ordered.append(guide)
    ordered = ordered[:4]
    items = ''.join(
        f'<li><a href="/{escape(guide["slug"].strip("/"))}/">{escape(guide.get("introTitle") or guide["slug"])}</a></li>'
        for guide in ordered
    )
    return '<div class="guide-related-block"><h3>Otras guías que te pueden interesar</h3><ul>' + items + '</ul></div>'


def build_schema(page: dict, slug: str) -> str:
    canonical = f'{BASE_URL}/{slug}/'
    faq_entities = []
    for item in page.get('faq') or []:
        if len(item) >= 2:
            faq_entities.append({
                '@type': 'Question',
                'name': item[0],
                'acceptedAnswer': {'@type': 'Answer', 'text': item[1]},
            })
    graph = [
        {
            '@type': 'BreadcrumbList',
            'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'Inicio', 'item': f'{BASE_URL}/'},
                {'@type': 'ListItem', 'position': 2, 'name': page.get('introTitle') or slug, 'item': canonical},
            ],
        },
        {
            '@type': 'Article',
            'headline': page.get('introTitle') or slug,
            'description': page.get('description') or '',
            'url': canonical,
            'mainEntityOfPage': canonical,
            'author': {'@type': 'Organization', 'name': 'CholloBici'},
            'publisher': {'@type': 'Organization', 'name': 'CholloBici'},
        },
    ]
    if faq_entities:
        graph.append({'@type': 'FAQPage', 'mainEntity': faq_entities})
    return json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, separators=(',', ':'))


def render_rich_text(value: str) -> str:
    """Renderiza texto controlado de guías permitiendo enlaces internos ya definidos."""
    text = unescape(str(value or ''))
    allowed_links: list[str] = []

    def keep_link(match):
        href = match.group(1)
        label = match.group(2)
        if re.fullmatch(r'/[a-z0-9-]+/?', href or ''):
            clean_href = href if href.endswith('/') else href + '/'
            token = f'__CHOLLOBICI_LINK_{len(allowed_links)}__'
            allowed_links.append(f'<a href="{escape(clean_href, quote=True)}" data-link="internal">{escape(label)}</a>')
            return token
        return escape(match.group(0))

    text = re.sub(r'<a\s+href=["\']([^"\']+)["\']\s+data-link=["\']internal["\']>(.*?)</a>', keep_link, text)
    text = escape(text)
    for idx, link in enumerate(allowed_links):
        text = text.replace(f'__CHOLLOBICI_LINK_{idx}__', link)
    return text


def build_page_html(page: dict, all_pages: list[dict], deals: list[dict]) -> str:
    slug = str(page.get('slug') or '').strip('/')
    canonical = f'{BASE_URL}/{slug}/'
    related_deals = pick_related_deals(page, deals)

    if page.get('articleParagraphs'):
        paragraph_values = page.get('articleParagraphs') or []
    else:
        paragraph_values = [page.get('introText') or page.get('description') or '']
    paragraphs = ''.join(f'<p>{render_rich_text(p)}</p>' for p in paragraph_values)

    article_lead = ''
    if page.get('articleLead'):
        article_lead = f'<div class="guide-article-block guide-lead-block"><p>{render_rich_text(page.get("articleLead"))}</p></div>'

    featured_html = render_featured_deals(related_deals)
    featured_block = (
        '<div class="guide-article-block guide-featured-block">'
        '<h2>Productos destacados de esta guía</h2>'
        '<p class="guide-helper-text">Una selección rápida con dos opciones especialmente interesantes para empezar a comparar.</p>'
        f'{featured_html}'
        '</div>'
    ) if featured_html else ''

    related_offers = render_related_offer_list(related_deals)
    related_offers_block = (
        '<div class="guide-article-block guide-related-offers-block">'
        f'<h2>{escape(page.get("linksTitle") or "Ofertas relacionadas")}</h2>'
        f'<p class="guide-helper-text">{escape(page.get("linksIntro") or "Hemos reunido aquí las ofertas más relevantes de esta temática para que puedas compararlas rápidamente.")}</p>'
        f'{related_offers}'
        '</div>'
    ) if related_offers else ''

    related_guides_block = render_related_guides(slug, page, all_pages)
    faq_block = render_faq(page)
    schema_json = build_schema(page, slug)
    title = escape(page.get('metaTitle') or page.get('introTitle') or 'Guía de compra | CholloBici')
    description = escape(page.get('description') or page.get('introText') or '')
    intro_title = escape(page.get('introTitle') or 'Guía de compra')
    kicker = escape(page.get('kicker') or 'Guía de compra')
    intro_text = escape(page.get('introText') or page.get('description') or '')
    closing_title = escape(page.get('closingTitle') or 'Consejos finales')
    closing_text = escape(page.get('closingText') or '')
    current_year_script = "<script>document.addEventListener('DOMContentLoaded',function(){var y=document.getElementById('currentYear');if(y){y.textContent=new Date().getFullYear();}});</script>"

    return f'''<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <link rel="canonical" href="{canonical}">
  <meta property="og:site_name" content="CholloBici">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <link rel="icon" type="image/png" href="/assets/favicon-chollobici.png">
  <link rel="apple-touch-icon" href="/assets/favicon-chollobici.png">
  <link rel="stylesheet" href="/styles.css">
  <script type="application/ld+json">{schema_json}</script>
</head>
<body>
  <header class="hero">
    <div class="wrap hero-inner">
      <div class="hero-brand card-glass">
        <a href="/" aria-label="Volver a inicio"><img src="/assets/chollobici-logo.png" alt="CholloBici" class="logo-main"></a>
        <div class="hero-copy">
          <span class="hero-kicker">Detector de ofertas ciclistas</span>
          <h1>{intro_title}</h1>
          <p>{intro_text}</p>
          <div class="hero-pills">
            <span class="hero-pill">Guia estatica indexable</span>
            <span class="hero-pill">Contenido util y ofertas relacionadas</span>
            <span class="hero-pill"><a href="/" style="color:inherit;text-decoration:none;">Ver todas las ofertas</a></span>
          </div>
        </div>
      </div>
    </div>
  </header>

  <main class="wrap page-main">
    <nav class="breadcrumbs">
      <a href="/">Inicio</a> <span>/</span> <span>{intro_title}</span>
    </nav>

    <article class="guide-article card">
      <header class="guide-hero-block">
        <span class="section-kicker">{kicker}</span>
        <h1>{intro_title}</h1>
        <p class="guide-hero-text">{intro_text}</p>
      </header>

      {article_lead}

      <div class="guide-article-block">
        {paragraphs}
      </div>

      {featured_block}

      <div class="guide-article-block">
        <h2>{closing_title}</h2>
        <p>{closing_text}</p>
      </div>

      {related_offers_block}
      {faq_block}
      {related_guides_block}
    </article>
  </main>

  <footer class="site-footer">
    <div class="wrap footer-inner">
      <div>
        <strong>CholloBici</strong>
        <p>Seleccionamos ofertas ciclistas y publicamos guias utiles para comprar mejor.</p>
      </div>
      <nav class="footer-links" aria-label="Enlaces de pie">
        <a href="/">Inicio</a>
        <a href="/robots.txt">Robots</a>
        <a href="/sitemap.xml">Sitemap</a>
      </nav>
      <div class="footer-copy">© <span id="currentYear"></span> CholloBici</div>
    </div>
  </footer>
  {current_year_script}
</body>
</html>
'''


def main() -> None:
    pages = load_json(SEO_PAGES_PATH)
    deals = load_json(DEALS_PATH)
    for page in pages:
        slug = str(page.get('slug') or '').strip('/')
        if not slug:
            continue
        page_dir = ROOT / slug
        if page_dir.exists():
            shutil.rmtree(page_dir)
        page_dir.mkdir(parents=True, exist_ok=True)
        (page_dir / 'index.html').write_text(build_page_html(page, pages, deals), encoding='utf-8')
    print(f'Guías estáticas generadas: {len(pages)}')


if __name__ == '__main__':
    main()
