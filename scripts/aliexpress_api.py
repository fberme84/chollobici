import os
import time
import json
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests


class AliExpressApiError(Exception):
    pass


DEFAULT_ENDPOINT = (os.getenv("ALIEXPRESS_API_URL") or "https://api-sg.aliexpress.com/sync").strip()


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if value is None:
        return ""
    return str(value)


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _sign(params: Dict[str, Any], app_secret: str) -> str:
    items = sorted((k, _stringify(v)) for k, v in params.items() if k != "sign" and v is not None)
    sign_str = app_secret + "".join(f"{k}{v}" for k, v in items) + app_secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def call_api(method: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Dict[str, Any]:
    payload = payload or {}

    app_key = (os.getenv("ALIEXPRESS_APP_KEY") or "").strip()
    app_secret = (os.getenv("ALIEXPRESS_APP_SECRET") or "").strip()
    endpoint = (os.getenv("ALIEXPRESS_API_URL") or "https://api-sg.aliexpress.com/sync").strip()

    if not endpoint:
        endpoint = "https://api-sg.aliexpress.com/sync"

    if not app_key or not app_secret:
        raise AliExpressApiError("Faltan ALIEXPRESS_APP_KEY o ALIEXPRESS_APP_SECRET")

    params: Dict[str, Any] = {
        "app_key": app_key,
        "method": method,
        "format": "json",
        "sign_method": "md5",
        "timestamp": _timestamp(),
        "v": "2.0",
        **payload,
    }

    params["sign"] = _sign(params, app_secret)

    response = requests.get(
        endpoint,
        params={k: _stringify(v) for k, v in params.items()},
        timeout=timeout,
    )
    response.raise_for_status()

    try:
        data = response.json()
    except Exception as exc:
        raise AliExpressApiError(f"Respuesta no JSON de AliExpress: {response.text[:500]}") from exc

    error_keys = [
        "error_response",
        "aliexpress_affiliate_product_query_response_error",
        "errorMessage",
        "error_message",
        "msg",
        "sub_msg",
    ]
    for key in error_keys:
        if key in data:
            raise AliExpressApiError(f"ERROR API: {data[key]}")

    return data


def _extract_product_list(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidate_paths = [
        ["aliexpress_affiliate_product_query_response", "resp_result", "result", "products", "product"],
        ["aliexpress_affiliate_product_query_response", "resp_result", "result", "products"],
        ["aliexpress_affiliate_product_query_response", "result", "products", "product"],
        ["aliexpress_affiliate_product_query_response", "result", "products"],
        ["result", "products", "product"],
        ["result", "products"],
        ["products", "product"],
        ["products"],
    ]

    for path in candidate_paths:
        cur: Any = data
        ok = True
        for part in path:
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and isinstance(cur, list):
            return cur

    def _walk(obj: Any) -> Optional[List[Dict[str, Any]]]:
        if isinstance(obj, list) and obj and isinstance(obj[0], dict) and (
            "product_id" in obj[0] or "product_title" in obj[0]
        ):
            return obj
        if isinstance(obj, dict):
            for v in obj.values():
                found = _walk(v)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for v in obj:
                found = _walk(v)
                if found is not None:
                    return found
        return None

    return _walk(data) or []


def _extract_promotion_links(data: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}

    def _walk(obj: Any) -> None:
        if isinstance(obj, dict):
            if "promotion_link" in obj and "source_value" in obj:
                out[str(obj["source_value"])] = str(obj["promotion_link"])
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)

    _walk(data)
    return out


def product_query(
    keywords: str,
    page_no: int = 1,
    page_size: int = 20,
    target_currency: str = "EUR",
    target_language: str = "ES",
    ship_to_country: str = "ES",
    sort: str = "LAST_VOLUME_DESC",
) -> List[Dict[str, Any]]:
    payload = {
        "keywords": keywords,
        "page_no": page_no,
        "page_size": page_size,
        "target_currency": target_currency,
        "target_language": target_language,
        "ship_to_country": ship_to_country,
        "sort": sort,
    }
    data = call_api("aliexpress.affiliate.product.query", payload)
    return _extract_product_list(data)


def generate_affiliate_links(urls: List[str], tracking_id: Optional[str] = None) -> Dict[str, str]:
    tracking_id = (tracking_id or os.getenv("ALIEXPRESS_TRACKING_ID") or "").strip()
    if not tracking_id:
        return {}

    payload = {
        "promotion_link_type": 0,
        "source_values": ",".join(urls),
        "tracking_id": tracking_id,
    }

    data = call_api("aliexpress.affiliate.link.generate", payload)
    return _extract_promotion_links(data)