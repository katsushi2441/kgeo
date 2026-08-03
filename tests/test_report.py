"""監査レポート(Markdown / PDF)の生成テスト。"""

from __future__ import annotations

import pytest

from app import report

ROW = {
    "id": "abc123def456",
    "site_id": "0123456789ab",
    "score": 47,
    "band": "foundation",
    "http_status": 200,
    "error": None,
    "score_breakdown": {"robots": 15, "llms": 0, "negative_penalty": -3},
    "recommendations_ja": ["サイトの要点を整理した /llms.txt を設置してください。"],
    "created_at": "2026-08-03T05:59:26.701791+00:00",
    "result": {
        "url": "https://example.com",
        "robots": {"found": True, "bots_allowed": ["GPTBot", "ClaudeBot"]},
        "llms": {"found": False},
        "schema": {"found_types": ["WebSite"]},
        "meta": {"title_text": "例のサイト｜日本語タイトル"},
        "aeo": {
            "checked": True,
            "language": "ja",
            "analyzed_as": "ja",
            "score": 45,
            "band": "foundation",
            "notice": "決定論的なAEO準備度です。",
            "metrics": {"answer_first": {"score": 47}, "claim_risk": {"score": 40}},
        },
    },
}


def test_markdown_contains_core_sections():
    md = report.build_markdown(ROW, "ja")
    assert "# Kurage GEO 監査レポート" in md
    assert "https://example.com" in md
    assert "47 / 100" in md
    assert "AIクローラー" in md  # 画面と同じカテゴリ名
    assert "/llms.txt" in md  # 推奨対応が入る
    assert "GPTBot, ClaudeBot" in md


def test_markdown_shows_jst_not_utc():
    """保存はUTC。レポートは必ずJSTで表示する(05:59Z = 14:59 JST)。"""
    md = report.build_markdown(ROW, "ja")
    assert "2026-08-03 14:59 JST" in md
    assert "05:59" not in md


def test_markdown_english_switches_labels():
    md = report.build_markdown(ROW, "en")
    assert "# Kurage GEO Audit Report" in md
    assert "AI crawlers" in md
    assert "AIクローラー" not in md


def test_aeo_score_is_not_labelled_as_geo_score():
    """AEO欄にGEOスコアのラベルを出すと別指標と誤読されるため分ける。"""
    md = report.build_markdown(ROW, "ja")
    assert "**AEOスコア**: 45 / 100" in md


def test_markdown_handles_audit_without_aeo():
    row = dict(ROW, result=dict(ROW["result"], aeo={}, japanese_aeo={}))
    md = report.build_markdown(row, "ja")
    assert "再監査すると追加されます" in md


def test_filename_stem_is_safe_and_identifiable():
    stem = report.filename_stem(ROW)
    assert stem == "kgeo-example.com-2026-08-03-1459"
    assert "/" not in stem and " " not in stem


def test_pdf_is_generated_with_embedded_font():
    """内蔵CIDフォントは埋め込まれず英数字が豆腐になるため、埋め込みを確認する。"""
    try:
        report._font_path()
    except report.ReportFontMissing:
        pytest.skip("日本語フォント未導入の環境")
    pdf = report.build_pdf(ROW, "ja")
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 5000
    # サブセット埋め込みフォントは FontFile2 を持つ。無ければ埋め込まれていない。
    assert b"FontFile2" in pdf


def test_missing_font_fails_loudly(monkeypatch):
    """フォントが無いまま黙って読めないPDFを出さない。

    build_pdf 経由では検証できない。reportlab の pdfmetrics はプロセス内で
    フォント登録をキャッシュするため、同一プロセスで一度でも登録に成功すると
    以後 _font_path() を呼ばないため。守るべき境界は解決処理そのものなので
    そこを直接検証する。
    """
    monkeypatch.setattr(report, "FONT_CANDIDATES", ())
    monkeypatch.setenv("KGEO_PDF_FONT", "/nonexistent/font.ttf")
    with pytest.raises(report.ReportFontMissing):
        report._font_path()


def test_font_env_override_wins(monkeypatch, tmp_path):
    font = tmp_path / "custom.ttf"
    font.write_bytes(b"dummy")
    monkeypatch.setenv("KGEO_PDF_FONT", str(font))
    assert report._font_path() == str(font)
