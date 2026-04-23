// PATCH imagen + ocultar métricas

function getImageUrl(deal) {
  const value = String(deal.image || "").trim();
  if (!value || value.length < 10 || value.includes("</") || !value.startsWith("http")) {
    return "/assets/placeholder-product.svg";
  }
  return value;
}

// dentro del render de cada card:

function applyMetrics(node, deal) {
  const priceOld = node.querySelector(".price-old");
  if (priceOld) {
    if (deal.old_price && deal.old_price > deal.price) {
      priceOld.textContent = deal.old_price + " €";
      priceOld.style.display = "";
    } else {
      priceOld.style.display = "none";
    }
  }

  const discountEl = node.querySelector(".metric-discount");
  let showDiscount = false;
  if (discountEl && deal.discount_pct > 0) {
    discountEl.textContent = "-" + deal.discount_pct + "%";
    discountEl.style.display = "";
    showDiscount = true;
  } else if (discountEl) {
    discountEl.style.display = "none";
  }

  const salesEl = node.querySelector(".metric-sales");
  let showSales = false;
  if (salesEl && deal.sales > 0) {
    salesEl.textContent = deal.sales + " vendidos";
    salesEl.style.display = "";
    showSales = true;
  } else if (salesEl) {
    salesEl.style.display = "none";
  }

  const row = node.querySelector(".deal-metrics");
  if (row) {
    row.style.display = (showDiscount || showSales) ? "" : "none";
  }
}
