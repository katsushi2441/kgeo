"""Cloud Run database smoke test; requires KGEO_DATABASE_URL."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

if not os.getenv("KGEO_DATABASE_URL", "").startswith("postgresql://"):
    raise SystemExit("KGEO_DATABASE_URL=postgresql://... is required")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import app  # noqa: E402


def fake_audit(url: str) -> dict:
    return {
        "url": url,
        "score": 71,
        "band": "good",
        "http_status": 200,
        "error": None,
        "score_breakdown": {},
        "robots": {"citation_bots_ok": True},
        "llms": {"found": True},
        "schema": {},
        "meta": {},
        "content": {"word_count": 500},
        "signals": {},
        "brand_entity": {},
        "ai_discovery": {},
        "recommendations": [],
    }


owner = f"postgres-smoke-{uuid.uuid4().hex[:8]}"
headers = {"X-KGeo-Token": "postgres-smoke-token", "X-KGeo-User": owner}
with patch("app.audit_service.validate_target", lambda url: url), patch(
    "app.main.audit_service.run_audit", fake_audit
):
    with TestClient(app) as client:
        created = client.post(
            "/api/sites",
            headers=headers,
            json={
                "name": "PostgreSQL smoke",
                "url": "https://example.com",
                "brand_name": "KGeo",
                "competitors": [],
            },
        )
        assert created.status_code == 200, created.text
        site = created.json()
        audit = client.post(f"/api/sites/{site['id']}/audits", headers=headers)
        assert audit.status_code == 200, audit.text
        assert audit.json()["score"] == 71
        listed = client.get("/api/sites", headers=headers)
        assert listed.status_code == 200
        assert listed.json()[0]["latest_score"] == 71

print(f"PostgreSQL smoke passed for owner {owner}")
