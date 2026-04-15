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
// RENDER HELPERS (CLAVE)
// ==============================
function renderDealHeadingLink(deal) {
  // SIN ficha → solo texto
  return `<span class="deal-title">${deal.title}</span>`;
}

function renderDetailButton(deal) {
  // SIN ficha → no mostramos botón
  return "";
}

function renderShopButton(deal) {
  if (!deal.affiliate_url) return "";

  return `
    <a href="${deal.affiliate_url}" 
       target="_blank" 
       rel="noopener sponsored nofollow"
       class="btn-primary">
       Ver en tienda
    </a>
  `;
}

// ==============================
// CARD
// ==============================
function renderDealCard(deal) {
  return `
    <div class="deal-card">
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
          ${renderDetailButton(deal)}
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

  let html = "";

  deals.forEach(deal => {
    html += renderDealCard(deal);
  });

  container.innerHTML = html;
}

// ==============================
// HOME
// ==============================
function renderHomePage(deals) {
  renderTopPicks(deals);
}

// ==============================
// ROUTER SIMPLE
// ==============================
function renderCurrentRoute(deals) {
  const path = window.location.pathname;

  // solo home de momento
  renderHomePage(deals);
}

// ==============================
// INIT
// ==============================
async function init() {
  try {
    const res = await fetch(DATA_URL);
    const deals = await res.json();

    renderCurrentRoute(deals);

  } catch (e) {
    console.error("Error cargando datos:", e);
  }
}

init();