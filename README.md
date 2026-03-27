# Detector de Chollos Ciclistas

MVP estático para GitHub Pages con actualización automática de datos mediante GitHub Actions.

## Estructura

- `index.html`, `app.js`, `styles.css`: frontal estático.
- `data/amazon_products.json`: catálogo base de productos Amazon.
- `data/deals.json`: ofertas visibles en la web.
- `data/history.json`: histórico mínimo de precios.
- `scripts/update_deals.py`: regeneración automática de datos y aplicación del tag de afiliado.
- `.github/workflows/update-data.yml`: job diario.
- `.github/workflows/deploy-pages.yml`: despliegue a GitHub Pages.

## Secret necesario

En GitHub, añade este secret del repositorio en `Settings > Secrets and variables > Actions`:

- `AMAZON_PARTNER_TAG` = `chollobici0a-21`

## Puesta en marcha

1. Sube el contenido al repositorio.
2. En GitHub, activa **Pages** con fuente **GitHub Actions**.
3. Añade el secret `AMAZON_PARTNER_TAG`.
4. Lanza manualmente el workflow `Update deals data`.
5. Lanza manualmente `Deploy static site to GitHub Pages`.

## Nota legal sugerida

Incluye en la web un aviso de afiliación, por ejemplo:

> Como afiliado de Amazon, obtengo ingresos por las compras adscritas.
