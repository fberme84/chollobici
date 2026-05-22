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

## Despliegue en Render (simple)

Este repo ya incluye `render.yaml` para crear el servicio web automaticamente.

### Lo que ya esta preparado

- runtime Python
- instalacion de dependencias con `requirements.txt`
- arranque con `gunicorn admin_panel.app:app`
- variables base (`GITHUB_OWNER`, `GITHUB_REPO`, `ADMIN_USERNAME`)

### Lo unico que tienes que poner tu en Render

- `ADMIN_PASSWORD`
- `GITHUB_TOKEN` (token de GitHub con permiso de lectura de Actions)

### Pasos en Render

1. `New` -> `Blueprint`.
2. Selecciona el repo `fberme84/chollobici`.
3. Render detectara `render.yaml` y propondra `chollobici-admin`.
4. En variables, define `ADMIN_PASSWORD` y `GITHUB_TOKEN`.
5. Crea el servicio y abre la URL generada.

Cuando abra la URL, pedira usuario y password (Basic Auth).
