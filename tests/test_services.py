import pytest

from app import config
from app.audit_service import japanese_recommendations, validate_target
from app.japanese_aeo import analyze_japanese_aeo
from app.monitor_service import _parse_evaluation, analyze_response, configured, provider_for


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


def test_llm_provider_is_selected_by_owner(monkeypatch) -> None:
    monkeypatch.setattr(config, "ADMIN_USERS", {"xb_bittensor"})
    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", "test-key")
    assert provider_for("@XB_BITTENSOR") == "ollama"
    assert provider_for("alice") == "deepseek"
    assert configured("xb_bittensor") is True
    assert configured("alice") is True


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


def test_japanese_aeo_detects_japanese_answers_and_intents() -> None:
    html = """
    <html lang="ja"><body><main>
      <h1>GEO対策サービス</h1>
      <h2>GEOとは？</h2>
      <p>GEOとは、生成AIの回答で企業情報を引用されやすくする施策を指します。</p>
      <h2>どのように改善しますか？</h2>
      <p>サイト構造、根拠、著者情報、よくある質問を調査して改善します。</p>
      <h2>料金はいくらですか？</h2>
      <p>料金は月額5万円です。無料相談から申し込めます。</p>
      <h2>他社との違いは？</h2>
      <p>比較表と調査結果を示し、選び方を具体的に説明します。</p>
      <p>2026年の自社調査では80％が改善しました。出典は調査報告書です。</p>
      <a href="https://example.org/report">調査報告書</a>
    </main></body></html>
    """
    result = analyze_japanese_aeo(html)
    assert result["checked"] is True
    assert result["language"] == "ja"
    assert result["metrics"]["answer_first"]["found"] == 4
    assert result["metrics"]["definitions"]["found"] >= 1
    assert result["metrics"]["question_answers"]["questions"] == 4
    assert set(result["metrics"]["intent_coverage"]["found"]) >= {
        "informational",
        "transactional",
        "commercial",
    }
    assert result["metrics"]["evidence"]["score"] > 0


def test_japanese_aeo_flags_unsupported_absolute_claims() -> None:
    result = analyze_japanese_aeo(
        "<html lang='ja'><body><main><h1>製品</h1><h2>効果</h2>"
        "<p>誰でも必ず100％成功する唯一のサービスです。</p></main></body></html>"
    )
    assert result["metrics"]["claim_risk"]["score"] > 0
    assert result["metrics"]["claim_risk"]["unsourced_statistics"] >= 1
    assert any("断定" in item for item in result["recommendations"])


def test_grounded_llm_json_is_parsed() -> None:
    answer, analysis = _parse_evaluation(
        """```json
        {"answer":"Kurage GEOは日本語AEOを診断します。", "answerability_score":82,
        "supported_points":["日本語AEO診断"], "missing_information":["料金"],
        "improvement_suggestions":["料金表を追加"]}
        ```""",
        "https://example.jp",
        3456,
    )
    assert answer.startswith("Kurage GEO")
    assert analysis["answerability_score"] == 82
    assert analysis["source_content_chars"] == 3456
    assert analysis["structured_response"] is True


def test_brand_matching_normalizes_width_and_spaces() -> None:
    result = analyze_response("Ｋｕｒａｇｅ　ＧＥＯを利用できます。", "Kurage GEO", "https://example.jp")
    assert result["brand_mentioned"] is True


def test_brand_matching_accepts_japanese_site_name_alias() -> None:
    result = analyze_response(
        "株式会社エクスブリッジが提供しています。",
        "exbridge",
        "https://exbridge.jp",
        ["株式会社エクスブリッジ"],
    )
    assert result["brand_mentioned"] is True
