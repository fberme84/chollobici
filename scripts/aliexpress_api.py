from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

DEFAULT_ENDPOINT = os.getenv("ALIEXPRESS_API_URL", "https://api-sg.aliexpress.com/sync").strip()


class AliExpressApiError(RuntimeError):
    pass


def _gmt8_timestamp() -> str:
    gmt8 = timezone(timedelta(hours=8))
    return datetime.now(gmt8).strftime("%Y-%m-%d %H:%M:%S")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return _json_dumps(value)
    return str(value)


def sign_params(params: dict[str, Any], app_secret: str) -> str:
    items = sorted((key, _stringify(value)) for key, value in params.items() if value is not None and key != "sign")
    raw = app_secret + "".join(f"{key}{value}" for key, value in items) + app_secret
    return hashlib.md5(raw.encode("utf-8")).hexdigest().upper()


def call_api(method: str, payload: dict[str, Any] | None = None, *, timeout: int = 45) -> dict[str, Any]:
    app_key = os.getenv("ALIEXPRESS_APP_KEY", "").strip()
    app_secret = os.getenv("ALIEXPRESS_APP_SECRET", "").strip()
    endpoint = os.getenv("ALIEXPRESS_API_URL", DEFAULT_ENDPOINT).strip() or DEFAULT_ENDPOINT

    if not app_key or not app_secret:
        raise AliExpressApiError("Faltan ALIEXPRESS_APP_KEY o ALIEXPRESS_APP_SECRET")

    params: dict[str, Any] = {
        "method": method,
        "app_key": app_key,
        "timestamp": _gmt8_timestamp(),
        "format": "json",
        "v": "2.0",
        "sign_method": "md5",
        "simplify": "true",
    }
    if payload:
        params.update(payload)

    params["sign"] = sign_params(params, app_secret)

    response = requests.get(endpoint, params={k: _stringify(v) for k, v in params.items()}, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    error = data.get("error_response") if isinstance(data, dict) else None
    if error:
        message = error.get("msg") or error.get("sub_msg") or "Error desconocido"
        code = error.get("code") or error.get("sub_code") or "unknown"
        raise AliExpressApiError(f"{code}: {message}")

    return data


def _find_first_list(node: Any, candidate_keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        for key in candidate_keys:
            value = node.get(key)
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
        for value in node.values():
            found = _find_first_list(value, candidate_keys)
            if found:
                return found
    elif isinstance(node, list):
        if node and isinstance(node[0], dict):
            return node
        for value in node:
            found = _find_first_list(value, candidate_keys)
            if found:
                return found
    return []


def _find_first_dict(node: Any, candidate_keys: tuple[str, ...]) -> dict[str, Any]:
    if isinstance(node, dict):
        for key in candidate_keys:
            value = node.get(key)
            if isinstance(value, dict):
                return value
        for value in node.values():
            found = _find_first_dict(value, candidate_keys)
            if found:
                return found
    elif isinstance(node, list):
        for value in node:
            found = _find_first_dict(value, candidate_keys)
            if found:
                return found
    return {}


def product_query(*, keywords: str, page_no: int = 1, page_size: int = 20, tracking_id: str = "", target_currency: str = "EUR", target_language: str = "ES", ship_to_country: str = "ES", sort: str = "LAST_VOLUME_DESC") -> list[dict[str, Any]]:
    payload = {
        "keywords": keywords,
        "page_no": page_no,
        "page_size": page_size,
        "target_currency": target_currency,
        "target_language": target_language,
        "ship_to_country": ship_to_country,
        "sort": sort,
    }
    if tracking_id:
        payload["tracking_id"] = tracking_id

    data = call_api("aliexpress.affiliate.product.query", payload)
    return _find_first_list(data, ("products", "resp_result", "promotion_product", "promotion_products", "products_list", "records"))


def product_details(source_values: list[str], *, tracking_id: str = "", target_currency: str = "EUR", target_language: str = "ES", ship_to_country: str = "ES") -> list[dict[str, Any]]:
    payload = {
        "source_values": ",".join(source_values),
        "target_currency": target_currency,
        "target_language": target_language,
        "ship_to_country": ship_to_country,
    }
    if tracking_id:
        payload["tracking_id"] = tracking_id

    data = call_api("aliexpress.affiliate.productdetail.get", payload)
    return _find_first_list(data, ("products", "resp_result", "promotion_product", "promotion_products", "products_list", "records"))


def generate_affiliate_links(urls: list[str], *, tracking_id: str, promotion_link_type: int = 0) -> dict[str, str]:
    if not tracking_id:
        raise AliExpressApiError("Falta ALIEXPRESS_TRACKING_ID")

    payload = {
        "source_values": ",".join(urls),
        "tracking_id": tracking_id,
        "promotion_link_type": promotion_link_type,
    }
    data = call_api("aliexpress.affiliate.link.generate", payload)
    items = _find_first_list(data, ("promotion_links", "resp_result", "promotion_link", "links", "records"))
    mapping: dict[str, str] = {}
    for item in items:
        original = item.get("source_value") or item.get("url") or item.get("sourceUrl") or item.get("promotion_link")
        affiliate = item.get("promotion_link") or item.get("promotionUrl") or item.get("short_link") or item.get("shortUrl")
        if original and affiliate:
            mapping[str(original)] = str(affiliate)
    return mapping
