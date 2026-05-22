# CholloBici Admin (MVP)

Panel privado con password para ver estado de workflows:
- Deploy Pages
- Update Data
- SEO Mini Monitor

## Variables de entorno

- `ADMIN_USERNAME` (opcional, por defecto `admin`)
- `ADMIN_PASSWORD` (obligatoria)
- `GITHUB_TOKEN` (obligatoria, token con acceso a Actions read)
- `GITHUB_OWNER` (opcional, por defecto `fberme84`)
- `GITHUB_REPO` (opcional, por defecto `chollobici`)
- `ADMIN_PORT` (opcional, por defecto `8787`)

## Ejecucion local

1. Instalar dependencias:

```bash
pip install -r requirements.txt
```

2. Exportar entorno (PowerShell):

```powershell
$env:ADMIN_USERNAME="admin"
$env:ADMIN_PASSWORD="pon-una-password-segura"
$env:GITHUB_TOKEN="ghp_xxx"
$env:GITHUB_OWNER="fberme84"
$env:GITHUB_REPO="chollobici"
```

3. Ejecutar:

```bash
python admin_panel/app.py
```

4. Abrir:

- http://localhost:8787

## Nota de seguridad

No poner este panel en GitHub Pages publico. Debe vivir en un servicio con backend (Render, Railway, Fly, etc.) o detras de un gateway privado.
