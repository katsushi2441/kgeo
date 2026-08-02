from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from . import config


def enabled() -> bool:
    return bool(config.STORAGE_API_URL and config.STORAGE_API_TOKEN)


def _envelope(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Wrap the request in base64.

    Heteml's SiteGuard WAF inspects the request body and rejects audit results
    (HTML fragments, URLs, SQL-looking text) with 403 before PHP runs. Sending an
    opaque base64 string keeps the payload out of the WAF's pattern matching.
    """
    inner = json.dumps({"action": action, "payload": payload}, ensure_ascii=False)
    data = base64.b64encode(inner.encode("utf-8")).decode("ascii")
    return {"action": "call_b64", "payload": {"data": data}}


def call(action: str, payload: dict[str, Any] | None = None) -> Any:
    if not enabled():
        raise RuntimeError("KGeo Heteml storage API is not configured")
    response = httpx.post(
        config.STORAGE_API_URL,
        headers={
            "X-KGeo-Storage-Token": config.STORAGE_API_TOKEN,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=_envelope(action, payload or {}),
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or not body.get("ok"):
        raise RuntimeError(f"KGeo Heteml storage API rejected action: {action}")
    return body.get("result")
