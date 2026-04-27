// ==============================
// CONFIG
// ==============================
const DATA_URL = "/data/generated_deals.json";
const SEO_PAGES_URL = "/data/seo_pages.json";

// ==============================
// STATE
// ==============================
let allDeals = [];
let filteredDeals = [];
let favoritesOnly = false;
let seoPages = [];

// ==============================
// HELPERS
// ==============================
function formatPrice(price) {
  const num = Number(price);
  if (!Number.isFinite(num) || num <= 0) return "";
  return num.toFixed(2).replace(".", ",") + " €";
}

function getDiscountPct(deal) {
  const explicit = Number(deal.discount_pct);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;

  const price = Number(deal.price);
  const oldPrice = Number(deal.old_price);
  if (Number.isFinite(price) && Number.isFinite(oldPrice) && oldPrice > price && oldPrice > 0) {
    return Math.round(((oldPrice - price) / oldPrice) * 100);
  }
  return 0;
}

function getChollometerScore(deal) {
  const score = Number(deal.chollometer_score ?? deal.recomendacion ?? 0);
  if (!Number.isFinite(score)) return 0;
  return Math.max(0, Math.min(100, Math.round(score)));
}

function getChollometerLabel(deal) {
  return safeText(deal.chollometer_label || "Precio interesante");
}

function formatSignedPct(value) {
  const num = Number(value);
  if (!Number.isFinite(num) || num === 0) return "";
  const sign = num > 0 ? "+" : "";
  return `${sign}${num.toFixed(Math.abs(num) >= 10 ? 0 : 1).replace(".", ",")}%`;
}

function formatPriceCompact(price) {
  return formatPrice(price).replace(" €", "€");
}

function getStoreLabel(deal) {
  return deal.source_label || deal.store || deal.source || "Tienda";
}

function getDealUrl(deal) {
  return deal.affiliate_url || deal.url || "#";
}

function getImageUrl(deal) {
  const value = String(deal.image || "").trim();
  if (!value || value.length < 10 || value.includes("</") || !/^https?:\/\//i.test(value)) {
    return "/assets/placeholder-product.svg";
  }
  return value;
}

function safeText(value) {
  return String(value || "");
}

function normalizeText(value) {
  return safeText(value)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function slugify(value) {
  return normalizeText(value)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function getFavoriteKey(deal) {
  return safeText(deal.id || deal.product_id || deal.url || deal.title);
}

function loadFavorites() {
  try {
    return JSON.parse(localStorage.getItem("chollobici_favorites") || "[]");
  } catch {
    return [];
  }
}

function saveFavorites(keys) {
  localStorage.setItem("chollobici_favorites", JSON.stringify(keys));
}

function isFavorite(deal) {
  return loadFavorites().includes(getFavoriteKey(deal));
}

function toggleFavorite(deal) {
  const key = getFavoriteKey(deal);
  const favs = loadFavorites();
  const idx = favs.indexOf(key);
  if (idx >= 0) {
    favs.splice(idx, 1);
  } else {
    favs.push(key);
  }
  saveFavorites(favs);
  applyFiltersAndRender();
}

function inferBucket(deal) {
  const text = normalizeText(`${deal.title || ""} ${deal.brand || ""} ${deal.category_hint || ""}`);

  if (/(bicicleta|e-bike|ebike|gravel bike|mtb|mountain bike|urbana|carretera|gravel)/.test(text)) return "Bicis";
  if (/(casco|helmet)/.test(text)) return "Cascos";
  if (/(maillot|culotte|chaqueta|ropa|guantes|camiseta|malla|jersey|cubrezapatillas|calcetin|calcetines)/.test(text)) return "Ropa";
  if (/(luz|luces|faro|rear light|trasera|delantera)/.test(text)) return "Luces";
  if (/(sillin|manillar|pedal|cadena|freno|rueda|cubierta|camara|potencia|punos|grips|calas)/.test(text)) return "Componentes";
  if (/(herramienta|bomba|inflador|multiherramienta|soporte|portabidon|guardabarros|bolsa|bidon)/.test(text)) return "Accesorios";
  return "Otros";
}

function getStoreClass(deal) {
  const store = normalizeText(getStoreLabel(deal));
  if (store.includes("decathlon")) return "store-pill--decathlon";
  if (store.includes("aliexpress")) return "store-pill--aliexpress";
  if (store.includes("amazon")) return "store-pill--amazon";
  return "store-pill--generic";
}

// ==============================
// GUIDE RENDER
// ==============================
function renderSeoGuides(pages) {
  const grid = document.getElementById("seoGuidesGrid");
  if (!grid) return;

  grid.innerHTML = "";
  pages.forEach((page) => {
    const card = document.createElement("article");
    card.className = "seo-guide-home-card";
    const slug = safeText(page.slug).replace(/^\/+|\/+$/g, "");
    const href = `/${slug}/`;
    card.innerHTML = `
      <div class="seo-guide-home-top">
        <span class="seo-guide-badge">${safeText(page.kicker || "Guía")}</span>
      </div>
      <h3><a href="${href}">${safeText(page.shortLabel || page.introTitle || slug)}</a></h3>
      <p>${safeText(page.description || page.introText || "")}</p>
      <a class="seo-guide-cta" href="${href}">Abrir guía</a>
    `;
    grid.appendChild(card);
  });
}

// ==============================
// TEMPLATE RENDER
// ==============================
function renderDealCard(deal) {
  const template = document.getElementById("dealCardTemplate");
  if (!template) return document.createElement("div");

  const node = template.content.firstElementChild.cloneNode(true);
  const url = getDealUrl(deal);

  const storePill = node.querySelector(".store-pill");
  if (storePill) {
    storePill.textContent = getStoreLabel(deal);
    storePill.classList.add(getStoreClass(deal));
    storePill.dataset.store = getStoreLabel(deal);
  }

  const imageBadges = node.querySelector(".image-badges");
  if (imageBadges) {
    imageBadges.innerHTML = "";
    const discount = getDiscountPct(deal);
    if (discount > 0) {
      const badge = document.createElement("span");
      badge.className = "overlay-badge discount";
      badge.textContent = `-${discount}%`;
      imageBadges.appendChild(badge);
    }

    const score = getChollometerScore(deal);
    if (score >= 70) {
      const badge = document.createElement("span");
      badge.className = "overlay-badge chollometer";
      badge.textContent = `🔥 ${score}`;
      badge.title = getChollometerLabel(deal);
      imageBadges.appendChild(badge);
    } else if (deal.is_price_drop) {
      const badge = document.createElement("span");
      badge.className = "overlay-badge price-drop";
      badge.textContent = "📉 Baja";
      imageBadges.appendChild(badge);
    } else if (deal.is_recent_min_price) {
      const badge = document.createElement("span");
      badge.className = "overlay-badge min-price";
      badge.textContent = "🏷️ Mín. 30d";
      imageBadges.appendChild(badge);
    }
  }

  const image = node.querySelector(".deal-image");
  if (image) {
    image.src = getImageUrl(deal);
    image.alt = safeText(deal.title);
    image.onerror = () => {
      image.onerror = null;
      image.src = "/assets/placeholder-product.svg";
    };
  }

  const category = node.querySelector(".deal-category");
  if (category) category.textContent = inferBucket(deal);

  const title = node.querySelector(".deal-title");
  if (title) title.textContent = safeText(deal.title);

  const priceCurrent = node.querySelector(".price-current");
  if (priceCurrent) priceCurrent.textContent = formatPrice(deal.price);

  const priceOld = node.querySelector(".price-old");
  if (priceOld) {
    const oldPrice = formatPrice(deal.old_price);
    if (oldPrice && oldPrice !== formatPrice(deal.price)) {
      priceOld.textContent = oldPrice;
      priceOld.hidden = false;
      priceOld.style.display = "";
    } else {
      priceOld.textContent = "";
      priceOld.hidden = true;
      priceOld.style.display = "none";
    }
  }

  const metricDiscount = node.querySelector(".metric-discount");
  let hasDiscountMetric = false;
  if (metricDiscount) {
    const discount = getDiscountPct(deal);
    if (discount > 0) {
      metricDiscount.textContent = `-${discount}%`;
      metricDiscount.hidden = false;
      metricDiscount.style.display = "";
      hasDiscountMetric = true;
    } else {
      metricDiscount.textContent = "";
      metricDiscount.hidden = true;
      metricDiscount.style.display = "none";
    }
  }

  const metricSales = node.querySelector(".metric-sales");
  let hasSalesMetric = false;
  if (metricSales) {
    const sales = Number(deal.sales || 0);
    if (sales > 0) {
      metricSales.textContent = `${sales.toLocaleString("es-ES")} vendidos`;
      metricSales.hidden = false;
      metricSales.style.display = "";
      hasSalesMetric = true;
    } else {
      metricSales.textContent = "";
      metricSales.hidden = true;
      metricSales.style.display = "none";
    }
  }

  const metricsRow = node.querySelector(".deal-metrics");
  let hasChollometerMetric = false;
  let hasHistoryMetric = false;

  if (metricsRow) {
    const score = getChollometerScore(deal);
    if (score >= 45) {
      const metric = document.createElement("span");
      metric.className = "metric metric-chollometer";
      metric.textContent = `🔥 ${score}/100 · ${getChollometerLabel(deal)}`;
      metricsRow.appendChild(metric);
      hasChollometerMetric = true;
    }

    const changePct = Number(deal.price_change_pct);
    if (Number.isFinite(changePct) && changePct < 0) {
      const metric = document.createElement("span");
      metric.className = "metric metric-price-drop";
      metric.textContent = `📉 ${formatSignedPct(changePct)} desde ${formatPriceCompact(deal.previous_price)}`;
      metricsRow.appendChild(metric);
      hasHistoryMetric = true;
    } else if (deal.is_recent_min_price) {
      const metric = document.createElement("span");
      metric.className = "metric metric-min-price";
      metric.textContent = "🏷️ mínimo 30 días";
      metricsRow.appendChild(metric);
      hasHistoryMetric = true;
    }

    const reasons = Array.isArray(deal.chollometer_reasons) ? deal.chollometer_reasons.filter(Boolean) : [];
    if (reasons.length) {
      const metric = document.createElement("span");
      metric.className = "metric metric-reason";
      metric.textContent = reasons.join(" · ");
      metricsRow.appendChild(metric);
      hasHistoryMetric = true;
    }

    const showMetrics = hasDiscountMetric || hasSalesMetric || hasChollometerMetric || hasHistoryMetric;
    metricsRow.hidden = !showMetrics;
    metricsRow.style.display = showMetrics ? "" : "none";
  }

  const actionBtn = node.querySelector(".deal-actions a");
  if (actionBtn) {
    actionBtn.href = url;
    actionBtn.textContent = "Ver en tienda";
    actionBtn.addEventListener("click", (event) => event.stopPropagation());
  }

  const favoriteBtn = node.querySelector(".favorite-btn");
  if (favoriteBtn) {
    favoriteBtn.textContent = isFavorite(deal) ? "♥" : "♡";
    favoriteBtn.classList.toggle("is-favorite", isFavorite(deal));
    favoriteBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleFavorite(deal);
    });
  }

  node.addEventListener("click", () => {
    window.open(url, "_blank", "noopener");
  });

  return node;
}

// ==============================
// FILTERS UI
// ==============================
function populateStoreFilter(deals) {
  const select = document.getElementById("storeFilter");
  if (!select) return;

  const currentValue = select.value || "";
  const stores = [...new Set(deals.map(getStoreLabel))].sort((a, b) => a.localeCompare(b));

  select.innerHTML = `<option value="">Todas</option>`;
  stores.forEach((store) => {
    const option = document.createElement("option");
    option.value = store;
    option.textContent = store;
    select.appendChild(option);
  });

  select.value = stores.includes(currentValue) ? currentValue : "";
}

function populateCategoryChips(deals) {
  const container = document.getElementById("categoryChips");
  if (!container) return;

  const categories = [...new Set(deals.map(inferBucket))].sort((a, b) => a.localeCompare(b));
  const current = document.getElementById("categoryFilter")?.value || "";
  container.innerHTML = "";

  const createChip = (label, value) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "filter-chip";
    btn.textContent = label;
    if (current === value) btn.classList.add("is-active");
    btn.addEventListener("click", () => {
      const select = document.getElementById("categoryFilter");
      if (!select) return;
      select.value = value;
      applyFiltersAndRender();
    });
    return btn;
  };

  container.appendChild(createChip("Todas", ""));
  categories.forEach((cat) => container.appendChild(createChip(cat, cat)));

  const categorySelect = document.getElementById("categoryFilter");
  if (categorySelect) {
    categorySelect.innerHTML = `<option value="">Todas</option>`;
    categories.forEach((cat) => {
      const option = document.createElement("option");
      option.value = cat;
      option.textContent = cat;
      categorySelect.appendChild(option);
    });
    categorySelect.value = categories.includes(current) ? current : "";
  }
}

// ==============================
// FILTER / SORT
// ==============================
function applyFilters(deals) {
  const search = normalizeText(document.getElementById("searchInput")?.value || "");
  const store = document.getElementById("storeFilter")?.value || "";
  const minDiscount = Number(document.getElementById("discountFilter")?.value || 0);
  const sort = document.getElementById("sortFilter")?.value || "recomendacion";
  const category = document.getElementById("categoryFilter")?.value || "";

  let result = [...deals];

  if (favoritesOnly) result = result.filter(isFavorite);

  if (search) {
    result = result.filter((deal) => {
      const haystack = normalizeText(`${deal.title || ""} ${deal.brand || ""} ${deal.category_hint || ""} ${getStoreLabel(deal)}`);
      return haystack.includes(search);
    });
  }

  if (store) result = result.filter((deal) => getStoreLabel(deal) === store);
  if (minDiscount > 0) result = result.filter((deal) => getDiscountPct(deal) >= minDiscount);
  if (category) result = result.filter((deal) => inferBucket(deal) === category);

  result.sort((a, b) => {
    if (sort === "discount") return getDiscountPct(b) - getDiscountPct(a);
    if (sort === "chollometer") return getChollometerScore(b) - getChollometerScore(a);
    if (sort === "price_asc") return (Number(a.price) || 0) - (Number(b.price) || 0);
    if (sort === "price_desc") return (Number(b.price) || 0) - (Number(a.price) || 0);
    if (sort === "sales") return (Number(b.sales) || 0) - (Number(a.sales) || 0);

    const scoreA = getChollometerScore(a) * 1000 + getDiscountPct(a) * 10 - (Number(a.price) || 0);
    const scoreB = getChollometerScore(b) * 1000 + getDiscountPct(b) * 10 - (Number(b.price) || 0);
    return scoreB - scoreA;
  });

  return result;
}

// ==============================
// RENDER MAIN
// ==============================
function renderTopPicks(deals) {
  const section = document.getElementById("topPicksSection");
  const container = document.getElementById("topPicksGrid");
  if (!section || !container) return;

  const picks = [...deals]
    .sort((a, b) => getChollometerScore(b) - getChollometerScore(a))
    .slice(0, 3);

  container.innerHTML = "";
  picks.forEach((deal) => container.appendChild(renderDealCard(deal)));
  section.hidden = picks.length === 0;
}

function renderDealsGrid(deals) {
  const container = document.getElementById("dealsGrid");
  if (!container) return;
  container.innerHTML = "";
  deals.slice(0, 60).forEach((deal) => container.appendChild(renderDealCard(deal)));
}

function renderDealsInfo(deals) {
  const info = document.getElementById("dealsInfo");
  if (!info) return;
  const stores = [...new Set(deals.map(getStoreLabel))];
  info.textContent = `${deals.length} oferta(s) encontrada(s)${stores.length ? ` · ${stores.join(", ")}` : ""}`;
}

function renderHomePage(deals) {
  renderSeoGuides(seoPages);
  renderTopPicks(deals);
  renderDealsGrid(deals);
  renderDealsInfo(deals);
}

function renderCurrentRoute(deals) {
  renderHomePage(deals);
}

// ==============================
// TOGGLES / MODALS
// ==============================
function setupCollapsible(sectionId, bodyId, buttonId, expandedText = "Ocultar", collapsedText = "Mostrar") {
  const section = document.getElementById(sectionId);
  const body = document.getElementById(bodyId);
  const button = document.getElementById(buttonId);
  if (!section || !body || !button) return;

  const isMobileViewport = () => window.matchMedia("(max-width: 768px)").matches;

  const sync = (expanded) => {
    body.hidden = !expanded;
    section.classList.toggle("is-collapsed", !expanded);
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    button.textContent = expanded ? expandedText : collapsedText;
  };

  const syncByViewport = () => {
    sync(!isMobileViewport());
  };

  syncByViewport();
  window.addEventListener("resize", syncByViewport);

  button.addEventListener("click", () => {
    const expanded = button.getAttribute("aria-expanded") === "true";
    sync(!expanded);
  });
}

function setupCookiesModal() {
  const banner = document.getElementById("cookieBanner");
  const modal = document.getElementById("cookiesModal");
  const acceptBtn = document.getElementById("acceptCookiesBtn");
  const moreInfoBtn = document.getElementById("cookieMoreInfo");
  const openBtn = document.getElementById("openCookiesPolicy");
  const closeBtn = document.getElementById("closeCookiesModal");
  const backdrop = document.querySelector("[data-close-cookies='true']");
  const key = "chollobici_cookie_notice_accepted";

  if (!banner || !modal) return;

  const openModal = () => {
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("has-modal-open");
  };
  const closeModal = () => {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("has-modal-open");
  };

  if (!localStorage.getItem(key)) banner.hidden = false;
  acceptBtn?.addEventListener("click", () => {
    localStorage.setItem(key, "1");
    banner.hidden = true;
  });
  moreInfoBtn?.addEventListener("click", openModal);
  openBtn?.addEventListener("click", openModal);
  closeBtn?.addEventListener("click", closeModal);
  backdrop?.addEventListener("click", closeModal);
}

// ==============================
// EVENTS
// ==============================
function attachEvents() {
  document.getElementById("searchInput")?.addEventListener("input", applyFiltersAndRender);
  document.getElementById("storeFilter")?.addEventListener("change", applyFiltersAndRender);
  document.getElementById("discountFilter")?.addEventListener("change", applyFiltersAndRender);
  document.getElementById("sortFilter")?.addEventListener("change", applyFiltersAndRender);
  document.getElementById("categoryFilter")?.addEventListener("change", applyFiltersAndRender);

  document.getElementById("favoritesToggle")?.addEventListener("click", () => {
    favoritesOnly = !favoritesOnly;
    const btn = document.getElementById("favoritesToggle");
    if (btn) {
      btn.setAttribute("aria-pressed", favoritesOnly ? "true" : "false");
      btn.textContent = favoritesOnly ? "♥ Solo favoritos" : "♡ Solo favoritos";
      btn.classList.toggle("is-active", favoritesOnly);
    }
    applyFiltersAndRender();
  });

  setupCollapsible("seoGuidesSection", "seoGuidesBody", "toggleGuidesBtn", "Ocultar", "Mostrar");
  setupCollapsible("filtersSection", "filtersBody", "toggleFiltersBtn", "Ocultar", "Mostrar");
  setupCookiesModal();
}

function applyFiltersAndRender() {
  filteredDeals = applyFilters(allDeals);
  populateCategoryChips(allDeals);
  renderCurrentRoute(filteredDeals);
}

// ==============================
// INIT
// ==============================
async function init() {
  try {
    const [dealsRes, seoRes] = await Promise.all([
      fetch(DATA_URL, { cache: "no-store" }),
      fetch(SEO_PAGES_URL, { cache: "no-store" }).catch(() => null),
    ]);

    const deals = await dealsRes.json();
    allDeals = Array.isArray(deals) ? deals : [];

    if (seoRes && seoRes.ok) {
      seoPages = await seoRes.json();
      if (!Array.isArray(seoPages)) seoPages = [];
    }

    populateStoreFilter(allDeals);
    populateCategoryChips(allDeals);
    attachEvents();
    applyFiltersAndRender();

    const lastUpdate = document.getElementById("lastUpdate");
    if (lastUpdate) lastUpdate.textContent = `Última actualización: ${new Date().toLocaleString("es-ES")}`;

    const currentYear = document.getElementById("currentYear");
    if (currentYear) currentYear.textContent = new Date().getFullYear();
  } catch (e) {
    console.error("Error cargando datos:", e);
  }
}

document.addEventListener("DOMContentLoaded", init);
