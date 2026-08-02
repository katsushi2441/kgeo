import pytest

from app.audit_service import japanese_recommendations, validate_target
from app.monitor_service import analyze_response


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://localhost/private",
        "http://192.168.0.11/",
        "ftp://example.com/file",
        "https://user:password@example.com/",
    ],
)
def test_private_or_unsupported_targets_are_rejected(url: str) -> None:
    with pytest.raises(ValueError):
        validate_target(url)


def test_monitor_response_analysis() -> None:
    result = analyze_response(
        "候補はKurage GEOです。参照: https://example.jp/geo ほか https://other.jp/a",
        "Kurage GEO",
        "https://example.jp",
    )
    assert result["brand_mentioned"] is True
    assert result["domain_cited"] is True
    assert result["citation_rank"] == 1
    assert len(result["cited_urls"]) == 2


def test_japanese_actions_are_based_on_missing_facts() -> None:
    actions = japanese_recommendations(
        {
            "robots": {"citation_bots_ok": False},
            "llms": {"found": False},
            "schema": {},
            "meta": {},
            "content": {"word_count": 40},
            "signals": {},
            "brand_entity": {"brand_name_consistent": False},
            "ai_discovery": {},
        }
    )
    assert any("robots.txt" in item for item in actions)
    assert any("/llms.txt" in item for item in actions)
    assert any("ブランド名" in item for item in actions)
