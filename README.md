# Detector de Chollos Ciclistas

MVP estático para GitHub Pages con actualización automática de datos mediante GitHub Actions.

## Estructura

- `index.html`, `app.js`, `styles.css`: frontal estático.
- `data/amazon_products.json`: catálogo base de productos Amazon.
- `data/generated_deals.json`: ofertas visibles en la web, generado automáticamente para el despliegue.
- `data/history.json`: histórico mínimo de precios.
- `scripts/update_deals.py`: regeneración automática de datos y aplicación del tag de afiliado.
- `.github/workflows/update-data.yml`: actualiza solo el histórico en el repo.
- `.github/workflows/deploy-pages.yml`: genera `generated_deals.json` en el despliegue y publica en GitHub Pages.

## Secret necesario

En GitHub, añade este secret del repositorio en `Settings > Secrets and variables > Actions`:

- `AMAZON_PARTNER_TAG` = `chollobici0a-21`

## Puesta en marcha

1. Sustituye tu proyecto por este contenido.
2. Borra del repo el archivo antiguo `data/deals.json` si todavía existe y haz commit.
3. En GitHub, activa **Pages** con fuente **GitHub Actions**.
4. Añade el secret `AMAZON_PARTNER_TAG`.
5. Lanza manualmente `Update deals data`.
6. Lanza manualmente `Deploy static site to GitHub Pages`.

## Cómo evita conflictos esta versión

- `data/generated_deals.json` ya no se guarda en Git.
- GitHub Actions solo hace commit de `data/history.json`.
- La web pública se despliega generando `generated_deals.json` durante el workflow de Pages.

Así evitas conflictos en tus commits manuales y la web sigue mostrando ofertas actualizadas.

## Nota legal sugerida

Incluye en la web un aviso de afiliación, por ejemplo:

> Como afiliado de Amazon, obtengo ingresos por las compras adscritas.


## Nota sobre generated_deals.json
Este archivo se versiona en el repositorio y lo actualiza el workflow `Update deals data`. No lo edites manualmente.


## Preparado para actualización diaria de precios

La actualización diaria ya está preparada en dos pasos:

1. `scripts/refresh_amazon_products.py`
   - normaliza URLs de Amazon
   - deja el catálogo listo para conectarlo a la API de Amazon
   - actualiza `last_checked`

2. `scripts/update_deals.py`
   - compara precios con `history.json`
   - regenera `generated_deals.json`
   - aplica el tag de afiliado

### Secrets previstos para cuando actives la API de Amazon

Añade estos secrets en GitHub Actions cuando te aprueben / configures la API:

- `AMAZON_PAAPI_ACCESS_KEY`
- `AMAZON_PAAPI_SECRET_KEY`
- `AMAZON_PAAPI_PARTNER_TAG`
- `AMAZON_PAAPI_REGION`
- `AMAZON_PAAPI_HOST`

Ejemplo habitual para España:
- `AMAZON_PAAPI_REGION` = `eu-west-1`
- `AMAZON_PAAPI_HOST` = `webservices.amazon.es`

### Estado actual de v6.7

Esta versión deja todo preparado, pero el script de refresco aún va en modo plantilla:
- no consulta Amazon todavía
- no inventa precios
- deja la estructura lista para que conectes la API en cuanto puedas
