const state = {
  deals: [],
  filtered: [],
  favorites: JSON.parse(localStorage.getItem('favorites') || '[]')
};

const els = {
  grid: document.getElementById('dealsGrid'),
  info: document.getElementById('dealsInfo'),
  stats: document.getElementById('stats'),
  search: document.getElementById('searchInput'),
  category: document.getElementById('categoryFilter'),
  store: document.getElementById('storeFilter'),
  discount: document.getElementById('discountFilter'),
  sort: document.getElementById('sortFilter'),
  template: document.getElementById('dealCardTemplate')
};

function formatPrice(value) {
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency: 'EUR'
  }).format(value);
}

function formatCheckedDate(value) {
  if (!value) return 'sin fecha';
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('es-ES');
}


function isRecentDate(value, days = 7) {
  if (!value) return false;
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return false;
  const diffDays = (Date.now() - date.getTime()) / (1000 * 60 * 60 * 24);
  return diffDays <= days;
}

function getDealId(deal) {
  return deal.id || deal.asin || deal.url || deal.title || String(Math.random());
}

function isFavorite(deal) {
  return state.favorites.includes(getDealId(deal));
}

function toggleFavorite(deal) {
  const id = getDealId(deal);
  if (state.favorites.includes(id)) {
    state.favorites = state.favorites.filter(x => x !== id);
  } else {
    state.favorites = [...state.favorites, id];
  }
  localStorage.setItem('favorites', JSON.stringify(state.favorites));
  renderDeals();
}

function getPrimaryDiscount(deal) {
  return Math.max(deal.discount_pct || 0, deal.drop_vs_previous_pct || 0);
}

function createOption(value) {
  const opt = document.createElement('option');
  opt.value = value;
  opt.textContent = value;
  return opt;
}

function placeholderImage(title, store) {
  const safeTitle = (title || 'Oferta').replace(/[&<>"]/g, '');
  const safeStore = (store || 'Tienda').replace(/[&<>"]/g, '');
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#eff6ff" />
          <stop offset="100%" stop-color="#dbeafe" />
        </linearGradient>
      </defs>
      <rect width="640" height="400" fill="url(#bg)" />
      <rect x="24" y="24" width="112" height="34" rx="17" fill="#111827" />
      <text x="80" y="46" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#ffffff">${safeStore}</text>
      <g opacity="0.18">
        <circle cx="198" cy="248" r="70" fill="none" stroke="#1d4ed8" stroke-width="14" />
        <circle cx="436" cy="248" r="70" fill="none" stroke="#1d4ed8" stroke-width="14" />
        <path d="M198 248 L292 162 L380 162 L436 248" fill="none" stroke="#1d4ed8" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" />
      </g>
      <text x="320" y="178" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="28" font-weight="700" fill="#0f172a">Imagen pendiente</text>
      <text x="320" y="216" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="20" fill="#334155">${safeTitle}</text>
    </svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function populateFilters(deals) {
  const categories = [...new Set(deals.map(d => d.category).filter(Boolean))].sort();
  const stores = [...new Set(deals.map(d => d.store).filter(Boolean))].sort();

  categories.forEach(c => els.category.appendChild(createOption(c)));
  stores.forEach(s => els.store.appendChild(createOption(s)));
}

function renderStats(deals) {
  const total = deals.length;
  const hot = deals.filter(d => d.status === 'hot').length;
  const picks = deals.filter(d => d.editor_pick).length;
  const avg = total ? Math.round(deals.reduce((sum, d) => sum + (d.discount_pct || 0), 0) / total) : 0;
  const latest = deals.length ? deals.map(d => d.last_checked).filter(Boolean).sort().reverse()[0] : null;
  const lastUpdateText = latest ? `Última actualización: ${formatCheckedDate(latest)}` : 'Última actualización: sin fecha';

  const lastUpdateEl = document.getElementById('lastUpdate');
  if (lastUpdateEl) lastUpdateEl.textContent = lastUpdateText;

  els.stats.innerHTML = `
    <span class="stat-chip">${total} ofertas</span>
    <span class="stat-chip">${hot} destacadas</span>
    <span class="stat-chip">${picks} recomendadas</span>
    <span class="stat-chip">Descuento medio ${avg}%</span>
    <span class="stat-chip">Actualizado ${latest ? formatCheckedDate(latest) : 'sin fecha'}</span>
  `;
}

function sortDeals(deals) {
  const mode = els.sort.value;

  return [...deals].sort((a, b) => {
    if (mode === 'discount') return (b.discount_pct || 0) - (a.discount_pct || 0);
    if (mode === 'price_asc') return (a.price || 0) - (b.price || 0);
    if (mode === 'price_desc') return (b.price || 0) - (a.price || 0);
    return (b.recomendacion || 0) - (a.recomendacion || 0);
  });
}

function applyFilters() {
  const search = els.search.value.trim().toLowerCase();
  const category = els.category.value;
  const store = els.store.value;
  const minDiscount = Number(els.discount.value || 0);

  const filtered = state.deals.filter(deal => {
    const text = [deal.title, deal.category, deal.store].join(' ').toLowerCase();
    return (!search || text.includes(search))
      && (!category || deal.category === category)
      && (!store || deal.store === store)
      && ((Math.max(deal.discount_pct || 0, deal.drop_vs_previous_pct || 0)) >= minDiscount);
  });

  state.filtered = sortDeals(filtered);
  renderDeals();
}

function renderDeals() {
  els.grid.innerHTML = '';
  els.info.textContent = `${state.filtered.length} resultado(s) mostrado(s)`;

  if (!state.filtered.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state card';
    empty.textContent = 'No hay ofertas que cumplan los filtros actuales.';
    els.grid.appendChild(empty);
    return;
  }

  state.filtered.forEach(deal => {
    const node = els.template.content.firstElementChild.cloneNode(true);
    const imageEl = node.querySelector('.deal-image');
    imageEl.src = deal.image || placeholderImage(deal.title, deal.store);
    imageEl.alt = deal.title;
    imageEl.onerror = () => { imageEl.src = placeholderImage(deal.title, deal.store); };

    node.querySelector('.badge-store').textContent = deal.store || 'Tienda';
    node.querySelector('.badge-status').textContent = deal.status === 'hot' ? '🔥 CHOLLO' : 'Oferta';

    const pickBadge = node.querySelector('.badge-pick');
    if (deal.editor_pick) {
      pickBadge.textContent = '⭐ Recomendado';
    } else {
      pickBadge.remove();
    }

    const imageWrap = node.querySelector('.deal-image-wrap');
    const primaryDiscount = getPrimaryDiscount(deal);
    if (primaryDiscount >= 25) {
      const topBadge = document.createElement('span');
      topBadge.className = 'badge badge-top-overlay';
      topBadge.textContent = `TOP -${primaryDiscount}%`;
      imageWrap.appendChild(topBadge);
    } else if (isRecentDate(deal.last_checked)) {
      const newBadge = document.createElement('span');
      newBadge.className = 'badge badge-new-overlay';
      newBadge.textContent = 'NUEVO';
      imageWrap.appendChild(newBadge);
    }

    const favBtn = document.createElement('button');
    favBtn.type = 'button';
    favBtn.className = `favorite-btn${isFavorite(deal) ? ' is-favorite' : ''}`;
    favBtn.setAttribute('aria-label', isFavorite(deal) ? 'Quitar de favoritos' : 'Añadir a favoritos');
    favBtn.title = isFavorite(deal) ? 'Quitar de favoritos' : 'Añadir a favoritos';
    favBtn.textContent = isFavorite(deal) ? '❤' : '♡';
    favBtn.addEventListener('click', () => toggleFavorite(deal));
    imageWrap.appendChild(favBtn);

    node.querySelector('.deal-title').textContent = deal.title;
    node.querySelector('.deal-meta').textContent = `${deal.category || 'Sin categoría'} · Precio revisado ${formatCheckedDate(deal.last_checked)} · Fuente ${deal.source || 'manual'}`;
    node.querySelector('.price-current').textContent = formatPrice(deal.price);
    node.querySelector('.price-old').textContent = deal.old_price ? formatPrice(deal.old_price) : '';
    node.querySelector('.price-discount').textContent = primaryDiscount ? `-${primaryDiscount}%` : '';
    node.querySelector('.deal-reason').textContent = deal.reason || 'Bajada detectada por comparación histórica.';

    const btn = node.querySelector('.btn');
    btn.href = deal.affiliate_url || deal.url || '#';
    btn.textContent = `🔥 Ver oferta en ${deal.store || 'la tienda'}`;

    els.grid.appendChild(node);
  });
}

async function init() {
  try {
    const response = await fetch('data/generated_deals.json', { cache: 'no-store' });
    const deals = await response.json();
    state.deals = Array.isArray(deals) ? deals : [];
    populateFilters(state.deals);
    renderStats(state.deals);
    applyFilters();
  } catch (error) {
    els.info.textContent = 'Error cargando las ofertas.';
    console.error(error);
  }
}

[els.search, els.category, els.store, els.discount, els.sort].forEach(el => {
  el.addEventListener('input', applyFilters);
  el.addEventListener('change', applyFilters);
});

init();
