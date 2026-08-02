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
    assert captured["json"] == {"action": "table_counts", "payload": {}}
