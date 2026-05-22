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
let premiumOnly = false;
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

function hasRealImage(deal) {
  return getImageUrl(deal) !== "/assets/placeholder-product.svg";
}

function getDealQualityScore(deal) {
  const explicit = Number(deal.quality_score);
  if (Number.isFinite(explicit)) return Math.max(0, Math.min(100, Math.round(explicit)));

  let score = 0;

  const title = safeText(deal.title).trim();
  if (title.length >= 16) score += 20;
  else if (title.length >= 10) score += 12;

  if (hasRealImage(deal)) score += 10;
  if (getProductDetailUrl(deal)) score += 10;

  score += Math.round(getChollometerScore(deal) * 0.3);
  score += Math.min(20, Math.round(getDiscountPct(deal) * 0.6));

  const sales = Number(deal.sales || 0);
  if (sales > 0) score += Math.min(10, Math.round(Math.log10(sales + 1) * 4));

  if (deal.is_price_drop) score += 4;
  if (deal.is_recent_min_price) score += 6;

  return Math.max(0, Math.min(100, score));
}

function isPremiumDeal(deal) {
  if (typeof deal.is_premium_quality === "boolean") return deal.is_premium_quality;
  return getDealQualityScore(deal) >= 70;
}

function getDealIdentityKey(deal) {
  const detail = safeText(deal.product_detail_path || deal.product_detail_url);
  if (detail) return `detail:${detail.toLowerCase()}`;

  const id = safeText(deal.id || deal.product_id);
  if (id) return `id:${id.toLowerCase()}`;

  const href = safeText(getDealUrl(deal));
  if (href && href !== "#") return `url:${href.toLowerCase()}`;

  return `fallback:${slugify(safeText(deal.title))}:${slugify(getStoreLabel(deal))}`;
}

function isRenderableDeal(deal) {
  if (!deal || typeof deal !== "object") return false;

  const title = safeText(deal.title).trim();
  if (title.length < 8) return false;

  const price = Number(deal.price);
  if (!Number.isFinite(price) || price <= 0) return false;

  const detailUrl = getProductDetailUrl(deal);
  if (detailUrl) return true;

  const url = safeText(getDealUrl(deal)).trim();
  return /^https?:\/\//i.test(url);
}

function pickBetterDeal(current, candidate) {
  const scoreCurrent = getChollometerScore(current) * 1000 + getDiscountPct(current) * 10 + (Number(current.sales) || 0);
  const scoreCandidate = getChollometerScore(candidate) * 1000 + getDiscountPct(candidate) * 10 + (Number(candidate.sales) || 0);
  if (scoreCandidate > scoreCurrent) return candidate;
  if (scoreCandidate < scoreCurrent) return current;

  const priceCurrent = Number(current.price) || Number.POSITIVE_INFINITY;
  const priceCandidate = Number(candidate.price) || Number.POSITIVE_INFINITY;
  return priceCandidate < priceCurrent ? candidate : current;
}

function prepareDeals(rawDeals) {
  const cleanDeals = (Array.isArray(rawDeals) ? rawDeals : []).filter(isRenderableDeal);
  const byKey = new Map();

  cleanDeals.forEach((deal) => {
    const key = getDealIdentityKey(deal);
    if (!byKey.has(key)) {
      byKey.set(key, deal);
      return;
    }
    byKey.set(key, pickBetterDeal(byKey.get(key), deal));
  });

  return [...byKey.values()];
}

function pickTopCuratedDeals(deals, limit = 3) {
  const sorted = [...deals].sort((a, b) => getDealEditorialScore(b) - getDealEditorialScore(a));
  const picked = [];
  const pickedKeys = new Set();
  const usedStores = new Set();
  const usedCategories = new Set();

  for (const deal of sorted) {
    if (picked.length >= limit) break;
    const key = getDealIdentityKey(deal);
    const store = getStoreLabel(deal);
    const category = inferBucket(deal);
    if (pickedKeys.has(key) || usedStores.has(store) || usedCategories.has(category)) continue;
    picked.push(deal);
    pickedKeys.add(key);
    usedStores.add(store);
    usedCategories.add(category);
  }

  for (const deal of sorted) {
    if (picked.length >= limit) break;
    const key = getDealIdentityKey(deal);
    const store = getStoreLabel(deal);
    if (pickedKeys.has(key) || usedStores.has(store)) continue;
    picked.push(deal);
    pickedKeys.add(key);
    usedStores.add(store);
  }

  for (const deal of sorted) {
    if (picked.length >= limit) break;
    const key = getDealIdentityKey(deal);
    if (pickedKeys.has(key)) continue;
    picked.push(deal);
    pickedKeys.add(key);
  }

  return picked;
}

function getProductDetailUrl(deal) {
  const value = deal.product_detail_path || deal.product_detail_url || "";
  if (!value) return "";
  try {
    const parsed = new URL(value, window.location.origin);
    if (parsed.origin === window.location.origin && parsed.pathname.startsWith("/producto/")) {
      return parsed.pathname.endsWith("/") ? parsed.pathname : parsed.pathname + "/";
    }
  } catch {
    // Si no es una URL absoluta válida, tratamos el valor como ruta local.
  }
  if (String(value).startsWith("/producto/")) {
    return String(value).endsWith("/") ? String(value) : String(value) + "/";
  }
  return "";
}

function getShareUrl(deal) {
  return getProductDetailUrl(deal) || getDealUrl(deal);
}

async function copyText(value) {
  if (!navigator.clipboard?.writeText) return false;
  try {
    await navigator.clipboard.writeText(value);
    return true;
  } catch {
    return false;
  }
}

async function shareDealOnWhatsApp(deal, button) {
  const shareUrl = getShareUrl(deal);
  if (!shareUrl || shareUrl === "#") return;

  const title = safeText(deal.title).trim();
  const message = `${title}\n${shareUrl}`;

  if (navigator.share) {
    try {
      await navigator.share({
        title,
        text: title,
        url: shareUrl,
      });
      return;
    } catch {
      // Continue with WhatsApp + copy fallback.
    }
  }

  const copied = await copyText(message);
  if (button && copied) {
    const previousTitle = button.getAttribute("title") || "Compartir por WhatsApp";
    button.classList.add("is-copied");
    button.setAttribute("title", "Enlace copiado");
    button.setAttribute("aria-label", "Enlace copiado");
    window.setTimeout(() => {
      button.classList.remove("is-copied");
      button.setAttribute("title", previousTitle);
      button.setAttribute("aria-label", "Compartir por WhatsApp");
    }, 1400);
  }

  const waUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
  window.open(waUrl, "_blank", "noopener");
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

function getDealPriceBand(deal) {
  const price = Number(deal.price);
  if (!Number.isFinite(price)) return "unknown";
  if (price < 5) return "low";
  if (price < 25) return "mid";
  return "high";
}

function getTitleNoisePenalty(deal) {
  const title = safeText(deal.title).trim();
  if (!title) return 0;

  let penalty = 0;
  if (title.length > 120) penalty += 8;
  else if (title.length > 95) penalty += 4;

  const upperChars = title.replace(/[^A-Z]/g, "").length;
  const alphaChars = title.replace(/[^a-zA-Z]/g, "").length;
  if (alphaChars > 0 && upperChars / alphaChars > 0.32) penalty += 5;

  if (/\b(nuevo|original|oferta|mejor|top|premium)\b/gi.test(title) && title.length > 85) penalty += 3;
  if (/[|]{2,}|\*{2,}/.test(title)) penalty += 2;

  return penalty;
}

function getDealEditorialScore(deal) {
  const quality = getDealQualityScore(deal);
  const chollometer = getChollometerScore(deal);
  const discount = Math.min(55, getDiscountPct(deal));
  const sales = Number(deal.sales || 0);

  let score = quality * 1.25 + chollometer * 0.7 + discount * 0.55;

  if (hasRealImage(deal)) score += 8;
  if (getProductDetailUrl(deal)) score += 8;
  if (deal.is_price_drop) score += 5;
  if (deal.is_recent_min_price) score += 5;
  if (sales > 0) score += Math.min(10, Math.log10(sales + 1) * 4);

  const price = Number(deal.price);
  if (Number.isFinite(price) && price >= 8 && price <= 80) score += 6;
  if (Number.isFinite(price) && price < 3.5) score -= 6;

  score -= getTitleNoisePenalty(deal);

  return score;
}

function getDealReasons(deal, maxItems = 2) {
  const qualityReasons = Array.isArray(deal.quality_reasons) ? deal.quality_reasons : [];
  const cholloReasons = Array.isArray(deal.chollometer_reasons) ? deal.chollometer_reasons : [];
  const reasons = [...qualityReasons, ...cholloReasons]
    .map((reason) => safeText(reason).trim())
    .filter(Boolean);

  if (reasons.length) return reasons.slice(0, maxItems);

  const fallback = [];
  if (getDealQualityScore(deal) >= 70) fallback.push("Calidad de ficha por encima de la media");
  if (getDiscountPct(deal) >= 20) fallback.push("Descuento relevante sobre su precio base");
  if (hasRealImage(deal)) fallback.push("Imagen real para validar mejor el producto");
  return fallback.slice(0, maxItems);
}

function buildCuratedRecommendedOrder(deals, options = {}) {
  const firstWindow = Math.min(12, deals.length);
  if (firstWindow <= 1) return [...deals];

  const maxStoreInWindow = options.lockStore ? Number.POSITIVE_INFINITY : 3;
  const maxCategoryInWindow = options.lockCategory ? Number.POSITIVE_INFINITY : 4;
  const maxLowPriceInWindow = 4;

  const pending = [...deals];
  const selected = [];
  const storeCount = new Map();
  const categoryCount = new Map();
  let lowPriceCount = 0;
  let strictMode = true;

  const canPlaceInWindow = (deal) => {
    if (!strictMode || selected.length >= firstWindow) return true;

    const store = getStoreLabel(deal);
    const category = inferBucket(deal);
    const isLowPrice = getDealPriceBand(deal) === "low";

    if ((storeCount.get(store) || 0) >= maxStoreInWindow) return false;
    if ((categoryCount.get(category) || 0) >= maxCategoryInWindow) return false;
    if (isLowPrice && lowPriceCount >= maxLowPriceInWindow) return false;

    return true;
  };

  const registerWindowPlacement = (deal) => {
    if (selected.length > firstWindow) return;
    const store = getStoreLabel(deal);
    const category = inferBucket(deal);
    storeCount.set(store, (storeCount.get(store) || 0) + 1);
    categoryCount.set(category, (categoryCount.get(category) || 0) + 1);
    if (getDealPriceBand(deal) === "low") lowPriceCount += 1;
  };

  while (pending.length) {
    let addedInPass = false;

    for (let idx = 0; idx < pending.length; idx += 1) {
      const deal = pending[idx];
      if (!canPlaceInWindow(deal)) continue;

      const withinWindow = selected.length < firstWindow;
      selected.push(deal);
      pending.splice(idx, 1);
      idx -= 1;
      addedInPass = true;

      if (withinWindow) registerWindowPlacement(deal);
    }

    if (addedInPass) continue;
    if (strictMode) {
      strictMode = false;
      continue;
    }

    selected.push(...pending);
    break;
  }

  return selected;
}

function pickDailyRecommendationDeal(deals) {
  if (!Array.isArray(deals) || deals.length === 0) return null;

  const dominantStores = new Map();
  deals.slice(0, 8).forEach((deal) => {
    const store = getStoreLabel(deal);
    dominantStores.set(store, (dominantStores.get(store) || 0) + 1);
  });
  let dominantStore = "";
  let dominantCount = 0;
  dominantStores.forEach((count, store) => {
    if (count > dominantCount) {
      dominantCount = count;
      dominantStore = store;
    }
  });

  let bestDeal = null;
  let bestScore = Number.NEGATIVE_INFINITY;
  deals.slice(0, 20).forEach((deal) => {
    const store = getStoreLabel(deal);
    let score = getDealEditorialScore(deal);
    if (dominantStore && store === dominantStore && dominantCount >= 3) score -= 14;
    if (getDealReasons(deal, 2).length >= 2) score += 4;

    if (score > bestScore) {
      bestScore = score;
      bestDeal = deal;
    }
  });

  return bestDeal;
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
  let hasQualityMetric = false;
  let hasChollometerMetric = false;
  let hasHistoryMetric = false;

  if (metricsRow) {
    const quality = getDealQualityScore(deal);
    if (quality >= 55) {
      const metric = document.createElement("span");
      metric.className = `metric metric-quality ${quality >= 70 ? "is-premium" : ""}`;
      metric.textContent = `⭐ Calidad ${quality}/100`;
      metricsRow.appendChild(metric);
      hasQualityMetric = true;
    }

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

    const showMetrics = hasDiscountMetric || hasSalesMetric || hasQualityMetric || hasChollometerMetric || hasHistoryMetric;
    metricsRow.hidden = !showMetrics;
    metricsRow.style.display = showMetrics ? "" : "none";
  }

  const actionBtn = node.querySelector(".btn-store");
  if (actionBtn) {
    actionBtn.href = url;
    actionBtn.textContent = "Ver en tienda";
    actionBtn.addEventListener("click", (event) => event.stopPropagation());
  }

  const shareBtn = node.querySelector(".btn-share-icon");
  if (shareBtn) {
    shareBtn.addEventListener("click", async (event) => {
      event.stopPropagation();
      await shareDealOnWhatsApp(deal, shareBtn);
    });
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

  const detailUrl = getProductDetailUrl(deal);
  node.addEventListener("click", () => {
    if (detailUrl) {
      window.location.href = detailUrl;
    } else {
      window.open(url, "_blank", "noopener");
    }
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
  if (premiumOnly) result = result.filter(isPremiumDeal);

  if (sort === "recomendacion") {
    result.sort((a, b) => getDealEditorialScore(b) - getDealEditorialScore(a));
    result = buildCuratedRecommendedOrder(result, {
      lockStore: Boolean(store),
      lockCategory: Boolean(category),
    });
    return result;
  }

  result.sort((a, b) => {
    if (sort === "quality") return getDealQualityScore(b) - getDealQualityScore(a);
    if (sort === "discount") return getDiscountPct(b) - getDiscountPct(a);
    if (sort === "chollometer") return getChollometerScore(b) - getChollometerScore(a);
    if (sort === "price_asc") return (Number(a.price) || 0) - (Number(b.price) || 0);
    if (sort === "price_desc") return (Number(b.price) || 0) - (Number(a.price) || 0);
    if (sort === "sales") return (Number(b.sales) || 0) - (Number(a.sales) || 0);

    return getDealQualityScore(b) - getDealQualityScore(a);
  });

  return result;
}

// ==============================
// RENDER MAIN
// ==============================
function renderTopPicks(deals) {
  const section = document.getElementById("topPicksSection");
  const container = document.getElementById("topPicksGrid");
  if (!section || !container) return [];

  const picks = pickTopCuratedDeals(deals, 3);

  container.innerHTML = "";
  picks.forEach((deal) => container.appendChild(renderDealCard(deal)));
  section.hidden = picks.length === 0;
  return picks;
}

function renderDailyRecommendation(deals) {
  const section = document.getElementById("dailyRecommendationSection");
  const container = document.getElementById("dailyRecommendationCard");
  if (!section || !container) return null;

  const deal = pickDailyRecommendationDeal(deals);
  container.innerHTML = "";

  if (!deal) {
    section.hidden = true;
    return null;
  }

  const card = document.createElement("article");
  card.className = "daily-reco-card card";

  const media = document.createElement("div");
  media.className = "daily-reco-media";
  const image = document.createElement("img");
  image.className = "daily-reco-image";
  image.src = getImageUrl(deal);
  image.alt = safeText(deal.title);
  image.loading = "lazy";
  image.onerror = () => {
    image.onerror = null;
    image.src = "/assets/placeholder-product.svg";
  };
  media.appendChild(image);

  const storePill = document.createElement("span");
  storePill.className = `store-pill ${getStoreClass(deal)}`;
  storePill.dataset.store = getStoreLabel(deal);
  storePill.textContent = getStoreLabel(deal);
  media.appendChild(storePill);

  const content = document.createElement("div");
  content.className = "daily-reco-content";

  const kicker = document.createElement("span");
  kicker.className = "daily-reco-kicker";
  kicker.textContent = "Elegida hoy";
  content.appendChild(kicker);

  const title = document.createElement("h3");
  title.textContent = safeText(deal.title);
  content.appendChild(title);

  const note = document.createElement("p");
  note.className = "daily-reco-note";
  note.textContent = "Equilibrio entre precio, calidad editorial y utilidad real para el día a día.";
  content.appendChild(note);

  const reasons = getDealReasons(deal, 2);
  if (reasons.length) {
    const list = document.createElement("ul");
    list.className = "daily-reco-reasons";
    reasons.forEach((reason) => {
      const item = document.createElement("li");
      item.textContent = reason;
      list.appendChild(item);
    });
    content.appendChild(list);
  }

  const priceRow = document.createElement("div");
  priceRow.className = "daily-reco-price-row";

  const current = document.createElement("strong");
  current.textContent = formatPrice(deal.price);
  priceRow.appendChild(current);

  const discount = getDiscountPct(deal);
  if (discount > 0) {
    const discountEl = document.createElement("span");
    discountEl.className = "daily-reco-discount";
    discountEl.textContent = `-${discount}%`;
    priceRow.appendChild(discountEl);
  }

  const oldPrice = formatPrice(deal.old_price);
  const currentPrice = formatPrice(deal.price);
  if (oldPrice && oldPrice !== currentPrice) {
    const old = document.createElement("span");
    old.className = "daily-reco-old-price";
    old.textContent = oldPrice;
    priceRow.appendChild(old);
  }
  content.appendChild(priceRow);

  const actions = document.createElement("div");
  actions.className = "deal-actions daily-reco-actions";

  const actionBtn = document.createElement("a");
  actionBtn.className = "btn btn-store";
  actionBtn.href = getDealUrl(deal);
  actionBtn.target = "_blank";
  actionBtn.rel = "noopener sponsored nofollow";
  actionBtn.textContent = "Ver en tienda";
  actionBtn.addEventListener("click", (event) => event.stopPropagation());
  actions.appendChild(actionBtn);

  const shareBtn = document.createElement("button");
  shareBtn.type = "button";
  shareBtn.className = "btn btn-light btn-share-icon";
  shareBtn.setAttribute("aria-label", "Compartir por WhatsApp");
  shareBtn.setAttribute("title", "Compartir por WhatsApp");
  shareBtn.addEventListener("click", async (event) => {
    event.stopPropagation();
    await shareDealOnWhatsApp(deal, shareBtn);
  });
  actions.appendChild(shareBtn);

  content.appendChild(actions);

  card.appendChild(media);
  card.appendChild(content);

  const detailUrl = getProductDetailUrl(deal);
  card.addEventListener("click", () => {
    if (detailUrl) {
      window.location.href = detailUrl;
    } else {
      window.open(getDealUrl(deal), "_blank", "noopener");
    }
  });

  container.appendChild(card);
  section.hidden = false;
  return deal;
}

function renderDealsGrid(deals, excludedKeys = new Set()) {
  const container = document.getElementById("dealsGrid");
  if (!container) return;
  container.innerHTML = "";

  const list = deals.filter((deal) => !excludedKeys.has(getDealIdentityKey(deal)));
  list.slice(0, 60).forEach((deal) => container.appendChild(renderDealCard(deal)));
}

function renderDealsInfo(deals) {
  const info = document.getElementById("dealsInfo");
  if (!info) return;
  const stores = [...new Set(deals.map(getStoreLabel))];
  const premiumCount = deals.filter(isPremiumDeal).length;
  info.textContent = `${deals.length} oferta(s) encontrada(s) · ${premiumCount} premium${stores.length ? ` · ${stores.join(", ")}` : ""}`;
}

function renderHomePage(deals) {
  renderSeoGuides(seoPages);
  const dailyRecommendation = renderDailyRecommendation(deals);
  const dailyKey = dailyRecommendation ? getDealIdentityKey(dailyRecommendation) : "";
  const topSource = dailyKey ? deals.filter((deal) => getDealIdentityKey(deal) !== dailyKey) : deals;
  const topPicks = renderTopPicks(topSource);
  const excluded = new Set(topPicks.map(getDealIdentityKey));
  if (dailyKey) excluded.add(dailyKey);
  renderDealsGrid(deals, excluded);
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

  document.getElementById("premiumToggle")?.addEventListener("click", () => {
    premiumOnly = !premiumOnly;
    const btn = document.getElementById("premiumToggle");
    if (btn) {
      btn.setAttribute("aria-pressed", premiumOnly ? "true" : "false");
      btn.textContent = premiumOnly ? "★ Solo premium" : "☆ Solo premium";
      btn.classList.toggle("is-active", premiumOnly);
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
      fetch(DATA_URL),
      fetch(SEO_PAGES_URL).catch(() => null),
    ]);

    const deals = await dealsRes.json();
    allDeals = prepareDeals(deals);

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
