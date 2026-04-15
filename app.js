// ==============================
// CONFIG
// ==============================
const DATA_URL = "/data/generated_deals.json";

// ==============================
// STATE
// ==============================
let allDeals = [];
let filteredDeals = [];
let favoritesOnly = false;

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

function getStoreLabel(deal) {
  return deal.source_label || deal.store || deal.source || "Tienda";
}

function getCategoryLabel(deal) {
  return deal.category_hint || deal.category || "Ciclismo";
}

function getDealUrl(deal) {
  return deal.affiliate_url || deal.url || "#";
}

function getImageUrl(deal) {
  return deal.image || "/assets/chollobici-logo.png";
}

function safeText(value) {
  return String(value || "");
}

function normalizeText(value) {
  return safeText(value)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
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

  if (/(bicicleta|e-bike|ebike|gravel bike|mtb|mountain bike|urbana|carretera)/.test(text)) return "Bicis";
  if (/(casco|helmet)/.test(text)) return "Cascos";
  if (/(maillot|culotte|chaqueta|ropa|guantes|camiseta|malla|jersey|cubrezapatillas)/.test(text)) return "Ropa";
  if (/(luz|luces|faro|rear light|trasera)/.test(text)) return "Luces";
  if (/(sillin|sillin|manillar|pedal|cadena|freno|rueda|cubierta|camara|potencia|punos|grips|calas)/.test(text)) return "Componentes";
  if (/(herramienta|bomba|inflador|multiherramienta|soporte|portabidon|guardabarros|bolsa|bidon)/.test(text)) return "Accesorios";
  return "Otros";
}

function renderDealCard(deal) {
  const template = document.getElementById("dealCardTemplate");
  if (!template) return document.createElement("div");

  const node = template.content.firstElementChild.cloneNode(true);
  const url = getDealUrl(deal);

  const storePill = node.querySelector(".store-pill");
  if (storePill) storePill.textContent = getStoreLabel(deal);

  const image = node.querySelector(".deal-image");
  if (image) {
    image.src = getImageUrl(deal);
    image.alt = safeText(deal.title);
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
    } else {
      priceOld.textContent = "";
      priceOld.hidden = true;
    }
  }

  const metricDiscount = node.querySelector(".metric-discount");
  if (metricDiscount) {
    const discount = getDiscountPct(deal);
    if (discount > 0) {
      metricDiscount.textContent = `-${discount}%`;
      metricDiscount.hidden = false;
    } else {
      metricDiscount.hidden = true;
    }
  }

  const metricSales = node.querySelector(".metric-sales");
  if (metricSales) {
    const sales = Number(deal.sales || 0);
    if (sales > 0) {
      metricSales.textContent = `${sales.toLocaleString("es-ES")} vendidos`;
      metricSales.hidden = false;
    } else {
      metricSales.hidden = true;
    }
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
    btn.className = "chip-btn";
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
    if (sort === "price_asc") return (Number(a.price) || 0) - (Number(b.price) || 0);
    if (sort === "price_desc") return (Number(b.price) || 0) - (Number(a.price) || 0);
    if (sort === "sales") return (Number(b.sales) || 0) - (Number(a.sales) || 0);

    const storeBiasA = getStoreLabel(a) === "Decathlon" ? 50 : 0;
    const storeBiasB = getStoreLabel(b) === "Decathlon" ? 50 : 0;
    const scoreA = (getDiscountPct(a) * 1000) + storeBiasA - (Number(a.price) || 0);
    const scoreB = (getDiscountPct(b) * 1000) + storeBiasB - (Number(b.price) || 0);
    return scoreB - scoreA;
  });

  return result;
}

function buildTopPicks(deals, maxItems = 12) {
  const grouped = new Map();
  deals.forEach((deal) => {
    const bucket = inferBucket(deal);
    if (!grouped.has(bucket)) grouped.set(bucket, []);
    grouped.get(bucket).push(deal);
  });

  for (const [bucket, list] of grouped.entries()) {
    list.sort((a, b) => {
      const storeBiasA = getStoreLabel(a) === "Decathlon" ? 50 : 0;
      const storeBiasB = getStoreLabel(b) === "Decathlon" ? 50 : 0;
      const scoreA = (getDiscountPct(a) * 1000) + storeBiasA - (Number(a.price) || 0);
      const scoreB = (getDiscountPct(b) * 1000) + storeBiasB - (Number(b.price) || 0);
      return scoreB - scoreA;
    });
    grouped.set(bucket, list);
  }

  const picks = [];
  let added = true;
  while (picks.length < maxItems && added) {
    added = false;
    for (const [, list] of grouped.entries()) {
      if (list.length && picks.length < maxItems) {
        picks.push(list.shift());
        added = true;
      }
    }
  }
  return picks;
}

function renderTopPicks(deals) {
  const container = document.getElementById("topPicksGrid");
  if (!container) return;
  container.innerHTML = "";
  buildTopPicks(deals, 12).forEach((deal) => container.appendChild(renderDealCard(deal)));
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
  info.textContent = `${deals.length} oferta(s) encontrada(s) · ${stores.join(", ")}`;
}

function renderHomePage(deals) {
  renderTopPicks(deals);
  renderDealsGrid(deals);
  renderDealsInfo(deals);
}

function renderCurrentRoute(deals) {
  renderHomePage(deals);
}

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
    }
    applyFiltersAndRender();
  });
}

function applyFiltersAndRender() {
  filteredDeals = applyFilters(allDeals);
  populateCategoryChips(allDeals);
  renderCurrentRoute(filteredDeals);
}

async function init() {
  try {
    const res = await fetch(DATA_URL, { cache: "no-store" });
    const deals = await res.json();
    allDeals = Array.isArray(deals) ? deals : [];

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
