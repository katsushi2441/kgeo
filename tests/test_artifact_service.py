"""llms.txt / JSON-LD 生成のテスト。

生成物はお客様がサイトに設置するもので、壊れたまま渡すと設置しても効かない。
形式の検証と、「不足しているものだけ生成する」判定を固定する。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app import artifact_service


class TestMissingArtifacts:
    """すでに揃っているサイトに生成を勧めない。不信感につながるため。"""

    def test_both_missing(self):
        audit = {"result": {"llms": {"found": False}, "schema": {}}}
        assert artifact_service.missing_artifacts(audit) == ["llms_txt", "json_ld"]

    def test_nothing_missing(self):
        audit = {"result": {"llms": {"found": True},
                            "schema": {"has_organization": True, "has_website": True}}}
        assert artifact_service.missing_artifacts(audit) == []

    def test_only_llms_missing(self):
        audit = {"result": {"llms": {"found": False},
                            "schema": {"has_organization": True, "has_website": True}}}
        assert artifact_service.missing_artifacts(audit) == ["llms_txt"]

    def test_partial_schema_still_needs_jsonld(self):
        """Organizationだけあって WebSite が無い場合も生成対象。"""
        audit = {"result": {"llms": {"found": True},
                            "schema": {"has_organization": True, "has_website": False}}}
        assert artifact_service.missing_artifacts(audit) == ["json_ld"]

    def test_accepts_flat_result(self):
        """result で包まれていない監査行でも読めること。"""
        assert artifact_service.missing_artifacts({"llms": {"found": True}, "schema": {}}) == ["json_ld"]


class TestFenceStripping:
    """モデルは頼まなくてもコードフェンスを付ける。付いたまま渡すと設置で壊れる。"""

    def test_strips_json_fence(self):
        assert artifact_service._strip_fence('```json\n{"a":1}\n```') == '{"a":1}'

    def test_strips_bare_fence(self):
        assert artifact_service._strip_fence("```\n# Title\n```") == "# Title"

    def test_leaves_plain_text(self):
        assert artifact_service._strip_fence("  # Title\n") == "# Title"


class TestJsonLdValidation:
    def test_valid_graph_passes(self):
        body = json.dumps({"@context": "https://schema.org", "@graph": [
            {"@type": "Organization", "name": "A", "url": "https://a.example"},
            {"@type": "WebSite", "name": "A", "url": "https://a.example"},
        ]})
        assert artifact_service._valid_jsonld(body) == (True, "")

    def test_broken_json_is_rejected(self):
        ok, reason = artifact_service._valid_jsonld("{not json")
        assert ok is False and "解釈できません" in reason

    def test_missing_website_is_reported(self):
        body = json.dumps({"@graph": [{"@type": "Organization", "name": "A"}]})
        ok, reason = artifact_service._valid_jsonld(body)
        assert ok is False and "WebSite" in reason

    def test_single_node_without_graph(self):
        body = json.dumps({"@type": "Organization", "name": "A"})
        ok, reason = artifact_service._valid_jsonld(body)
        assert ok is False and "WebSite" in reason


class TestGenerate:
    @pytest.fixture()
    def stub_llm(self, monkeypatch):
        calls = []

        async def fake_run(messages, owner, *, paid):
            calls.append({"owner": owner, "paid": paid, "system": messages[0]["content"]})
            if "llms.txt" in messages[0]["content"]:
                return "# Sample\n\n> 要約", "ollama-rqdb4ai", "gemma4:12b-it-qat"
            body = json.dumps({"@graph": [{"@type": "Organization"}, {"@type": "WebSite"}]})
            return f"```json\n{body}\n```", "ollama-rqdb4ai", "gemma4:12b-it-qat"

        monkeypatch.setattr(artifact_service.monitor_service, "run_messages", fake_run)
        monkeypatch.setattr(artifact_service.monitor_service, "configured",
                            lambda owner, paid=True: True)
        monkeypatch.setattr(artifact_service.audit_service, "fetch_site_context",
                            lambda url: "本文サンプル")
        return calls

    def test_generates_both(self, stub_llm):
        out = asyncio.run(artifact_service.generate(
            "https://a.example/", "A社", ["llms_txt", "json_ld"], "alice", paid=False))
        assert set(out["artifacts"]) == {"llms_txt", "json_ld"}
        assert out["artifacts"]["llms_txt"]["filename"] == "llms.txt"
        # コードフェンスが外れ、scriptタグで包まれていること
        content = out["artifacts"]["json_ld"]["content"]
        assert content.startswith('<script type="application/ld+json">')
        assert "```" not in content
        assert out["artifacts"]["json_ld"]["valid"] is True

    def test_placement_is_included(self, stub_llm):
        """設置の仕方が分からないと、生成しても使われない。"""
        out = asyncio.run(artifact_service.generate(
            "https://a.example/", "A社", ["llms_txt", "json_ld"], "alice", paid=False))
        assert "/llms.txt" in out["artifacts"]["llms_txt"]["placement"]
        assert "<head>" in out["artifacts"]["json_ld"]["placement"]

    def test_free_run_is_passed_down(self, stub_llm):
        """無料枠ならローカルGemma側で走るよう paid=False が伝わること。"""
        asyncio.run(artifact_service.generate(
            "https://a.example/", "A社", ["llms_txt"], "alice", paid=False))
        assert stub_llm[0]["paid"] is False

    def test_unconfigured_llm_raises(self, monkeypatch):
        monkeypatch.setattr(artifact_service.monitor_service, "configured",
                            lambda owner, paid=True: False)
        with pytest.raises(RuntimeError):
            asyncio.run(artifact_service.generate(
                "https://a.example/", "A", ["llms_txt"], "x", paid=True))
