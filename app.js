
const BASE_PATH = '';
const state = {
  deals: [],
  enrichedDeals: [],
  filtered: [],
  seoPages: [],
  favorites: JSON.parse(localStorage.getItem('favorites') || '[]'),
  onlyFavorites: false,
  route: { type: 'home' }
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
  lastUpdate: document.getElementById('lastUpdate'),
  breadcrumbs: document.getElementById('breadcrumbs'),
  pageIntro: document.getElementById('pageIntro'),
  pageIntroKicker: document.getElementById('pageIntroKicker'),
  pageIntroTitle: document.getElementById('pageIntroTitle'),
  pageIntroText: document.getElementById('pageIntroText'),
  productView: document.getElementById('productView'),
  toolbarRow: document.getElementById('toolbarRow'),
  filters: document.getElementById('filtersSection'),
  listHead: document.getElementById('listSectionHead'),
  seoGuidesSection: document.getElementById('seoGuidesSection'),
  seoGuidesGrid: document.getElementById('seoGuidesGrid'),
  seoGuidesBody: document.getElementById('seoGuidesBody'),
  toggleGuidesBtn: document.getElementById('toggleGuidesBtn'),
  filtersBody: document.getElementById('filtersBody'),
  toggleFiltersBtn: document.getElementById('toggleFiltersBtn'),
  seoClosing: document.getElementById('seoClosingSection'),
  cookieBanner: document.getElementById('cookieBanner'),
  acceptCookiesBtn: document.getElementById('acceptCookiesBtn'),
  cookieMoreInfo: document.getElementById('cookieMoreInfo'),
  openCookiesPolicy: document.getElementById('openCookiesPolicy'),
  cookiesModal: document.getElementById('cookiesModal'),
  closeCookiesModal: document.getElementById('closeCookiesModal'),
  currentYear: document.getElementById('currentYear')
};

const KNOWN_BRANDS = [
  'x-tiger', 'lamicall', 'esen-sp', 'magene', 'gputek', 'rockbros', 'shimano', 'xoss', 'santic',
  'west biking', 'cofit', 'toopre', 'thinkrider', 'cyclami', 'elite', 'garmin', 'bryton'
];

function slugify(text) {
  return String(text || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/&/g, ' y ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function stripBasePath(pathname) {
  if (BASE_PATH && pathname.startsWith(BASE_PATH)) {
    return pathname.slice(BASE_PATH.length) || '/';
  }
  return pathname || '/';
}

function buildPath(path) {
  return `${BASE_PATH}${path}`;
}

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
  const raw = value.includes('T') ? value : `${value}T00:00:00`;
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('es-ES');
}

function isRecentDate(value, days = 7) {
  if (!value) return false;
  const raw = value.includes('T') ? value : `${value}T00:00:00`;
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return false;
  const diffDays = (Date.now() - date.getTime()) / (1000 * 60 * 60 * 24);
  return diffDays <= days;
}

function truncateText(text, maxLength = 74) {
  if (!text) return '';
  const clean = String(text).trim();
  return clean.length > maxLength ? `${clean.slice(0, maxLength).trim()}...` : clean;
}

function getDealId(deal) {
  return deal.id || deal.asin || deal.url || deal.title;
}

function getStoreLabel(deal) {
  return deal.source_label || deal.store || (deal.source === 'aliexpress' ? 'AliExpress' : 'Tienda');
}

function getStoreButtonText(deal) {
  return `Ver en ${getStoreLabel(deal)}`;
}

function getPrimaryDiscount(deal) {
  return Math.max(deal.discount_pct || 0, deal.drop_vs_previous_pct || 0);
}

function detectBrand(title = '') {
  const value = title.toLowerCase();
  const known = KNOWN_BRANDS.find(brand => value.includes(brand));
  if (known) return known.split(' ').map(part => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
  const firstToken = String(title).trim().split(/\s+/)[0] || 'Ciclismo';
  return firstToken.replace(/[^\w-]/g, '');
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

function enrichDeals(deals) {
  return deals.map((deal, index) => {
    const category = deal.category || 'Otros';
    const brand = deal.brand || detectBrand(deal.title);
    const productSlug = `${slugify(deal.title).slice(0, 42).replace(/-+$/,'')}-${slugify(String(getDealId(deal) || index))}`;
    return {
      ...deal,
      category,
      brand,
      categorySlug: slugify(category),
      brandSlug: slugify(brand),
      productSlug,
      path: `/producto/${productSlug}/`,
      categoryPath: `/ofertas/${slugify(category)}`,
      brandPath: `/marca/${slugify(brand)}`
    };
  });
}

function parseRoute() {
  const path = stripBasePath(window.location.pathname);
  const cleanPath = path.replace(/\/+$/, '') || '/';
  const parts = cleanPath.split('/').filter(Boolean);

  if (!parts.length) return { type: 'home', path: '/' };
  if (parts[0] === 'ofertas' && parts.length === 1) return { type: 'offers', path: '/ofertas' };
  if (parts[0] === 'ofertas' && parts[1]) return { type: 'category', slug: parts[1], path: cleanPath };
  if (parts[0] === 'marca' && parts[1]) return { type: 'brand', slug: parts[1], path: cleanPath };
  if (parts[0] === 'producto' && parts[1]) return { type: 'product', slug: parts[1], path: cleanPath };
  if (parts.length === 1 && getSeoPage(parts[0])) return { type: 'guide', slug: parts[0], path: cleanPath };
  return { type: 'not-found', path: cleanPath };
}


function getSeoPage(slug) {
  return state.seoPages.find(page => page.slug === slug);
}

function renderSeoGuides() {
  if (!els.seoGuidesGrid || !els.seoGuidesSection) return;
  els.seoGuidesGrid.innerHTML = '';
  state.seoPages.forEach(page => {
    const card = document.createElement('article');
    card.className = 'seo-guide-home-card';
    const description = truncateText(page.description || page.closingText || '', 68);
    const badge = escapeHtml(page.category || 'Guía');
    const title = escapeHtml(page.introTitle || page.shortLabel || 'Guía de compra');
    card.innerHTML = `
      <div class="seo-guide-home-top">
        <span class="seo-guide-badge">${badge}</span>
      </div>
      <h3><a href="${buildPath('/' + page.slug)}" data-link="internal">${title}</a></h3>
      <p>${escapeHtml(description)}</p>
      <a href="${buildPath('/' + page.slug)}" data-link="internal" class="seo-guide-cta">Leer guía</a>
    `;
    els.seoGuidesGrid.appendChild(card);
  });
  els.seoGuidesSection.hidden = !state.seoPages.length;
}

function setSeoClosing(title = '', text = '') {
  if (!els.seoClosing) return;
  if (!title || !text) {
    els.seoClosing.hidden = true;
    els.seoClosing.innerHTML = '';
    return;
  }
  els.seoClosing.hidden = false;
  els.seoClosing.innerHTML = `
    <span class="section-kicker">Consejos de compra</span>
    <h2>${title}</h2>
    <p>${text}</p>
  `;
}

function renderGuideArticleLinks(deals) {
  const items = deals.map(deal => {
    const productHref = buildPath(deal.path);
    const shopHref = deal.affiliate_url || deal.url || '#';
    return `
      <li class="guide-link-item">
        <a href="${productHref}" data-link="internal" class="guide-link-main">${deal.title}</a>
        <div class="guide-link-meta">
          <span>${deal.category || 'Categoría'}</span>
          <span>·</span>
          <span>${getStoreLabel(deal)}</span>
          ${deal.price ? `<span>·</span><span>${formatPrice(deal.price)}</span>` : ''}
        </div>
        <div class="guide-link-actions">
          <a href="${productHref}" data-link="internal" class="guide-inline-link">Ver ficha</a>
          <a href="${shopHref}" target="_blank" rel="noopener sponsored nofollow" class="guide-inline-link">Ver en tienda</a>
        </div>
      </li>
    `;
  }).join('');

  return `<ul class="guide-links-list">${items}</ul>`;
}

function renderGuideFeaturedDeals(deals = []) {
  if (!deals.length) return '';
  const items = deals.slice(0, 2).map(deal => {
    const productHref = buildPath(deal.path);
    const shopHref = deal.affiliate_url || deal.url || '#';
    const imageSrc = deal.image || placeholderImage(deal.title, getStoreLabel(deal));
    const shortTitle = escapeHtml((deal.title || '').replace(/^([^,\-–:]+[\-–:])\s*/, '').trim() || deal.title || 'Producto recomendado');
    const priceHtml = hasValidPrice(deal.price) ? `<div class="guide-featured-price">${formatPrice(deal.price)}</div>` : '';
    const reasonHtml = deal.reason ? `<p class="guide-featured-reason">${escapeHtml(deal.reason)}</p>` : '';
    return `
      <article class="guide-featured-card">
        <a href="${productHref}" data-link="internal" class="guide-featured-media">
          <img src="${imageSrc}" alt="${escapeHtml(deal.title)}" loading="lazy">
        </a>
        <div class="guide-featured-content">
          <div class="guide-featured-top">
            <span class="guide-featured-store">${getStoreLabel(deal)}</span>
            ${priceHtml}
          </div>
          <h3><a href="${productHref}" data-link="internal">${shortTitle}</a></h3>
          <p class="guide-featured-meta">${escapeHtml(deal.category || 'Producto recomendado')}</p>
          ${reasonHtml}
          <div class="guide-featured-actions">
            <a href="${productHref}" data-link="internal" class="guide-inline-link">Ver ficha</a>
            <a href="${shopHref}" target="_blank" rel="noopener sponsored nofollow" class="guide-inline-link">Ver en tienda</a>
          </div>
        </div>
      </article>
    `;
  }).join('');

  return `<div class="guide-featured-grid">${items}</div>`;
}


function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function escapeRegex(value) {
  return String(value || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function normalizeWord(value) {
  return String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

function getSingularVariants(value = '') {
  const raw = String(value || '').trim();
  if (!raw) return [];
  const variants = new Set([raw]);
  const lower = raw.toLowerCase();
  if (lower.endsWith('es') && raw.length > 4) variants.add(raw.slice(0, -2));
  if (lower.endsWith('s') && raw.length > 3) variants.add(raw.slice(0, -1));
  return [...variants].filter(Boolean);
}

function extractAnchorCandidates(deal) {
  const stopwords = new Set(['para', 'con', 'sin', 'por', 'del', 'las', 'los', 'una', 'unas', 'unos', 'que', 'the', 'and', 'kit', 'set', 'pack', 'bicicleta', 'ciclismo', 'mtb', 'road', 'bike', 'bici', 'de', 'en', 'el', 'la', 'un', 'a']);
  const candidates = new Set();
  getSingularVariants(deal.category || '').forEach(item => candidates.add(item));
  getSingularVariants(deal.brand || '').forEach(item => candidates.add(item));

  String(deal.title || '').split(/[^\p{L}\p{N}]+/u)
    .map(token => token.trim())
    .filter(token => token.length >= 4)
    .forEach(token => {
      if (!stopwords.has(normalizeWord(token))) {
        candidates.add(token);
      }
    });

  return [...candidates]
    .map(item => item.trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
}

function findBestAnchorText(paragraph, deal) {
  const plain = String(paragraph || '');
  const plainNormalized = normalizeWord(plain);
  const candidates = extractAnchorCandidates(deal);

  for (const candidate of candidates) {
    const candidateNormalized = normalizeWord(candidate);
    if (!candidateNormalized || !plainNormalized.includes(candidateNormalized)) continue;
    const regex = new RegExp(`(^|[^\p{L}\p{N}])(${escapeRegex(candidate)})(?=[^\p{L}\p{N}]|$)`, 'iu');
    const match = plain.match(regex);
    if (match && match[2]) return match[2];
  }

  return '';
}

function injectLinkIntoParagraph(paragraph, deal) {
  const linkText = findBestAnchorText(paragraph, deal);
  const safeParagraph = escapeHtml(paragraph);
  if (!linkText) return safeParagraph;

  const safeLinkText = escapeHtml(linkText);
  const linkHtml = `<a href="${buildPath(deal.path)}" data-link="internal" class="guide-inline-link guide-inline-link-embedded" title="${escapeHtml(deal.title)}">${safeLinkText}</a>`;
  const regex = new RegExp(`(^|[^\p{L}\p{N}])(${escapeRegex(safeLinkText)})(?=[^\p{L}\p{N}]|$)`, 'iu');
  if (!regex.test(safeParagraph)) return safeParagraph;
  return safeParagraph.replace(regex, (full, prefix) => `${prefix}${linkHtml}`);
}

function renderGuideParagraphs(paragraphs = [], relatedDeals = []) {
  const deals = [...relatedDeals];
  return paragraphs.map((text, index) => {
    const preferredDeal = deals[index] || deals.find(item => findBestAnchorText(text, item));
    const html = preferredDeal ? injectLinkIntoParagraph(text, preferredDeal) : escapeHtml(text);
    return `<p>${html}</p>`;
  }).join('');
}

function renderGuideFaq(faq = []) {
  if (!faq.length) return '';
  const items = faq.map(([q, a]) => `
    <details class="guide-faq-item">
      <summary>${q}</summary>
      <p>${a}</p>
    </details>
  `).join('');
  return `
    <div class="guide-faq-block">
      <h3>Preguntas frecuentes</h3>
      ${items}
    </div>
  `;
}

function renderRelatedGuides(currentSlug) {
  const guides = state.seoPages.filter(page => page.slug !== currentSlug).slice(0, 4);
  if (!guides.length) return '';
  const items = guides.map(page => `<li><a href="${buildPath('/' + page.slug)}" data-link="internal">${page.introTitle}</a></li>`).join('');
  return `
    <div class="guide-related-block">
      <h3>Otras guías que te pueden interesar</h3>
      <ul>${items}</ul>
    </div>
  `;
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

function createOption(value, label = value) {
  const opt = document.createElement('option');
  opt.value = value;
  opt.textContent = label;
  return opt;
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
  const latest = deals.length ? deals.map(d => d.last_checked || d.updated_at).filter(Boolean).sort().reverse()[0] : null;
  const lastUpdateText = latest ? `Última actualización: ${formatCheckedDate(latest)}` : 'Última actualización: sin fecha';
  if (els.lastUpdate) els.lastUpdate.textContent = lastUpdateText;
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
  renderCurrentRoute();
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

function applyFilters(baseDeals = state.enrichedDeals) {
  const search = els.search.value.trim().toLowerCase();
  const category = els.category.value;
  const store = els.store.value;
  const minDiscount = Number(els.discount.value || 0);

  const filtered = baseDeals.filter(deal => {
    const storeLabel = getStoreLabel(deal);
    const text = [deal.title, deal.category, deal.brand, storeLabel].join(' ').toLowerCase();
    const matchesBase = (!search || text.includes(search))
      && (!category || deal.category === category)
      && (!store || storeLabel === store)
      && (getPrimaryDiscount(deal) >= minDiscount);

    return matchesBase && (!state.onlyFavorites || isFavorite(deal));
  });

  state.filtered = sortDeals(filtered);
  return state.filtered;
}

function linkTo(path, text, className = '', title = '') {
  const safeText = text || '';
  const safeTitle = title ? ` title="${title.replace(/"/g, '&quot;')}"` : '';
  return `<a href="${buildPath(path)}" data-link="internal"${className ? ` class="${className}"` : ''}${safeTitle}>${safeText}</a>`;
}

function buildBreadcrumbs(items) {
  if (!els.breadcrumbs) return;
  els.breadcrumbs.innerHTML = '';
  if (!items || items.length <= 1) {
    els.breadcrumbs.hidden = true;
    return;
  }

  els.breadcrumbs.hidden = false;
  items.forEach((item, index) => {
    if (index > 0) {
      const sep = document.createElement('span');
      sep.className = 'breadcrumb-sep';
      sep.textContent = '›';
      els.breadcrumbs.appendChild(sep);
    }
    if (item.path && index < items.length - 1) {
      const a = document.createElement('a');
      a.href = buildPath(item.path);
      a.dataset.link = 'internal';
      a.textContent = item.label;
      els.breadcrumbs.appendChild(a);
    } else {
      const span = document.createElement('span');
      span.className = 'breadcrumb-current';
      span.textContent = item.label;
      els.breadcrumbs.appendChild(span);
    }
  });
}

function updatePageIntro({ kicker = '', title = '', text = '' } = {}) {
  if (!els.pageIntro) return;
  if (!title) {
    els.pageIntro.hidden = true;
    return;
  }
  els.pageIntro.hidden = false;
  els.pageIntroKicker.textContent = kicker;
  els.pageIntroTitle.textContent = title;
  els.pageIntroText.textContent = text;
}

function setLayoutMode(mode) {
  const isProduct = mode === 'product';
  const isGuide = mode === 'guide';
  const isDetail = isProduct || isGuide;
  els.productView.hidden = !isDetail;

  els.toolbarRow.hidden = isDetail;
  els.filters.hidden = isDetail;
  els.topPicksSection.hidden = isDetail;
  els.listHead.hidden = isDetail;
  els.grid.hidden = isDetail;

  if (els.seoGuidesSection) {
    els.seoGuidesSection.hidden = isDetail;
  }
  if (els.pageIntro) {
    els.pageIntro.hidden = isDetail;
  }

  if (!isDetail) {
    els.productView.innerHTML = '';
  }
}


function setCollapseState(kind, expanded, persist = true) {
  const isGuides = kind === 'guides';
  const section = isGuides ? els.seoGuidesSection : els.filters;
  const body = isGuides ? els.seoGuidesBody : els.filtersBody;
  const btn = isGuides ? els.toggleGuidesBtn : els.toggleFiltersBtn;
  if (!section || !body || !btn) return;

  section.classList.toggle('is-collapsed', !expanded);
  body.hidden = !expanded;
  btn.setAttribute('aria-expanded', String(expanded));
  btn.textContent = expanded ? '− Ocultar' : '+ Mostrar';

  if (persist) {
    try {
      localStorage.setItem(`collapse:${kind}`, expanded ? '1' : '0');
    } catch (error) {}
  }
}

function setupCollapsibles() {
  const mobileDefaultCollapsed = window.matchMedia('(max-width: 768px)').matches;

  const savedGuides = (() => {
    try { return localStorage.getItem('collapse:guides'); } catch (error) { return null; }
  })();
  const savedFilters = (() => {
    try { return localStorage.getItem('collapse:filters'); } catch (error) { return null; }
  })();

  setCollapseState('guides', savedGuides === null ? !mobileDefaultCollapsed : savedGuides === '1', false);
  setCollapseState('filters', savedFilters === null ? !mobileDefaultCollapsed : savedFilters === '1', false);

  if (els.toggleGuidesBtn && !els.toggleGuidesBtn.dataset.bound) {
    els.toggleGuidesBtn.dataset.bound = '1';
    els.toggleGuidesBtn.addEventListener('click', () => {
      const expanded = els.toggleGuidesBtn.getAttribute('aria-expanded') === 'true';
      setCollapseState('guides', !expanded, true);
    });
  }

  if (els.toggleFiltersBtn && !els.toggleFiltersBtn.dataset.bound) {
    els.toggleFiltersBtn.dataset.bound = '1';
    els.toggleFiltersBtn.addEventListener('click', () => {
      const expanded = els.toggleFiltersBtn.getAttribute('aria-expanded') === 'true';
      setCollapseState('filters', !expanded, true);
    });
  }
}

function clearGrid() {
  els.grid.innerHTML = '';
}

function renderTopPicks(deals = state.enrichedDeals) {
  if (!els.topPicks || !els.topPicksSection) return;

  const picks = [...deals]
    .sort((a, b) => {
      const scoreA = (a.recomendacion || 0) + getPrimaryDiscount(a);
      const scoreB = (b.recomendacion || 0) + getPrimaryDiscount(b);
      return scoreB - scoreA;
    })
    .slice(0, 3);

  els.topPicks.innerHTML = '';
  if (!picks.length) {
    els.topPicksSection.hidden = true;
    return;
  }

  if (!els.toolbarRow.hidden) {
    els.topPicksSection.hidden = false;
  }

  picks.forEach((deal, idx) => {
    const item = document.createElement('article');
    item.className = 'top-pick-card card';
    const discount = getPrimaryDiscount(deal);
    const salesText = deal.sales ? `${Number(deal.sales).toLocaleString('es-ES')} ventas` : `${deal.brand} · ${getStoreLabel(deal)}`;
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
        <p class="top-pick-meta">${linkTo(deal.categoryPath, deal.category, 'inline-link')} · ${linkTo(deal.brandPath, deal.brand, 'inline-link')}</p>
        <h3>${linkTo(deal.path, titleText, 'top-pick-title-link', deal.title)}</h3>
        <div class="top-pick-price-row">
          <strong>${currentPrice}</strong>
          ${oldPrice}
        </div>
        <p class="top-pick-submeta">${salesText}</p>
        <div class="top-pick-actions">
          <a class="btn btn-light" href="${buildPath(deal.path)}" data-link="internal">Ver ficha</a>
          <a class="top-pick-link" href="${deal.affiliate_url || deal.url || '#'}" target="_blank" rel="noopener sponsored nofollow">${getStoreButtonText(deal)}</a>
        </div>
      </div>
    `;

    const img = item.querySelector('.top-pick-image');
    if (img) img.onerror = () => { img.src = placeholderImage(deal.title, getStoreLabel(deal)); };

    const productHref = buildPath(deal.path);
    item.dataset.href = productHref;
    item.setAttribute('role', 'link');
    item.setAttribute('tabindex', '0');
    item.setAttribute('aria-label', `Abrir ficha de ${deal.title}`);
    item.addEventListener('click', (event) => {
      if (event.target.closest('a, button')) return;
      window.location.href = productHref;
    });
    item.addEventListener('keydown', (event) => {
      if (event.target.closest('a, button')) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        window.location.href = productHref;
      }
    });

    els.topPicks.appendChild(item);
  });
}

function renderDealCards(deals) {
  clearGrid();
  els.info.textContent = `${deals.length} resultado(s) mostrado(s)`;

  if (!deals.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-state card';
    empty.textContent = 'No hay ofertas que cumplan los filtros actuales.';
    els.grid.appendChild(empty);
    return;
  }

  deals.forEach(deal => {
    const node = els.template.content.firstElementChild.cloneNode(true);
    const imageEl = node.querySelector('.deal-image');
    const imageWrap = node.querySelector('.deal-image-wrap');
    const imageBadges = node.querySelector('.image-badges');
    const favoriteBtn = node.querySelector('.favorite-btn');
    const titleEl = node.querySelector('.deal-title');
    const categoryEl = node.querySelector('.deal-category');

    imageEl.src = deal.image || placeholderImage(deal.title, getStoreLabel(deal));
    imageEl.alt = deal.title;
    imageEl.onerror = () => { imageEl.src = placeholderImage(deal.title, getStoreLabel(deal)); };

    node.querySelector('.store-pill').textContent = getStoreLabel(deal);
    categoryEl.innerHTML = `${linkTo(deal.categoryPath, deal.category, 'inline-link')} · ${linkTo(deal.brandPath, deal.brand, 'inline-link')}`;
    titleEl.innerHTML = linkTo(deal.path, deal.title, 'deal-title-link', deal.title);

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
    } else if (isRecentDate(deal.last_checked || deal.updated_at)) {
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
      oldEl.textContent = hasValidPrice(deal.old_price) ? formatPrice(deal.old_price) : '';
    } else {
      currentEl.textContent = 'Ver precio en tienda';
      oldEl.textContent = '';
    }

    node.querySelector('.metric-discount').textContent = primaryDiscount ? `Descuento ${primaryDiscount}%` : 'Oferta activa';
    node.querySelector('.metric-sales').textContent = deal.sales ? `${Number(deal.sales).toLocaleString('es-ES')} ventas` : `${deal.brand} · ${getStoreLabel(deal)}`;

    const btn = node.querySelector('.btn');
    btn.href = deal.affiliate_url || deal.url || '#';
    btn.textContent = getStoreButtonText(deal);

    const more = document.createElement('a');
    more.className = 'btn btn-light';
    more.href = buildPath(deal.path);
    more.dataset.link = 'internal';
    more.textContent = 'Ver ficha';
    node.querySelector('.deal-actions').prepend(more);

    imageWrap.dataset.category = deal.category || 'Otros';

    const productHref = buildPath(deal.path);
    node.dataset.href = productHref;
    node.setAttribute('role', 'link');
    node.setAttribute('tabindex', '0');
    node.setAttribute('aria-label', `Abrir ficha de ${deal.title}`);

    node.addEventListener('click', (event) => {
      if (event.target.closest('.favorite-btn')) return;
      const externalLink = event.target.closest('a:not([data-link="internal"])');
      if (externalLink) return;
      window.location.href = productHref;
    });

    node.addEventListener('keydown', (event) => {
      if (event.target.closest('a, button')) return;
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        window.location.href = productHref;
      }
    });

    els.grid.appendChild(node);
  });
}

function updateSEO({ title, description, path, schema, robots = 'index,follow,max-image-preview:large' }) {
  document.title = title;

  let robotsTag = document.querySelector('meta[name="robots"]');
  if (!robotsTag) {
    robotsTag = document.createElement('meta');
    robotsTag.name = 'robots';
    document.head.appendChild(robotsTag);
  }
  robotsTag.content = robots;

  let metaDesc = document.querySelector('meta[name="description"]');
  if (!metaDesc) {
    metaDesc = document.createElement('meta');
    metaDesc.name = 'description';
    document.head.appendChild(metaDesc);
  }
  metaDesc.content = description;

  let canonical = document.querySelector('link[rel="canonical"]');
  if (!canonical) {
    canonical = document.createElement('link');
    canonical.rel = 'canonical';
    document.head.appendChild(canonical);
  }
  canonical.href = `${window.location.origin}${buildPath(path)}`;

  const og = [
    ['og:title', title],
    ['og:description', description],
    ['og:type', 'website'],
    ['og:url', `${window.location.origin}${buildPath(path)}`]
  ];
  og.forEach(([property, content]) => {
    let tag = document.querySelector(`meta[property="${property}"]`);
    if (!tag) {
      tag = document.createElement('meta');
      tag.setAttribute('property', property);
      document.head.appendChild(tag);
    }
    tag.setAttribute('content', content);
  });

  let twitter = document.querySelector('meta[name="twitter:card"]');
  if (!twitter) {
    twitter = document.createElement('meta');
    twitter.name = 'twitter:card';
    document.head.appendChild(twitter);
  }
  twitter.content = 'summary_large_image';

  let schemaTag = document.getElementById('schema-jsonld');
  if (!schemaTag) {
    schemaTag = document.createElement('script');
    schemaTag.type = 'application/ld+json';
    schemaTag.id = 'schema-jsonld';
    document.head.appendChild(schemaTag);
  }
  schemaTag.textContent = JSON.stringify(schema);
}

function buildBreadcrumbSchema(items) {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.label,
      item: `${window.location.origin}${buildPath(item.path || state.route.path)}`
    }))
  };
}

function buildCollectionSchema(title, description, deals, path) {
  return {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: title,
    description,
    url: `${window.location.origin}${buildPath(path)}`,
    mainEntity: {
      '@type': 'ItemList',
      itemListElement: deals.slice(0, 10).map((deal, index) => ({
        '@type': 'ListItem',
        position: index + 1,
        url: `${window.location.origin}${buildPath(deal.path)}`,
        name: deal.title
      }))
    }
  };
}

function buildWebsiteSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'CholloBici',
    url: `${window.location.origin}${buildPath('/')}`,
    potentialAction: {
      '@type': 'SearchAction',
      target: `${window.location.origin}${buildPath('/ofertas')}?q={search_term_string}`,
      'query-input': 'required name=search_term_string'
    }
  };
}

function getSchemaSafeName(text, maxLength = 150) {
  const clean = String(text || '').replace(/\s+/g, ' ').trim();
  if (!clean) return 'Producto ciclista';
  return clean.length > maxLength
    ? `${clean.slice(0, maxLength - 1).trim()}…`
    : clean;
}

function buildProductSchema(deal) {
  const ratingValue = Number(deal.rating || 0);
  const salesValue = Number(deal.sales || 0);

  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: getSchemaSafeName(deal.title),
    brand: {
      '@type': 'Brand',
      name: deal.brand || 'CholloBici'
    },
    category: deal.category,
    image: deal.image ? [deal.image] : undefined,
    review: ratingValue ? [{
      '@type': 'Review',
      reviewRating: {
        '@type': 'Rating',
        ratingValue: ratingValue,
        bestRating: 100,
        worstRating: 0
      },
      author: {
        '@type': 'Organization',
        name: getStoreLabel(deal)
      },
      reviewBody: `Valoración visible del producto en ${getStoreLabel(deal)}.`
    }] : undefined,
    aggregateRating: ratingValue ? {
      '@type': 'AggregateRating',
      ratingValue: ratingValue,
      reviewCount: salesValue || 1,
      ratingCount: salesValue || 1,
      bestRating: 100,
      worstRating: 0
    } : undefined,
    offers: {
      '@type': 'Offer',
      priceCurrency: 'EUR',
      price: hasValidPrice(deal.price) ? deal.price : undefined,
      availability: 'https://schema.org/InStock',
      url: deal.affiliate_url || deal.url || `${window.location.origin}${buildPath(deal.path)}`,
      shippingDetails: {
        '@type': 'OfferShippingDetails',
        shippingRate: {
          '@type': 'MonetaryAmount',
          value: 0,
          currency: 'EUR'
        },
        shippingDestination: {
          '@type': 'DefinedRegion',
          addressCountry: 'ES'
        },
        deliveryTime: {
          '@type': 'ShippingDeliveryTime',
          handlingTime: {
            '@type': 'QuantitativeValue',
            minValue: 0,
            maxValue: 1,
            unitCode: 'DAY'
          },
          transitTime: {
            '@type': 'QuantitativeValue',
            minValue: 2,
            maxValue: 5,
            unitCode: 'DAY'
          }
        }
      },
      hasMerchantReturnPolicy: {
        '@type': 'MerchantReturnPolicy',
        applicableCountry: 'ES',
        returnPolicyCategory: 'https://schema.org/MerchantReturnFiniteReturnWindow',
        merchantReturnDays: 14,
        returnFees: 'https://schema.org/FreeReturn',
        returnMethod: 'https://schema.org/ReturnByMail'
      }
    }
  };
}

function renderProductView(deal) {
  const related = sortDeals(state.enrichedDeals.filter(item => item.productSlug !== deal.productSlug && item.categorySlug === deal.categorySlug)).slice(0, 6);
  const discount = getPrimaryDiscount(deal);
  const imageSrc = deal.image || placeholderImage(deal.title, getStoreLabel(deal));
  const oldPrice = hasValidPrice(deal.old_price) ? `<span class="product-old-price">${formatPrice(deal.old_price)}</span>` : '';
  const reasonText = deal.reason ? `<p class="product-reason">${deal.reason}</p>` : '';
  const checkedText = deal.last_checked ? `<span>Revisado: ${formatCheckedDate(deal.last_checked)}</span>` : '';
  const recommendation = deal.recomendacion ? `<span>Recomendación: ${deal.recomendacion}/100</span>` : '';

  els.productView.innerHTML = `
    <article class="product-shell card">
      <div class="product-media">
        <img src="${imageSrc}" alt="${deal.title}" class="product-image" loading="eager">
      </div>
      <div class="product-content">
        <div class="product-meta">
          ${linkTo(deal.categoryPath, deal.category, 'inline-link')}
          <span>·</span>
          ${linkTo(deal.brandPath, deal.brand, 'inline-link')}
          <span>·</span>
          <span>${getStoreLabel(deal)}</span>
        </div>
        <h2 class="product-title">${deal.title}</h2>
        <div class="product-price-row">
          <strong>${hasValidPrice(deal.price) ? formatPrice(deal.price) : 'Ver en tienda'}</strong>
          ${oldPrice}
        </div>
        <div class="product-badges">
          ${discount ? `<span class="metric metric-discount">Descuento ${discount}%</span>` : '<span class="metric">Oferta activa</span>'}
          ${recommendation}
          ${checkedText}
        </div>
        ${reasonText}
        <div class="product-actions">
          <a class="btn" href="${deal.affiliate_url || deal.url || '#'}" target="_blank" rel="noopener sponsored nofollow">${getStoreButtonText(deal)}</a>
          <button type="button" class="toggle-btn product-favorite-btn ${isFavorite(deal) ? 'is-active' : ''}" id="productFavoriteBtn">${isFavorite(deal) ? '❤ En favoritos' : '♡ Guardar oferta'}</button>
        </div>
      </div>
    </article>

    <section class="related-section">
      <div class="section-head section-head-list">
        <div>
          <span class="section-kicker">Más ofertas relacionadas</span>
          <h2>Más chollos de ${deal.category}</h2>
        </div>
      </div>
      <div id="relatedGrid" class="deals-grid"></div>
    </section>
  `;

  const img = els.productView.querySelector('.product-image');
  if (img) img.onerror = () => { img.src = placeholderImage(deal.title, getStoreLabel(deal)); };

  const favoriteBtn = document.getElementById('productFavoriteBtn');
  if (favoriteBtn) favoriteBtn.addEventListener('click', () => toggleFavorite(deal));

  const relatedGrid = document.getElementById('relatedGrid');
  if (!related.length) {
    relatedGrid.innerHTML = '<div class="empty-state card">Aún no hay más ofertas relacionadas disponibles.</div>';
  } else {
    related.forEach(item => {
      const node = els.template.content.firstElementChild.cloneNode(true);
      const imageEl = node.querySelector('.deal-image');
      const imageBadges = node.querySelector('.image-badges');
      const favoriteBtnItem = node.querySelector('.favorite-btn');

      imageEl.src = item.image || placeholderImage(item.title, getStoreLabel(item));
      imageEl.alt = item.title;
      imageEl.onerror = () => { imageEl.src = placeholderImage(item.title, getStoreLabel(item)); };

      node.querySelector('.store-pill').textContent = getStoreLabel(item);
      node.querySelector('.deal-category').innerHTML = `${linkTo(item.categoryPath, item.category, 'inline-link')} · ${linkTo(item.brandPath, item.brand, 'inline-link')}`;
      node.querySelector('.deal-title').innerHTML = linkTo(item.path, item.title, 'deal-title-link', item.title);
      node.querySelector('.price-current').textContent = hasValidPrice(item.price) ? formatPrice(item.price) : 'Ver en tienda';
      node.querySelector('.price-old').textContent = hasValidPrice(item.old_price) ? formatPrice(item.old_price) : '';
      node.querySelector('.metric-discount').textContent = getPrimaryDiscount(item) ? `Descuento ${getPrimaryDiscount(item)}%` : 'Oferta activa';
      node.querySelector('.metric-sales').textContent = item.sales ? `${Number(item.sales).toLocaleString('es-ES')} ventas` : `${item.brand} · ${getStoreLabel(item)}`;
      node.querySelector('.btn').href = item.affiliate_url || item.url || '#';
      node.querySelector('.btn').textContent = getStoreButtonText(item);

      const more = document.createElement('a');
      more.className = 'btn btn-light';
      more.href = buildPath(item.path);
      more.dataset.link = 'internal';
      more.textContent = 'Ver ficha';
      node.querySelector('.deal-actions').prepend(more);

      if (getPrimaryDiscount(item)) {
        const discountBadge = document.createElement('span');
        discountBadge.className = 'overlay-badge discount';
        discountBadge.textContent = `-${getPrimaryDiscount(item)}%`;
        imageBadges.appendChild(discountBadge);
      }
      favoriteBtnItem.classList.toggle('is-favorite', isFavorite(item));
      favoriteBtnItem.textContent = isFavorite(item) ? '❤' : '♡';
      favoriteBtnItem.addEventListener('click', () => toggleFavorite(item));
      relatedGrid.appendChild(node);
    });
  }
}


function findDealByProductSlugOrId(slug) {
  const exact = state.enrichedDeals.find(item => item.productSlug === slug);
  if (exact) return exact;
  const slugText = String(slug || '').trim().toLowerCase();
  const idMatch = slugText.match(/([a-z0-9]+)$/);
  const candidateId = idMatch ? idMatch[1] : '';
  if (!candidateId) return null;
  return state.enrichedDeals.find(item => String(getDealId(item)).toLowerCase() === candidateId) || null;
}

function renderHomePage() {
  setSeoClosing();
  setLayoutMode('list');
  updatePageIntro({});
  buildBreadcrumbs([{ label: 'Inicio', path: '/' }]);
  renderTopPicks(state.enrichedDeals);
  const filtered = applyFilters(state.enrichedDeals);
  renderDealCards(filtered);

  updateSEO({
    title: 'Ofertas de ciclismo y accesorios baratos | CholloBici',
    description: 'Encuentra chollos de ciclismo en accesorios, herramientas, ropa y electrónica. Filtra por categoría y descubre ofertas reales actualizadas.',
    path: '/',
    schema: {
      '@context': 'https://schema.org',
      '@graph': [
        buildWebsiteSchema(),
        buildCollectionSchema('Ofertas de ciclismo y accesorios baratos', 'Listado principal de ofertas de ciclismo', filtered, '/')
      ]
    }
  });
}

function renderOffersPage() {
  setSeoClosing();
  setLayoutMode('list');
  updatePageIntro({
    kicker: 'Todas las categorías',
    title: 'Todas las ofertas de ciclismo',
    text: 'Explora el listado completo de chollos detectados por CholloBici y filtra por categoría, tienda, precio o descuento.'
  });
  buildBreadcrumbs([{ label: 'Inicio', path: '/' }, { label: 'Ofertas', path: '/ofertas' }]);
  renderTopPicks(state.enrichedDeals);
  const filtered = applyFilters(state.enrichedDeals);
  renderDealCards(filtered);

  updateSEO({
    title: 'Todas las ofertas de ciclismo | CholloBici',
    description: 'Listado completo de ofertas de ciclismo para ahorrar en accesorios, ropa, herramientas y electrónica.',
    path: '/ofertas',
    schema: buildCollectionSchema('Todas las ofertas de ciclismo', 'Listado completo de ofertas de ciclismo', filtered, '/ofertas')
  });
}

function renderCategoryPage(slug) {
  setSeoClosing();
  setLayoutMode('list');
  const categoryDeals = state.enrichedDeals.filter(deal => deal.categorySlug === slug);
  if (!categoryDeals.length) {
    renderNotFoundPage();
    return;
  }
  const categoryName = categoryDeals[0]?.category || slug.replace(/-/g, ' ');
  els.category.value = categoryName;
  buildCategoryChips([...new Set(state.enrichedDeals.map(d => d.category))].sort());
  updatePageIntro({
    kicker: 'Categoría',
    title: `Ofertas de ${categoryName}`,
    text: `Selección de chollos de ${categoryName.toLowerCase()} con enlaces directos a tienda, descuentos visibles y fichas individuales indexables.`
  });
  buildBreadcrumbs([
    { label: 'Inicio', path: '/' },
    { label: 'Ofertas', path: '/ofertas' },
    { label: categoryName, path: `/ofertas/${slug}` }
  ]);
  renderTopPicks(categoryDeals.length ? categoryDeals : state.enrichedDeals);
  const filtered = applyFilters(categoryDeals);
  renderDealCards(filtered);

  updateSEO({
    title: `Ofertas de ${categoryName} baratas | CholloBici`,
    description: `Encuentra ofertas de ${categoryName.toLowerCase()} y compara productos recomendados con sus descuentos actuales.`,
    path: `/ofertas/${slug}`,
    schema: {
      '@context': 'https://schema.org',
      '@graph': [
        buildBreadcrumbSchema([
          { label: 'Inicio', path: '/' },
          { label: 'Ofertas', path: '/ofertas' },
          { label: categoryName, path: `/ofertas/${slug}` }
        ]),
        buildCollectionSchema(`Ofertas de ${categoryName}`, `Selección de ofertas de ${categoryName}`, filtered, `/ofertas/${slug}`)
      ]
    }
  });
}

function renderBrandPage(slug) {
  setSeoClosing();
  setLayoutMode('list');
  const brandDeals = state.enrichedDeals.filter(deal => deal.brandSlug === slug);
  if (!brandDeals.length) {
    renderNotFoundPage();
    return;
  }
  const brandName = brandDeals[0]?.brand || slug.replace(/-/g, ' ');
  els.category.value = '';
  buildCategoryChips([...new Set(state.enrichedDeals.map(d => d.category))].sort());
  updatePageIntro({
    kicker: 'Marca',
    title: `Ofertas de ${brandName}`,
    text: `Productos de ${brandName} con precio actual, descuento visible y acceso rápido a su ficha individual.`
  });
  buildBreadcrumbs([
    { label: 'Inicio', path: '/' },
    { label: 'Marca', path: `/marca/${slug}` },
    { label: brandName, path: `/marca/${slug}` }
  ]);
  renderTopPicks(brandDeals.length ? brandDeals : state.enrichedDeals);
  const filtered = applyFilters(brandDeals);
  renderDealCards(filtered);

  updateSEO({
    title: `Ofertas ${brandName} | CholloBici`,
    description: `Descubre ofertas de ${brandName} en ciclismo con fichas optimizadas y enlaces directos a tienda.`,
    path: `/marca/${slug}`,
    schema: {
      '@context': 'https://schema.org',
      '@graph': [
        buildBreadcrumbSchema([
          { label: 'Inicio', path: '/' },
          { label: 'Marca', path: `/marca/${slug}` },
          { label: brandName, path: `/marca/${slug}` }
        ]),
        buildCollectionSchema(`Ofertas ${brandName}`, `Selección de ofertas de ${brandName}`, filtered, `/marca/${slug}`)
      ]
    }
  });
}

function renderProductPage(slug) {
  setSeoClosing();
  const deal = findDealByProductSlugOrId(slug);
  if (!deal) {
    renderNotFoundPage();
    return;
  }

  if (deal.productSlug !== slug) {
    window.location.replace(buildPath(deal.path));
    return;
  }

  setLayoutMode('product');
  buildBreadcrumbs([
    { label: 'Inicio', path: '/' },
    { label: 'Ofertas', path: '/ofertas' },
    { label: deal.category, path: deal.categoryPath },
    { label: deal.title, path: deal.path }
  ]);
  updatePageIntro({});
  renderProductView(deal);

  updateSEO({
    title: `${deal.title} al mejor precio | CholloBici`,
    description: `${deal.title}. Precio actual ${hasValidPrice(deal.price) ? formatPrice(deal.price) : 'consultar en tienda'}${getPrimaryDiscount(deal) ? ` con descuento del ${getPrimaryDiscount(deal)}%` : ''}.`,
    path: deal.path,
    schema: {
      '@context': 'https://schema.org',
      '@graph': [
        buildBreadcrumbSchema([
          { label: 'Inicio', path: '/' },
          { label: 'Ofertas', path: '/ofertas' },
          { label: deal.category, path: deal.categoryPath },
          { label: deal.title, path: deal.path }
        ]),
        buildProductSchema(deal)
      ]
    }
  });
}

function renderGuidePage(slug) {
  const page = getSeoPage(slug);
  if (!page) {
    renderNotFoundPage();
    return;
  }

  setSeoClosing();
  setLayoutMode('guide');

  const relatedDeals = state.enrichedDeals
    .filter(deal => (deal.category || '').toLowerCase() === (page.category || '').toLowerCase())
    .sort((a, b) => {
      const scoreA = (a.recomendacion || 0) + (a.discount_pct || 0);
      const scoreB = (b.recomendacion || 0) + (b.discount_pct || 0);
      return scoreB - scoreA;
    })
    .slice(0, 12);

  buildBreadcrumbs([
    { label: 'Inicio', path: '/' },
    { label: page.introTitle, path: '/' + page.slug }
  ]);

  const faqHtml = renderGuideFaq(page.faq || []);
  const relatedGuidesHtml = renderRelatedGuides(page.slug);
  const paragraphs = (page.articleParagraphs && page.articleParagraphs.length ? page.articleParagraphs : [page.introText || page.description || '']).filter(Boolean);
  const paragraphsHtml = renderGuideParagraphs(paragraphs, relatedDeals);
  const featuredDealsHtml = renderGuideFeaturedDeals(relatedDeals.slice(0, 2));
  const relatedDealsHtml = relatedDeals.length ? `
    <div class="guide-article-block guide-related-offers-block">
      <h2>${page.linksTitle || 'Ofertas relacionadas'}</h2>
      <p class="guide-helper-text">${page.linksIntro || 'Hemos reunido aquí las ofertas más relevantes de esta temática para que puedas compararlas rápidamente.'}</p>
      ${renderGuideArticleLinks(relatedDeals)}
    </div>
  ` : '';

  els.productView.innerHTML = `
    <article class="guide-article card">
      <header class="guide-hero-block">
        <span class="section-kicker">${page.kicker || 'Guía de compra'}</span>
        <h1>${page.introTitle || page.shortLabel || 'Guía de compra'}</h1>
        <p class="guide-hero-text">${page.introText || page.description || ''}</p>
      </header>

      ${page.articleLead ? `<div class="guide-article-block guide-lead-block"><p>${page.articleLead}</p></div>` : ''}

      <div class="guide-article-block">
        ${paragraphsHtml}
      </div>

      ${featuredDealsHtml ? `
      <div class="guide-article-block guide-featured-block">
        <h2>Productos destacados de esta guía</h2>
        <p class="guide-helper-text">Una selección rápida con dos opciones especialmente interesantes para empezar a comparar.</p>
        ${featuredDealsHtml}
      </div>` : ''}

      <div class="guide-article-block">
        <h2>${page.closingTitle}</h2>
        <p>${page.closingText}</p>
      </div>

      ${relatedDealsHtml}
      ${faqHtml}
      ${relatedGuidesHtml}
    </article>
  `;

  updateSEO({
    title: page.metaTitle || page.introTitle,
    description: page.description,
    path: '/' + page.slug,
    schema: {
      '@context': 'https://schema.org',
      '@graph': [
        buildBreadcrumbSchema([
          { label: 'Inicio', path: '/' },
          { label: page.introTitle, path: '/' + page.slug }
        ]),
        {
          '@type': 'Article',
          headline: page.introTitle,
          description: page.description,
          url: `${window.location.origin}${buildPath('/' + page.slug)}`
        },
        {
          '@type': 'FAQPage',
          'mainEntity': (page.faq || []).map(item => ({
            '@type': 'Question',
            'name': item[0],
            'acceptedAnswer': {
              '@type': 'Answer',
              'text': item[1]
            }
          }))
        }
      ]
    }
  });
}

function renderNotFoundPage() {
  setSeoClosing();
  setLayoutMode('list');
  updatePageIntro({
    kicker: 'Error 404',
    title: 'Página no encontrada',
    text: 'La ruta que buscas no existe o ya no está disponible. Te mostramos las mejores ofertas activas para que sigas navegando.'
  });
  buildBreadcrumbs([{ label: 'Inicio', path: '/' }, { label: '404', path: state.route.path }]);
  renderTopPicks(state.enrichedDeals);
  const filtered = applyFilters(state.enrichedDeals);
  renderDealCards(filtered);
  updateSEO({
    title: 'Página no encontrada | CholloBici',
    description: 'La página solicitada no existe. Descubre otras ofertas de ciclismo activas en CholloBici.',
    path: state.route.path,
    robots: 'noindex,follow',
    schema: buildCollectionSchema('Página no encontrada', 'Ofertas activas en CholloBici', filtered, '/')
  });
}

function showCookieBannerIfNeeded() {
  if (!els.cookieBanner) return;
  const accepted = localStorage.getItem('cookie_notice_ack') === 'yes';
  els.cookieBanner.hidden = accepted;
}

function openCookiesModal() {
  if (!els.cookiesModal) return;
  els.cookiesModal.hidden = false;
  els.cookiesModal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('has-modal-open');
}

function closeCookiesModal() {
  if (!els.cookiesModal) return;
  els.cookiesModal.hidden = true;
  els.cookiesModal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('has-modal-open');
}

function acceptCookieNotice() {
  localStorage.setItem('cookie_notice_ack', 'yes');
  if (els.cookieBanner) els.cookieBanner.hidden = true;
}

function resetUIControls() {
  if (!state.route || state.route.type === 'home' || state.route.type === 'offers') return;
  if (state.route.type !== 'category') {
    els.category.value = '';
  }
}

function renderCurrentRoute() {
  state.route = parseRoute();
  resetUIControls();

  if (state.route.type === 'home') return renderHomePage();
  if (state.route.type === 'offers') return renderOffersPage();
  if (state.route.type === 'category') return renderCategoryPage(state.route.slug);
  if (state.route.type === 'brand') return renderBrandPage(state.route.slug);
  if (state.route.type === 'product') return renderProductPage(state.route.slug);
  if (state.route.type === 'guide') return renderGuidePage(state.route.slug);
  return renderNotFoundPage();
}

function navigateTo(url) {
  const current = new URL(window.location.href);
  const target = new URL(url, window.location.origin);
  if (target.origin !== current.origin) {
    window.location.href = target.href;
    return;
  }
  window.history.pushState({}, '', target.href);
  renderCurrentRoute();
}

async function init() {
  try {
    const queryValue = new URLSearchParams(window.location.search).get('q');
    if (queryValue) {
      els.search.value = queryValue;
    }
    const [response, seoResponse] = await Promise.all([
      fetch('/data/generated_deals.json', { cache: 'no-store' }),
      fetch('/data/seo_pages.json', { cache: 'no-store' })
    ]);
    const deals = await response.json();
    const seoPages = await seoResponse.json();
    state.deals = Array.isArray(deals) ? deals : [];
    state.seoPages = Array.isArray(seoPages) ? seoPages : [];
    state.enrichedDeals = enrichDeals(state.deals);

    populateFilters(state.enrichedDeals);
    renderStats(state.enrichedDeals);
    renderSeoGuides();
    setupCollapsibles();
    if (els.currentYear) els.currentYear.textContent = new Date().getFullYear();
    showCookieBannerIfNeeded();
    renderCurrentRoute();
  } catch (error) {
    els.info.textContent = 'Error cargando las ofertas.';
    console.error(error);
  }
}

document.addEventListener('click', event => {
  const internalLink = event.target.closest('[data-link="internal"]');
  if (!internalLink) return;
  const href = internalLink.getAttribute('href') || '';
  if (href.includes('/producto/')) {
    event.preventDefault();
    window.location.href = href;
    return;
  }
  event.preventDefault();
  navigateTo(href);
});

window.addEventListener('popstate', renderCurrentRoute);

[els.search, els.category, els.store, els.discount, els.sort].forEach(el => {
  el.addEventListener('input', () => {
    if (state.route.type === 'product') return;
    if (state.route.type === 'category' && els.category.value && slugify(els.category.value) !== state.route.slug) {
      navigateTo(buildPath(`/ofertas/${slugify(els.category.value)}`));
      return;
    }
    renderCurrentRoute();
  });
  el.addEventListener('change', () => {
    if (state.route.type === 'product') return;
    if (state.route.type === 'category' && els.category.value && slugify(els.category.value) !== state.route.slug) {
      navigateTo(buildPath(`/ofertas/${slugify(els.category.value)}`));
      return;
    }
    renderCurrentRoute();
  });
});

if (els.categoryChips) {
  els.categoryChips.addEventListener('click', event => {
    const chip = event.target.closest('.filter-chip');
    if (!chip) return;

    const value = chip.dataset.value || '';
    if (!value) {
      els.category.value = '';
      navigateTo(buildPath('/ofertas'));
      return;
    }

    els.category.value = value;
    navigateTo(buildPath(`/ofertas/${slugify(value)}`));
  });
}

if (els.favoritesToggle) {
  els.favoritesToggle.addEventListener('click', () => {
    state.onlyFavorites = !state.onlyFavorites;
    els.favoritesToggle.classList.toggle('is-active', state.onlyFavorites);
    els.favoritesToggle.setAttribute('aria-pressed', String(state.onlyFavorites));
    els.favoritesToggle.textContent = state.onlyFavorites ? '❤ Solo favoritos' : '♡ Solo favoritos';
    renderCurrentRoute();
  });
}

if (els.acceptCookiesBtn) {
  els.acceptCookiesBtn.addEventListener('click', acceptCookieNotice);
}

if (els.cookieMoreInfo) {
  els.cookieMoreInfo.addEventListener('click', openCookiesModal);
}

if (els.openCookiesPolicy) {
  els.openCookiesPolicy.addEventListener('click', openCookiesModal);
}

if (els.closeCookiesModal) {
  els.closeCookiesModal.addEventListener('click', closeCookiesModal);
}

if (els.cookiesModal) {
  els.cookiesModal.addEventListener('click', event => {
    if (event.target.matches('[data-close-cookies="true"]')) {
      closeCookiesModal();
    }
  });
}

document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && els.cookiesModal && !els.cookiesModal.hidden) {
    closeCookiesModal();
  }
});

init();
