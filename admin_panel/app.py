from __future__ import annotations

import os
from base64 import b64decode
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests
from flask import Flask, Response, render_template


GITHUB_API = "https://api.github.com"

app = Flask(__name__)


@dataclass
class WorkflowSummary:
    label: str
    file_name: str
    status: str
    conclusion: str
    updated_at: str
    html_url: str
    run_number: int
    anomaly: str


@dataclass
class Light:
    label: str
    level: str
    detail: str


WORKFLOWS = [
    ("Deploy Pages", "deploy-pages.yml"),
    ("Update Data", "update-data.yml"),
    ("SEO Mini Monitor", "seo-mini-monitor.yml"),
]


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def parse_iso_to_local(value: str) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value


def read_basic_auth(auth_header: str) -> tuple[str, str]:
    if not auth_header or not auth_header.startswith("Basic "):
        return "", ""
    try:
        encoded = auth_header.split(" ", 1)[1]
        decoded = b64decode(encoded).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return "", ""


def unauthorized() -> Response:
    return Response(
        "Autenticacion requerida",
        401,
        {"WWW-Authenticate": 'Basic realm="CholloBici Admin"'},
    )


def require_auth() -> Response | None:
    expected_user = env("ADMIN_USERNAME", "admin")
    expected_password = env("ADMIN_PASSWORD")
    if not expected_password:
        return Response("Falta ADMIN_PASSWORD en el entorno", 500)

    from flask import request

    username, password = read_basic_auth(request.headers.get("Authorization", ""))
    if username != expected_user or password != expected_password:
        return unauthorized()
    return None


def github_get(path: str) -> dict[str, Any]:
    token = env("GITHUB_TOKEN")
    owner = env("GITHUB_OWNER", "fberme84")
    repo = env("GITHUB_REPO", "chollobici")
    if not token:
        raise RuntimeError("Falta GITHUB_TOKEN en el entorno")

    url = f"{GITHUB_API}/repos/{owner}/{repo}{path}"
    resp = requests.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "chollobici-admin-panel",
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def github_get_file_json(path: str) -> dict[str, Any] | None:
    try:
        data = github_get(f"/contents/{path}")
    except Exception:
        return None

    if not isinstance(data, dict) or "content" not in data:
        return None
    content = str(data.get("content") or "").replace("\n", "")
    if not content:
        return None
    try:
        raw = b64decode(content).decode("utf-8")
        import json

        return json.loads(raw)
    except Exception:
        return None


def parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def build_lights(items: list[WorkflowSummary], metrics: dict[str, Any] | None) -> list[Light]:
    lights: list[Light] = []

    failing = [i.label for i in items if i.conclusion not in ("success", "-", "")]
    if failing:
        lights.append(Light("Workflows", "red", f"Error en: {', '.join(failing)}"))
    else:
        lights.append(Light("Workflows", "green", "Sin fallos en el ultimo run"))

    sitemap_urls = int(((metrics or {}).get("totals") or {}).get("sitemap_urls") or 0)
    if sitemap_urls < 25:
        lights.append(Light("Cobertura sitemap", "red", f"Solo {sitemap_urls} URLs"))
    elif sitemap_urls < 40:
        lights.append(Light("Cobertura sitemap", "yellow", f"{sitemap_urls} URLs (vigilancia)"))
    else:
        lights.append(Light("Cobertura sitemap", "green", f"{sitemap_urls} URLs"))

    generated_at = parse_iso(str((metrics or {}).get("generated_at") or ""))
    if not generated_at:
        lights.append(Light("Frescura datos", "red", "Sin timestamp de metricas"))
    else:
        age_hours = (datetime.now(UTC) - generated_at.astimezone(UTC)).total_seconds() / 3600
        if age_hours > 36:
            lights.append(Light("Frescura datos", "red", f"Ultima actualizacion hace {age_hours:.1f}h"))
        elif age_hours > 24:
            lights.append(Light("Frescura datos", "yellow", f"Ultima actualizacion hace {age_hours:.1f}h"))
        else:
            lights.append(Light("Frescura datos", "green", f"Ultima actualizacion hace {age_hours:.1f}h"))

    monitor = next((i for i in items if i.file_name == "seo-mini-monitor.yml"), None)
    if monitor and monitor.conclusion == "success":
        lights.append(Light("SEO monitor", "green", f"Run #{monitor.run_number} OK"))
    elif monitor and monitor.conclusion not in ("-", ""):
        lights.append(Light("SEO monitor", "red", f"Conclusion: {monitor.conclusion}"))
    else:
        lights.append(Light("SEO monitor", "yellow", "Aun sin ejecuciones suficientes"))

    return lights


def fetch_workflow_summary(label: str, file_name: str) -> WorkflowSummary:
    data = github_get(f"/actions/workflows/{file_name}/runs?per_page=1")
    runs = data.get("workflow_runs", [])
    if not runs:
        return WorkflowSummary(
            label=label,
            file_name=file_name,
            status="no-runs",
            conclusion="-",
            updated_at="-",
            html_url="",
            run_number=0,
            anomaly="",
        )

    run = runs[0]
    anomaly = ""
    run_id = run.get("id")
    conclusion = str(run.get("conclusion") or "-")
    if run_id and conclusion not in ("success", "-"):
        try:
            jobs = github_get(f"/actions/runs/{run_id}/jobs?per_page=1")
            total_jobs = int(jobs.get("total_count") or 0)
            if total_jobs == 0:
                anomaly = "Fallo sin jobs: posible error de sintaxis/expresion en el workflow"
        except Exception:
            # If jobs cannot be read, keep normal summary without hard-failing the dashboard.
            anomaly = ""

    return WorkflowSummary(
        label=label,
        file_name=file_name,
        status=str(run.get("status") or "-"),
        conclusion=conclusion,
        updated_at=parse_iso_to_local(str(run.get("updated_at") or "")),
        html_url=str(run.get("html_url") or ""),
        run_number=int(run.get("run_number") or 0),
        anomaly=anomaly,
    )


@app.get("/healthz")
def healthz() -> tuple[str, int]:
    return "ok", 200


@app.get("/")
def dashboard() -> Response | str:
    auth_error = require_auth()
    if auth_error:
        return auth_error

    try:
        items = [fetch_workflow_summary(label, file) for label, file in WORKFLOWS]
        has_errors = any(i.conclusion not in ("success", "-", "") for i in items)
        metrics = github_get_file_json("data/admin_metrics.json")
        lights = build_lights(items, metrics)
        return render_template(
            "dashboard.html",
            items=items,
            has_errors=has_errors,
            metrics=metrics,
            lights=lights,
        )
    except Exception as exc:
        return Response(f"Error cargando datos: {exc}", 500)


if __name__ == "__main__":
    port = int(env("PORT") or env("ADMIN_PORT", "8787"))
    app.run(host="0.0.0.0", port=port)
