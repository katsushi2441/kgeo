import base64
import json as jsonlib

from app import config, remote_store


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"ok": True, "result": {"sites": 1}}


def test_remote_store_uses_private_header(monkeypatch) -> None:
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(url=url, headers=headers, json=json, timeout=timeout)
        return FakeResponse()

    monkeypatch.setattr(config, "STORAGE_API_URL", "https://example.com/kgeo_store.php")
    monkeypatch.setattr(config, "STORAGE_API_TOKEN", "private-token")
    monkeypatch.setattr("app.remote_store.httpx.post", fake_post)

    result = remote_store.call("table_counts")

    assert result == {"sites": 1}
    assert captured["headers"]["X-KGeo-Storage-Token"] == "private-token"
    assert "Authorization" not in captured["headers"]
    # Heteml WAF(SiteGuard)対策で、本文はbase64エンベロープに包んで送る。
    assert captured["json"]["action"] == "call_b64"
    decoded = jsonlib.loads(base64.b64decode(captured["json"]["payload"]["data"]).decode("utf-8"))
    assert decoded == {"action": "table_counts", "payload": {}}


def test_remote_store_envelope_hides_waf_triggering_body(monkeypatch) -> None:
    """監査結果のHTML断片やSQL様の文字列が、送信本文にそのまま現れないこと。"""
    captured: dict = {}

    def fake_post(url, *, headers, json, timeout):
        captured.update(json=json)
        return FakeResponse()

    monkeypatch.setattr(config, "STORAGE_API_URL", "https://example.com/kgeo_store.php")
    monkeypatch.setattr(config, "STORAGE_API_TOKEN", "private-token")
    monkeypatch.setattr("app.remote_store.httpx.post", fake_post)

    payload = {"result_json": '<a href="/x">link</a> SELECT * FROM users WHERE id=1--'}
    remote_store.call("save_audit", payload)

    wire = jsonlib.dumps(captured["json"], ensure_ascii=False)
    assert "SELECT * FROM" not in wire
    assert "<a href=" not in wire
    decoded = jsonlib.loads(base64.b64decode(captured["json"]["payload"]["data"]).decode("utf-8"))
    assert decoded["payload"] == payload
