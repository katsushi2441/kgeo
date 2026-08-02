from pathlib import Path

from fastapi.testclient import TestClient

from app import config, db
from app.main import app

HEADERS = {"X-KGeo-Token": "test-secret", "X-KGeo-User": "alice"}


def fake_audit(url: str) -> dict:
    return {
        "url": url,
        "score": 63,
        "band": "foundation",
        "http_status": 200,
        "error": None,
        "score_breakdown": {
            "robots": 10,
            "llms": 0,
            "schema": 12,
            "meta": 12,
            "content": 10,
            "signals": 5,
            "ai_discovery": 4,
            "brand_entity": 10,
        },
        "robots": {"citation_bots_ok": True},
        "llms": {"found": False},
        "schema": {"has_organization": True, "has_website": True},
        "meta": {"has_description": True, "has_canonical": True},
        "content": {"has_h1": True, "word_count": 500},
        "signals": {"has_freshness": True},
        "brand_entity": {"brand_name_consistent": True},
        "ai_discovery": {"endpoints_found": 1},
        "recommendations": [],
    }


def configure_test(tmp_path: Path, monkeypatch) -> None:
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", test_db)
    monkeypatch.setattr(db, "DB_PATH", test_db)
    monkeypatch.setattr(config, "INTERNAL_TOKEN", "test-secret")
    monkeypatch.setattr(config, "FREE_AUDITS_PER_MONTH", 3)
    monkeypatch.setattr(config, "FREE_MONITOR_RUNS_PER_MONTH", 5)
    monkeypatch.setattr("app.main.audit_service.validate_target", lambda url: url)


def create_site(client: TestClient, headers: dict = HEADERS) -> dict:
    response = client.post(
        "/api/sites",
        json={
            "name": "Kurage GEO",
            "url": "https://example.com",
            "brand_name": "Kurage",
            "competitors": ["Competitor A"],
        },
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def test_site_audit_lifecycle_and_owner_isolation(tmp_path: Path, monkeypatch) -> None:
    configure_test(tmp_path, monkeypatch)
    monkeypatch.setattr("app.main.audit_service.run_audit", fake_audit)
    with TestClient(app) as client:
        assert client.get("/api/sites").status_code == 401
        site = create_site(client)

        audit = client.post(f"/api/sites/{site['id']}/audits", headers=HEADERS)
        assert audit.status_code == 200
        body = audit.json()
        assert body["score"] == 63
        assert body["recommendations_ja"][0].startswith("サイトの要点")

        sites = client.get("/api/sites", headers=HEADERS).json()
        assert sites[0]["latest_score"] == 63
        assert client.get(
            f"/api/sites/{site['id']}",
            headers={**HEADERS, "X-KGeo-User": "bob"},
        ).status_code == 404
        assert client.get(
            "/api/sites", headers={**HEADERS, "X-KGeo-User": "bob"}
        ).json() == []


def test_audit_billing_is_delegated_to_public_gateway(tmp_path: Path, monkeypatch) -> None:
    configure_test(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "FREE_AUDITS_PER_MONTH", 1)
    monkeypatch.setattr("app.main.audit_service.run_audit", fake_audit)
    with TestClient(app) as client:
        site = create_site(client)
        assert client.post(f"/api/sites/{site['id']}/audits", headers=HEADERS).status_code == 200
        second = client.post(f"/api/sites/{site['id']}/audits", headers=HEADERS)
        assert second.status_code == 200
        usage = client.get("/api/usage", headers=HEADERS).json()
        assert usage["audits_limit"] is None


def test_admin_name_is_normalized_for_plan(tmp_path: Path, monkeypatch) -> None:
    configure_test(tmp_path, monkeypatch)
    monkeypatch.setattr(config, "ADMIN_USERS", {"xb_bittensor"})
    with TestClient(app) as client:
        usage = client.get(
            "/api/usage",
            headers={**HEADERS, "X-KGeo-User": "@XB_BITTENSOR"},
        ).json()
        assert usage["plan"] == "admin"
        assert usage["audits_limit"] is None
        assert usage["monitor_runs_limit"] is None


def test_prompt_monitoring(tmp_path: Path, monkeypatch) -> None:
    configure_test(tmp_path, monkeypatch)

    async def fake_prompt(
        prompt: str,
        brand_name: str,
        site_url: str,
        owner: str,
        brand_aliases: list[str] | None = None,
    ) -> dict:
        assert prompt == "日本語のGEOサービスは？"
        assert owner == "alice"
        assert brand_aliases == ["Kurage GEO"]
        return {
            "provider": "mock",
            "model": "mock-search",
            "evaluation_mode": "grounded-site-simulation",
            "analysis": {
                "answerability_score": 88,
                "supported_points": ["日本語対応"],
                "missing_information": [],
                "improvement_suggestions": ["料金を追加"],
            },
            "brand_mentioned": True,
            "domain_cited": True,
            "citation_rank": 1,
            "cited_urls": ["https://example.com/guide"],
            "response_text": "Kurage: https://example.com/guide",
            "error": None,
        }

    monkeypatch.setattr("app.main.monitor_service.run_prompt", fake_prompt)
    with TestClient(app) as client:
        site = create_site(client)
        created = client.post(
            f"/api/sites/{site['id']}/prompts",
            json={"prompt": "日本語のGEOサービスは？"},
            headers=HEADERS,
        )
        assert created.status_code == 200
        prompt = created.json()
        run = client.post(f"/api/prompts/{prompt['id']}/runs", headers=HEADERS)
        assert run.status_code == 200
        assert run.json()["brand_mentioned"] is True
        assert run.json()["domain_cited"] is True
        assert run.json()["evaluation_mode"] == "grounded-site-simulation"
        assert run.json()["analysis"]["answerability_score"] == 88
        history = client.get(f"/api/prompts/{prompt['id']}/runs", headers=HEADERS).json()
        assert history[0]["analysis"]["improvement_suggestions"] == ["料金を追加"]
        usage = client.get("/api/usage", headers=HEADERS).json()
        assert usage["monitor_runs_used"] == 1


def test_index_is_available_without_internal_headers(tmp_path: Path, monkeypatch) -> None:
    configure_test(tmp_path, monkeypatch)
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "Kurage GEO" in response.text
