from __future__ import annotations

import os
from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime
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
        )

    run = runs[0]
    return WorkflowSummary(
        label=label,
        file_name=file_name,
        status=str(run.get("status") or "-"),
        conclusion=str(run.get("conclusion") or "-"),
        updated_at=parse_iso_to_local(str(run.get("updated_at") or "")),
        html_url=str(run.get("html_url") or ""),
        run_number=int(run.get("run_number") or 0),
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
        return render_template("dashboard.html", items=items, has_errors=has_errors)
    except Exception as exc:
        return Response(f"Error cargando datos: {exc}", 500)


if __name__ == "__main__":
    port = int(env("ADMIN_PORT", "8787"))
    app.run(host="0.0.0.0", port=port)
