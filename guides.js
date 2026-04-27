const GUIDE_STATE = { deals: [] };

function guideFormatPrice(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num <= 0) return '';
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(num);
}

function guideDiscount(deal) {
  return Math.max(Number(deal.discount_pct || 0), Number(deal.drop_vs_previous_pct || 0));
}

function guidePlaceholderImage(title, store) {
  const safeTitle = String(title || 'Oferta CholloBici').replace(/[&<>"']/g, '');
  const safeStore = String(store || 'Tienda').replace(/[&<>"']/g, '');
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420"><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#eff6ff"/><stop offset="100%" stop-color="#dbeafe"/></linearGradient></defs><rect width="640" height="420" fill="url(#bg)"/><rect x="28" y="28" width="130" height="38" rx="19" fill="#071b35"/><text x="93" y="53" text-anchor="middle" font-family="Arial" font-size="15" font-weight="700" fill="#fff">${safeStore}</text><g opacity="0.20" stroke="#0d63c9" stroke-width="15" fill="none" stroke-linecap="round" stroke-linejoin="round"><circle cx="205" cy="272" r="72"/><circle cx="445" cy="272" r="72"/><path d="M205 272 L300 178 L382 178 L445 272 M300 178 L268 272 M300 178 L338 272"/></g><text x="320" y="176" text-anchor="middle" font-family="Arial" font-size="30" font-weight="700" fill="#0f172a">Imagen pendiente</text><text x="320" y="214" text-anchor="middle" font-family="Arial" font-size="18" fill="#334155">${safeTitle.slice(0, 46)}</text></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function guideMatches(deal, keywords) {
  const text = [deal.title, deal.category, deal.store, deal.reason, deal.source].filter(Boolean).join(' ').toLowerCase();
  return keywords.some(keyword => text.includes(keyword.trim().toLowerCase()));
}

function guideSort(deals) {
  return [...deals].sort((a, b) => {
    const scoreA = Number(a.recomendacion || 0) + guideDiscount(a);
    const scoreB = Number(b.recomendacion || 0) + guideDiscount(b);
    return scoreB - scoreA;
  });
}


function guideFixEscapedInternalLinks() {
  const article = document.querySelector('.guide-article');
  if (!article) return;

  article.querySelectorAll('p, li').forEach(node => {
    let html = node.innerHTML;
    if (!html.includes('&lt;a ')) return;

    html = html
      .replace(new RegExp('&lt;a\\s+href=&quot;/([^&]+?)&quot;\\s+data-link=&quot;internal&quot;&gt;(.+?)&lt;/a&gt;', 'g'), '<a href="$1.html" data-link="internal">$2</a>')
      .replace(new RegExp('&lt;a\\s+href=&quot;([^&]+?)&quot;\\s+data-link=&quot;internal&quot;&gt;(.+?)&lt;/a&gt;', 'g'), '<a href="$1" data-link="internal">$2</a>')
      .replace(new RegExp('href="/([^"#]+?)"', 'g'), 'href="$1.html"');

    node.innerHTML = html;
  });
}

function guideRenderProducts(container, products) {
  const selected = products.slice(0, 4);
  if (!selected.length) {
    container.innerHTML = '<div class="guide-empty card">Ahora mismo no hay ofertas relacionadas suficientes. Vuelve pronto: las ofertas se actualizan desde el catálogo de CholloBici.</div>';
    return;
  }
  container.innerHTML = selected.map(deal => {
    const discount = guideDiscount(deal);
    const price = guideFormatPrice(deal.price);
    const oldPrice = guideFormatPrice(deal.old_price);
    const href = deal.affiliate_url || deal.url || '#';
    const image = deal.image || guidePlaceholderImage(deal.title, deal.store);
    return `<article class="guide-product-card card"><div class="guide-product-image-wrap"><span class="badge badge-store badge-store-overlay">${deal.store || 'Tienda'}</span>${discount ? `<span class="badge badge-top-overlay">-${discount}%</span>` : ''}<img src="${image}" alt="${deal.title || 'Oferta de ciclismo'}" loading="lazy" onerror="this.src='${guidePlaceholderImage(deal.title, deal.store)}'"></div><div class="guide-product-body"><p class="guide-product-category">${deal.category || 'Ciclismo'}</p><h3>${deal.title || 'Oferta de ciclismo'}</h3><div class="guide-price-row">${price ? `<strong>${price}</strong>` : ''}${oldPrice ? `<span>${oldPrice}</span>` : ''}</div><p>${deal.reason || 'Oferta seleccionada por CholloBici por su relación calidad/precio.'}</p><a class="btn" href="${href}" target="_blank" rel="noopener sponsored nofollow">Ver chollo</a></div></article>`;
  }).join('');
}

async function guideInit() {
  guideFixEscapedInternalLinks();
  const containers = [...document.querySelectorAll('.guide-products')];
  if (!containers.length) return;
  try {
    const response = await fetch('../data/generated_deals.json', { cache: 'no-store' });
    const data = await response.json();
    GUIDE_STATE.deals = Array.isArray(data) ? data : [];
    const sorted = guideSort(GUIDE_STATE.deals);
    containers.forEach(container => {
      const keywords = (container.dataset.keywords || '').split(',').map(x => x.trim()).filter(Boolean);
      const matched = sorted.filter(deal => guideMatches(deal, keywords));
      guideRenderProducts(container, matched.length ? matched : sorted);
    });
  } catch (error) {
    containers.forEach(container => {
      container.innerHTML = '<div class="guide-empty card">No se han podido cargar las ofertas en este momento.</div>';
    });
    console.error(error);
  }
}

guideInit();
