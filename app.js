const state = {
  deals: [],
  filtered: []
};

const els = {
  grid: document.getElementById('dealsGrid'),
  info: document.getElementById('dealsInfo'),
  stats: document.getElementById('stats'),
  search: document.getElementById('searchInput'),
  category: document.getElementById('categoryFilter'),
  store: document.getElementById('storeFilter'),
  discount: document.getElementById('discountFilter'),
  template: document.getElementById('dealCardTemplate')
};

function formatPrice(value) {
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency: 'EUR'
  }).format(value);
}

function createOption(value) {
  const opt = document.createElement('option');
  opt.value = value;
  opt.textContent = value;
  return opt;
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
  const avg = total ? Math.round(deals.reduce((sum, d) => sum + (d.discount_pct || 0), 0) / total) : 0;

  els.stats.innerHTML = `
    <span class="stat-chip">${total} ofertas</span>
    <span class="stat-chip">${hot} destacadas</span>
    <span class="stat-chip">Descuento medio ${avg}%</span>
  `;
}

function applyFilters() {
  const search = els.search.value.trim().toLowerCase();
  const category = els.category.value;
  const store = els.store.value;
  const minDiscount = Number(els.discount.value || 0);

  state.filtered = state.deals.filter(deal => {
    const text = [deal.title, deal.category, deal.store].join(' ').toLowerCase();
    return (!search || text.includes(search))
      && (!category || deal.category === category)
      && (!store || deal.store === store)
      && ((deal.discount_pct || 0) >= minDiscount);
  });

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
    node.querySelector('.deal-image').src = deal.image || 'https://placehold.co/640x400?text=Oferta';
    node.querySelector('.deal-image').alt = deal.title;
    node.querySelector('.badge-store').textContent = deal.store || 'Tienda';
    node.querySelector('.badge-status').textContent = deal.status === 'hot' ? '🔥 Destacada' : 'Oferta';
    node.querySelector('.deal-title').textContent = deal.title;
    node.querySelector('.deal-meta').textContent = `${deal.category || 'Sin categoría'} · Actualizado ${new Date(deal.updated_at).toLocaleDateString('es-ES')}`;
    node.querySelector('.price-current').textContent = formatPrice(deal.price);
    node.querySelector('.price-old').textContent = deal.old_price ? formatPrice(deal.old_price) : '';
    node.querySelector('.price-discount').textContent = deal.discount_pct ? `-${deal.discount_pct}%` : '';
    node.querySelector('.deal-reason').textContent = deal.reason || 'Bajada detectada por comparación histórica.';
    node.querySelector('.btn').href = deal.affiliate_url || deal.url || '#';
    els.grid.appendChild(node);
  });
}

async function init() {
  try {
    const response = await fetch('data/deals.json', { cache: 'no-store' });
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

[els.search, els.category, els.store, els.discount].forEach(el => {
  el.addEventListener('input', applyFilters);
  el.addEventListener('change', applyFilters);
});

init();
