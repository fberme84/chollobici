async function loadDeals() {
  try {
    const response = await fetch("data/generated_deals.json");
    const deals = await response.json();

    window.allDeals = deals;

    renderDeals(deals);
  } catch (error) {
    console.error("Error cargando las ofertas", error);
  }
}

function formatPrice(price, currency) {
  if (!price) return "Ver precio";
  return `${price} ${currency || "€"}`;
}

function renderDeals(deals) {
  const container = document.getElementById("deals-container");
  container.innerHTML = deals.map(renderDeal).join("");
}

function renderDeal(deal) {
  return `
    <div class="deal-card">

      ${deal.discount ? `<span class="badge">-${deal.discount}</span>` : ""}

      <img src="${deal.image}" alt="${deal.title}">

      <h3 class="title">${deal.title}</h3>

      <div class="price-row">
        <span class="price">${formatPrice(deal.price, deal.currency)}</span>
        ${deal.old_price ? `<span class="old-price">${formatPrice(deal.old_price, deal.currency)}</span>` : ""}
      </div>

      <div class="meta">
        ${deal.sales ? `⭐ ${deal.sales} ventas` : ""}
      </div>

      <a href="${deal.url}" target="_blank" rel="noopener noreferrer" class="deal-card-button">
        ${deal.source === "amazon" ? "Ver en Amazon" : "Ver en AliExpress"}
      </a>

    </div>
  `;
}

function filterDeals(category) {
  const deals = window.allDeals || [];

  if (category === "Todos") {
    renderDeals(deals);
    return;
  }

  const filtered = deals.filter(d => d.category === category);
  renderDeals(filtered);
}

loadDeals();
