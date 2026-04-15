// ==============================
// CONFIG
// ==============================
const DATA_URL = "/data/generated_deals.json";

// ==============================
// HELPERS
// ==============================
function formatPrice(price) {
  const num = Number(price);
  if (!Number.isFinite(num) || num <= 0) return "";
  return num.toFixed(2).replace(".", ",") + " €";
}

function escapeHtml(text) {
  return String(text || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function getDiscountPct(deal) {
  const explicit = Number(deal.discount_pct);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;

  const p = Number(deal.price);
  const o = Number(deal.old_price);
  if (Number.isFinite(p) && Number.isFinite(o) && o > p && o > 0) {
    return Math.round(((o - p) / o) * 100);
  }
  return 0;
}

function getImage(deal) {
  return deal.image || "/assets/chollobici-logo.png";
}

function getUrl(deal) {
  return deal.affiliate_url || deal.url || "#";
}

function getStore(deal) {
  return deal.source_label || deal.store || deal.source || "Tienda";
}

function getCategory(deal) {
  return deal.category_hint || deal.category || "";
}

// ==============================
// CARD
// ==============================
function renderDealCard(deal) {
  const url = getUrl(deal);
  const image = getImage(deal);
  const title = escapeHtml(deal.title || "Producto");
  const store = escapeHtml(getStore(deal));
  const category = escapeHtml(getCategory(deal));
  const price = formatPrice(deal.price);
  const oldPrice = formatPrice(deal.old_price);
  const discount = getDiscountPct(deal);

  return `
    <article class="deal-card card" onclick="window.open('${url}','_blank')" style="cursor:pointer;">
      <div class="deal-image-wrap">
        <span class="store-pill">${store}</span>
        <img class="deal-image" src="${image}" alt="${title}" loading="lazy">
      </div>
      <div class="deal-body">
        ${category ? `<div class="deal-category">${category}</div>` : ""}
        <h2 class="deal-title">${title}</h2>
        <div class="price-row">
          <span class="price-current">${price}</span>
          ${oldPrice && oldPrice !== price ? `<span class="price-old">${oldPrice}</span>` : ""}
        </div>
        <div class="deal-metrics">
          ${discount > 0 ? `<span class="metric metric-discount">-${discount}%</span>` : ""}
        </div>
        <div class="deal-actions">
          <a
            class="btn"
            href="${url}"
            target="_blank"
            rel="noopener sponsored nofollow"
            onclick="event.stopPropagation();"
          >Ver en tienda</a>
        </div>
      </div>
    </article>
  `;
}

// ==============================
// RENDER
// ==============================
function renderTopPicks(deals) {
  const container = document.getElementById("topPicksGrid");
  console.log("[CholloBici] topPicksGrid:", !!container, "items:", deals.length);
  if (!container) return;

  container.innerHTML = deals.slice(0, 12).map(renderDealCard).join("");
}

function renderDealsGrid(deals) {
  const container = document.getElementById("dealsGrid");
  console.log("[CholloBici] dealsGrid:", !!container, "items:", deals.length);
  if (!container) return;

  container.innerHTML = deals.slice(0, 60).map(renderDealCard).join("");
}

function renderDealsInfo(deals) {
  const info = document.getElementById("dealsInfo");
  if (!info) return;
  info.textContent = `${deals.length} producto(s) cargado(s)`;
}

function renderHomePage(deals) {
  renderTopPicks(deals);
  renderDealsGrid(deals);
  renderDealsInfo(deals);
}

function renderCurrentRoute(deals) {
  renderHomePage(deals);
}

// ==============================
// INIT
// ==============================
async function init() {
  try {
    console.log("[CholloBici] Cargando", DATA_URL);
    const res = await fetch(DATA_URL, { cache: "no-store" });
    console.log("[CholloBici] HTTP", res.status);

    const deals = await res.json();
    console.log("[CholloBici] deals cargados:", Array.isArray(deals) ? deals.length : "no-array");
    console.log("[CholloBici] primer deal:", deals?.[0]);

    if (!Array.isArray(deals) || deals.length === 0) {
      console.warn("[CholloBici] No hay deals para pintar");
      renderDealsInfo([]);
      return;
    }

    deals.sort((a, b) => {
      const bd = getDiscountPct(b);
      const ad = getDiscountPct(a);
      if (bd !== ad) return bd - ad;
      return (Number(b.price) || 0) - (Number(a.price) || 0);
    });

    renderCurrentRoute(deals);
  } catch (e) {
    console.error("[CholloBici] Error cargando datos:", e);
  }
}

document.addEventListener("DOMContentLoaded", init);