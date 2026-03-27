# Detector de Chollos Ciclistas

MVP estático para GitHub Pages con actualización automática de datos mediante GitHub Actions.

## Estructura

- `index.html`, `app.js`, `styles.css`: frontal estático.
- `data/deals.json`: ofertas visibles.
- `data/history.json`: histórico mínimo de precios.
- `scripts/update_deals.py`: regeneración automática de datos.
- `.github/workflows/update-data.yml`: job diario.
- `.github/workflows/deploy-pages.yml`: despliegue a GitHub Pages.

## Puesta en marcha

1. Sube el contenido al repositorio.
2. En GitHub, activa **Pages** con fuente **GitHub Actions**.
3. Lanza manualmente el workflow `Deploy static site to GitHub Pages`.
4. Lanza manualmente `Update deals data` para probar la regeneración del JSON.

## Siguientes pasos

- Sustituir `fetch_products()` por APIs reales de afiliación.
- Añadir más reglas para destacar mejores chollos.
- Incorporar páginas por categoría y SEO básico.
