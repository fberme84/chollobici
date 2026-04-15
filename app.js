// ==============================
// CONFIG
// ==============================
const DATA_URL = "/data/generated_deals.json";

// ==============================
// HELPERS
// ==============================
function slugify(text) {
  return text
    .toString()
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function formatPrice(price) {
  if (!price) return "";
  return price.toFixed(2).replace(".", ",") + " €";
}

// ==============================
// RENDER HELPERS
// ==============================
function renderDealHeadingLink(deal) {
  return `<span class="deal-title">${deal.title}</span>`;
}

function renderDetailButton(deal) {
  return "";
}

function renderShopButton(deal) {
  if (!deal.affiliate_url) return "";

  return `
    <a href="${deal.affiliate_url}" 
       target="_blank" 
       rel="noopener sponsored nofollow"
       class="btn-primary"
       onclick="event.stopPropagation();">
       Ver en tienda
    </a>
  `;
}

// ==============================
// CARD
// ==============================
function renderDealCard(deal) {
  const url = deal.affiliate_url || deal.url;

  return `
    <div class="deal-card" onclick="window.open('${url}', '_blank')">
      
      <div class="deal-image">
        <img src="${deal.image}" alt="${deal.title}" />
      </div>

      <div class="deal-body">
        ${renderDealHeadingLink(deal)}

        <div class="deal-price">
          ${formatPrice(deal.price)}
        </div>

        <div class="deal-actions">
          ${renderShopButton(deal)}
        </div>
      </div>

    </div>
  `;
}

// ==============================
// TOP PICKS
// ==============================
function renderTopPicks(deals) {
  const container = document.getElementById("top-picks");
  if (!container) return;

  container.innerHTML = deals.slice(0, 12).map(renderDealCard).join("");
}

// ==============================
// LISTADO COMPLETO
// ==============================
function renderDealsGrid(deals) {
  const container = document.getElementById("deals-grid");
  if (!container) return;

  container.innerHTML = deals.slice(0, 60).map(renderDealCard).join("");
}

// ==============================
// HOME
// ==============================
function renderHomePage(deals) {
  renderTopPicks(deals);
  renderDealsGrid(deals); // 🔥 ESTE ERA EL FALLO
}

// ==============================
// ROUTER SIMPLE
// ==============================
function renderCurrentRoute(deals) {
  renderHomePage(deals);
}

// ==============================
// INIT
// ==============================
async function init() {
  try {
    const res = await fetch(DATA_URL);
    const deals = await res.json();

    // ordenar por descuento si existe
    deals.sort((a, b) => (b.discount_pct || 0) - (a.discount_pct || 0));

    renderCurrentRoute(deals);

  } catch (e) {
    console.error("Error cargando datos:", e);
  }
}

init();