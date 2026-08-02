from __future__ import annotations

from typing import Any

import httpx

from . import config


def enabled() -> bool:
    return bool(config.STORAGE_API_URL and config.STORAGE_API_TOKEN)


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
        json={"action": action, "payload": payload or {}},
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict) or not body.get("ok"):
        raise RuntimeError(f"KGeo Heteml storage API rejected action: {action}")
    return body.get("result")
