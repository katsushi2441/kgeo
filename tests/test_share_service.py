"""GEO監査結果のX投稿文のテスト。

投稿は利用者の名前で出るものなので、事実と違う数字を書いてはいけない。
280字を超えて切れることも許されない(途中で切れた投稿がそのまま出る)。
"""

from __future__ import annotations

import json
from urllib.parse import unquote

from app import share_service

SITE = {"name": "Kurage GEO", "url": "https://example.com/"}


def audit(score, breakdown, band="developing"):
    return {"score": score, "band": band, "score_breakdown": breakdown}


class TestSingleAudit:
    """1回だけなら比較できないので、現状の点数を出す。"""

    def test_reports_current_score(self):
        out = share_service.build_text(SITE, [audit(47, {"llms": 0})])
        assert out["compared"] is False
        assert "47/100" in out["text"]
        assert "→" not in out["text"].split("診断:")[0].replace("Kurage GEO", "")

    def test_band_is_japanese(self):
        out = share_service.build_text(SITE, [audit(47, {}, band="foundation")])
        assert "土台づくり" in out["text"]


class TestComparison:
    """2回以上で最初と最新を比較する。"""

    def test_shows_first_to_latest(self):
        audits = [audit(78, {"llms": 10}), audit(47, {"llms": 0})]   # 新しい順
        out = share_service.build_text(SITE, audits)
        assert out["compared"] is True
        assert "47 → 78/100" in out["text"]
        assert "+31" in out["text"]

    def test_uses_oldest_as_baseline_not_previous(self):
        """3回あるとき、基準は「前回」ではなく「最初」。"""
        audits = [audit(78, {}), audit(60, {}), audit(47, {})]
        out = share_service.build_text(SITE, audits)
        assert "47 → 78/100" in out["text"]
        assert out["audit_count"] == 3
        assert "計3回" in out["text"]

    def test_category_lines_use_japanese_labels(self):
        audits = [audit(78, {"llms": 10, "schema": 8}), audit(47, {"llms": 0, "schema": 2})]
        out = share_service.build_text(SITE, audits)
        assert "llms.txt 0 → 10（+10）" in out["text"]
        assert "構造化データ 2 → 8（+6）" in out["text"]

    def test_unchanged_categories_are_omitted(self):
        """動いていない項目を並べても意味がない。"""
        audits = [audit(50, {"llms": 5, "robots": 9}), audit(47, {"llms": 0, "robots": 9})]
        out = share_service.build_text(SITE, audits)
        assert "llms.txt" in out["text"]
        assert "AIクローラー許可" not in out["text"]

    def test_score_drop_is_reported_honestly(self):
        """下がったときに隠さない。捏造しないのが前提。"""
        audits = [audit(40, {"llms": 0}), audit(60, {"llms": 10})]
        out = share_service.build_text(SITE, audits)
        assert "60 → 40/100" in out["text"]
        assert "-20" in out["text"]

    def test_only_primary_categories_and_capped(self):
        """全8項目は読まれない。主要項目の上位だけに絞る。"""
        old = {"llms": 0, "schema": 0, "robots": 0, "content": 0, "meta": 0, "signals": 0}
        new = {k: 9 for k in old}
        out = share_service.build_text(SITE, [audit(90, new), audit(20, old)])
        lines = [l for l in out["text"].split("\n") if l.startswith("・")]
        assert len(lines) <= 3
        assert "メタ情報" not in out["text"]     # 主要4項目の外


class TestLimits:
    def test_never_exceeds_x_limit(self):
        long_site = {"name": "あ" * 120, "url": "https://example.com/"}
        old = {"llms": 0, "schema": 0, "robots": 0, "content": 0}
        new = {k: 9 for k in old}
        out = share_service.build_text(long_site, [audit(90, new), audit(20, old)],
                                       "https://kurage.exbridge.jp/kgeo.php")
        assert len(out["text"]) <= 280

    def test_intent_url_roundtrips(self):
        out = share_service.build_text(SITE, [audit(47, {})])
        assert out["intent_url"].startswith("https://x.com/intent/post?text=")
        encoded = out["intent_url"].split("text=", 1)[1]
        assert unquote(encoded) == out["text"]

    def test_breakdown_accepts_json_string(self):
        """本番のMySQLはJSON文字列で返すことがある。"""
        audits = [audit(78, json.dumps({"llms": 10})), audit(47, json.dumps({"llms": 0}))]
        out = share_service.build_text(SITE, audits)
        assert "llms.txt 0 → 10" in out["text"]

    def test_empty_audits_raises(self):
        try:
            share_service.build_text(SITE, [])
        except ValueError:
            return
        raise AssertionError("監査ゼロで例外にならない")
