from __future__ import annotations

import argparse
import os
import sys

import requests


def build_message(workflow: str, run_url: str, repository: str, branch: str, event: str) -> str:
    return (
        "🚨 CholloBici workflow failed\n"
        f"- Workflow: {workflow}\n"
        f"- Repo: {repository}\n"
        f"- Branch: {branch}\n"
        f"- Event: {event}\n"
        f"- Run: {run_url}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--run-url", required=True)
    args = parser.parse_args()

    webhook = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not webhook:
        print("ALERT_WEBHOOK_URL is empty, skipping alert")
        return 0

    repository = os.getenv("GITHUB_REPOSITORY", "-")
    branch = os.getenv("GITHUB_REF_NAME", "-")
    event = os.getenv("GITHUB_EVENT_NAME", "-")

    content = build_message(args.workflow, args.run_url, repository, branch, event)
    payload = {"content": content}

    try:
        response = requests.post(webhook, json=payload, timeout=15)
        response.raise_for_status()
        print("Alert sent")
        return 0
    except Exception as exc:
        print(f"Failed to send alert: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
