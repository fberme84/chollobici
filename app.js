const state = {
  deals: [],
  filtered: [],
  favorites: JSON.parse(localStorage.getItem('favorites') || '[]'),
  onlyFavorites: false
};

const els = {
  grid: document.getElementById('dealsGrid'),
  info: document.getElementById('dealsInfo'),
  topPicks: document.getElementById('topPicksGrid'),
  topPicksSection: document.getElementById('topPicksSection'),
  favoritesToggle: document.getElementById('favoritesToggle'),
  search: document.getElementById('searchInput'),
  category: document.getElementById('categoryFilter'),
  categoryChips: document.getElementById('categoryChips'),
  store: document.getElementById('storeFilter'),
  discount: document.getElementById('discountFilter'),
  sort: document.getElementById('sortFilter'),
  template: document.getElementById('dealCardTemplate'),
  lastUpdate: document.getElementById('lastUpdate')
};

function hasValidPrice(value) {
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

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

function createOption(value, label = value) {
  const opt = document.createElement('option');
  opt.value = value;
  opt.textContent = label;
  return opt;
}

function placeholderImage(title, store) {
  const safeTitle = (title || 'Oferta').replace(/[&<>"]/g, '');
  const safeStore = (store || 'Tienda').replace(/[&<>"]/g, '');
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="640" height="420" viewBox="0 0 640 420">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#f8fbff" />
          <stop offset="100%" stop-color="#dbeafe" />
        </linearGradient>
      </defs>
      <rect width="640" height="420" fill="url(#bg)" />
      <rect x="26" y="24" width="130" height="36" rx="18" fill="#0f172a" />
      <text x="91" y="47" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#ffffff">${safeStore}</text>
      <g opacity="0.16">
        <circle cx="198" cy="268" r="70" fill="none" stroke="#1d4ed8" stroke-width="14" />
        <circle cx="436" cy="268" r="70" fill="none" stroke="#1d4ed8" stroke-width="14" />
        <path d="M198 268 L292 182 L380 182 L436 268" fill="none" stroke="#1d4ed8" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" />
      </g>
      <text x="320" y="182" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="28" font-weight="700" fill="#0f172a">Imagen pendiente</text>
      <text x="320" y="220" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="20" fill="#334155">${safeTitle}</text>
    </svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function getStoreLabel(deal) {
  return deal.store || (deal.source === 'aliexpress' ? 'AliExpress' : 'Tienda');
}

function getStoreButtonText(deal) {
  const store = getStoreLabel(deal);
  return `Ver en ${store}`;
}

function truncateText(text, maxLength = 74) {
  if (!text) return '';
  const clean = String(text).trim();
  return clean.length > maxLength ? `${clean.slice(0, maxLength).trim()}...` : clean;
}

function buildCategoryChips(categories) {
  if (!els.categoryChips) return;
  els.categoryChips.innerHTML = '';

  const allChip = document.createElement('button');
  allChip.type = 'button';
  allChip.className = `filter-chip${!els.category.value ? ' is-active' : ''}`;
  allChip.dataset.value = '';
  allChip.textContent = 'Todas';
  els.categoryChips.appendChild(allChip);

  categories.forEach(category => {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = `filter-chip${els.category.value === category ? ' is-active' : ''}`;
    chip.dataset.value = category;
    chip.textContent = category;
    els.categoryChips.appendChild(chip);
  });
}

function populateFilters(deals) {
  const categories = [...new Set(deals.map(d => d.category).filter(Boolean))].sort();
  const stores = [...new Set(deals.map(d => getStoreLabel(d)).filter(Boolean))].sort();

  els.category.innerHTML = '<option value="">Todas</option>';
  els.store.innerHTML = '<option value="">Todas</option>';

  categories.forEach(c => els.category.appendChild(createOption(c)));
  stores.forEach(s => els.store.appendChild(createOption(s)));
  buildCategoryChips(categories);
}

function renderStats(deals) {
  const latest = deals.length ? deals.map(d => d.last_checked).filter(Boolean).sort().reverse()[0] : null;
  const lastUpdateText = latest ? `Última actualización: ${formatCheckedDate(latest)}` : 'Última actualización: sin fecha';
  if (els.lastUpdate) els.lastUpdate.textContent = lastUpdateText;
}

function sortDeals(deals) {
  const mode = els.sort.value;
  return [...deals].sort((a, b) => {
    const aDiscount = getPrimaryDiscount(a);
    const bDiscount = getPrimaryDiscount(b);
    if (mode === 'discount') return bDiscount - aDiscount;
    if (mode === 'sales') return (b.sales || 0) - (a.sales || 0);
    if (mode === 'price_asc') return (a.price || Number.MAX_SAFE_INTEGER) - (b.price || Number.MAX_SAFE_INTEGER);
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
    const storeLabel = getStoreLabel(deal);
    const text = [deal.title, deal.category, storeLabel].join(' ').toLowerCase();
    const matchesBase = (!search || text.includes(search))
      && (!category || deal.category === category)
      && (!store || storeLabel === store)
      && (getPrimaryDiscount(deal) >= minDiscount);

    return matchesBase && (!state.onlyFavorites || isFavorite(deal));
  });

  state.filtered = sortDeals(filtered);
  renderDeals();
}

function renderTopPicks() {
  if (!els.topPicks || !els.topPicksSection) return;

  const picks = [...state.deals]
    .sort((a, b) => {
      const scoreA = (a.recomendacion || 0) + getPrimaryDiscount(a);
      const scoreB = (b.recomendacion || 0) + getPrimaryDiscount(b);
      return scoreB - scoreA;
    })
    .slice(0, 3);

  els.topPicks.innerHTML = '';
  if (!picks.length) {
    els.topPicksSection.style.display = 'none';
    return;
  }

  els.topPicksSection.style.display = '';
  picks.forEach((deal, idx) => {
    const item = document.createElement('article');
    item.className = 'top-pick-card';
    const discount = getPrimaryDiscount(deal);
    const salesText = deal.sales ? `${Number(deal.sales).toLocaleString('es-ES')} ventas` : 'Selección destacada';
    const imageSrc = deal.image || placeholderImage(deal.title, getStoreLabel(deal));
    const titleText = truncateText(deal.title, 76);
    const currentPrice = hasValidPrice(deal.price) ? formatPrice(deal.price) : 'Ver en tienda';
    const oldPrice = hasValidPrice(deal.old_price) ? `<span class="top-pick-old-price">${formatPrice(deal.old_price)}</span>` : '';
    const badgeText = discount ? `-${discount}%` : 'Nuevo';

    item.innerHTML = `
      <div class="top-pick-media">
        <span class="top-pick-rank">🔥 TOP ${idx + 1}</span>
        <span class="top-pick-discount">${badgeText}</span>
        <img src="${imageSrc}" alt="${titleText}" class="top-pick-image" loading="lazy">
      </div>
      <div class="top-pick-content">
        <p class="top-pick-meta">${deal.category || 'Sin categoría'} · ${getStoreLabel(deal)}</p>
        <h3 title="${deal.title.replace(/"/g, '&quot;')}">${titleText}</h3>
        <div class="top-pick-price-row">
          <strong>${currentPrice}</strong>
          ${oldPrice}
        </div>
        <p class="top-pick-submeta">${salesText}</p>
        <a class="top-pick-link" href="${deal.affiliate_url || deal.url || '#'}" target="_blank" rel="noopener sponsored nofollow">${getStoreButtonText(deal)}</a>
      </div>
    `;

    const img = item.querySelector('.top-pick-image');
    if (img) {
      img.onerror = () => { img.src = placeholderImage(deal.title, getStoreLabel(deal)); };
    }

    els.topPicks.appendChild(item);
  });
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
    const imageWrap = node.querySelector('.deal-image-wrap');
    const imageBadges = node.querySelector('.image-badges');
    const favoriteBtn = node.querySelector('.favorite-btn');

    imageEl.src = deal.image || placeholderImage(deal.title, getStoreLabel(deal));
    imageEl.alt = deal.title;
    imageEl.onerror = () => { imageEl.src = placeholderImage(deal.title, getStoreLabel(deal)); };

    node.querySelector('.store-pill').textContent = getStoreLabel(deal);
    node.querySelector('.deal-category').textContent = deal.category || 'Otros';
    node.querySelector('.deal-title').textContent = deal.title;

    const primaryDiscount = getPrimaryDiscount(deal);
    if (primaryDiscount) {
      const discountBadge = document.createElement('span');
      discountBadge.className = 'overlay-badge discount';
      discountBadge.textContent = `-${primaryDiscount}%`;
      imageBadges.appendChild(discountBadge);
    }
    if (deal.editor_pick) {
      const pickBadge = document.createElement('span');
      pickBadge.className = 'overlay-badge pick';
      pickBadge.textContent = '⭐ Recomendado';
      imageBadges.appendChild(pickBadge);
    } else if (isRecentDate(deal.last_checked)) {
      const newBadge = document.createElement('span');
      newBadge.className = 'overlay-badge new';
      newBadge.textContent = 'NUEVO';
      imageBadges.appendChild(newBadge);
    }

    favoriteBtn.classList.toggle('is-favorite', isFavorite(deal));
    favoriteBtn.setAttribute('aria-label', isFavorite(deal) ? 'Quitar de favoritos' : 'Añadir a favoritos');
    favoriteBtn.setAttribute('title', isFavorite(deal) ? 'Quitar de favoritos' : 'Añadir a favoritos');
    favoriteBtn.textContent = isFavorite(deal) ? '❤' : '♡';
    favoriteBtn.addEventListener('click', () => toggleFavorite(deal));

    const currentEl = node.querySelector('.price-current');
    const oldEl = node.querySelector('.price-old');
    if (hasValidPrice(deal.price)) {
      currentEl.textContent = formatPrice(deal.price);
      oldEl.textContent = deal.old_price ? formatPrice(deal.old_price) : '';
    } else {
      currentEl.textContent = 'Ver precio en tienda';
      oldEl.textContent = '';
    }

    node.querySelector('.metric-discount').textContent = primaryDiscount ? `Descuento ${primaryDiscount}%` : 'Oferta activa';
    node.querySelector('.metric-sales').textContent = deal.sales ? `${Number(deal.sales).toLocaleString('es-ES')} ventas` : getStoreLabel(deal);

    const sourceLabel = deal.source || 'manual';
    node.querySelector('.deal-meta').textContent = `Fuente ${sourceLabel} · Revisado ${formatCheckedDate(deal.last_checked)}`;
    node.querySelector('.deal-reason').textContent = deal.reason || 'Bajada detectada por comparación histórica.';

    const btn = node.querySelector('.btn');
    btn.href = deal.affiliate_url || deal.url || '#';
    btn.textContent = getStoreButtonText(deal);

    const note = node.querySelector('.cta-note');
    note.textContent = hasValidPrice(deal.price)
      ? 'Precio visible y enlace directo a la tienda.'
      : 'Enlace listo para consultar el precio actual.';

    imageWrap.dataset.category = deal.category || 'Otros';
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
    renderTopPicks();
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

if (els.categoryChips) {
  els.categoryChips.addEventListener('click', event => {
    const chip = event.target.closest('.filter-chip');
    if (!chip) return;
    els.category.value = chip.dataset.value || '';
    [...els.categoryChips.querySelectorAll('.filter-chip')].forEach(node => node.classList.remove('is-active'));
    chip.classList.add('is-active');
    applyFilters();
  });
}

if (els.favoritesToggle) {
  els.favoritesToggle.addEventListener('click', () => {
    state.onlyFavorites = !state.onlyFavorites;
    els.favoritesToggle.classList.toggle('is-active', state.onlyFavorites);
    els.favoritesToggle.setAttribute('aria-pressed', String(state.onlyFavorites));
    els.favoritesToggle.textContent = state.onlyFavorites ? '❤ Solo favoritos' : '♡ Solo favoritos';
    applyFilters();
  });
}

init();
