"""seo モジュール（next-forge packages/seo の移植）のテスト。

生成物は顧客サイトの <head> に貼られる。埋め込みが壊れると、
効かないだけでなく顧客サイトに任意のHTMLを差し込む穴になる。
"""

from __future__ import annotations

import json
import re

import pytest

from app import seo


class TestJsonLdEmbedding:
    """LLMの出力をそのまま <script> に入れないこと。"""

    def test_closing_script_tag_cannot_break_out(self):
        """本文に </script> が混ざっても、スクリプトが途中で閉じない。

        これが漏れると、監査結果の説明文などに `</script><img onerror=...>`
        を仕込まれた場合、顧客サイトで実行されうる。
        """
        payload = {"@type": "Organization",
                   "description": "</script><img src=x onerror=alert(1)>"}
        out = seo.json_ld_script(payload)
        body = out.split(">", 1)[1].rsplit("<", 1)[0]
        assert "</script>" not in body
        assert "<img" not in body
        assert "\\u003c" in body

    def test_ampersand_is_escaped(self):
        out = seo.json_ld_script({"name": "A&B"})
        assert "&" not in out.split(">", 1)[1].rsplit("<", 1)[0]
        assert "\\u0026" in out

    def test_line_separators_are_escaped(self):
        """U+2028 / U+2029 はJavaScriptで行終端になり、構文を壊す。"""
        out = seo.json_ld_script({"name": "A B C"})
        assert " " not in out and " " not in out
        assert "\\u2028" in out and "\\u2029" in out

    def test_still_parses_as_json_after_escaping(self):
        """逃がした後も、JSONとしての値は変わらないこと。"""
        original = {"@type": "Organization", "name": "<A&B>", "url": "https://a.example"}
        out = seo.json_ld_script(original)
        body = re.search(r">\n(.*)\n</script>", out, re.S).group(1)
        assert json.loads(body) == original

    def test_accepts_json_string(self):
        """LLMの出力（文字列）をそのまま渡せること。"""
        out = seo.json_ld_script('{"@type": "WebSite", "name": "A"}')
        assert '"@type"' in out and out.startswith('<script type="application/ld+json">')

    def test_broken_json_is_wrapped_but_escaped(self):
        """壊れたJSONでも、埋め込みだけは安全にする（正否の判定は呼び出し側）。"""
        out = seo.json_ld_script('{"name": "</script>"')
        assert out.startswith('<script type="application/ld+json">')
        assert out.endswith("</script>")
        body = out[len('<script type="application/ld+json">'):-len("</script>")]
        assert "</script>" not in body

    def test_japanese_is_not_escaped_to_ascii(self):
        """日本語がそのまま読めること（ensure_ascii=False）。"""
        assert "株式会社" in seo.json_ld_script({"name": "株式会社エクスブリッジ"})


class TestCreateMetadata:
    def test_includes_the_core_tags(self):
        out = seo.create_metadata(
            title="料金", description="ご利用料金のご案内です。",
            url="https://a.example/price", site_name="A社")
        assert "<title>料金 | A社</title>" in out
        assert '<meta name="description" content="ご利用料金のご案内です。">' in out
        assert '<link rel="canonical" href="https://a.example/price">' in out
        assert '<meta property="og:title" content="料金 | A社">' in out
        assert '<meta property="og:url" content="https://a.example/price">' in out
        assert '<meta name="twitter:card" content="summary">' in out

    def test_image_switches_card_type_and_adds_size(self):
        out = seo.create_metadata(
            title="A", description="B", image="https://a.example/ogp.png")
        assert '<meta name="twitter:card" content="summary_large_image">' in out
        assert '<meta property="og:image:width" content="1200">' in out
        assert '<meta property="og:image:height" content="630">' in out

    def test_title_is_not_doubled_when_it_equals_site_name(self):
        out = seo.create_metadata(title="A社", description="B", site_name="A社")
        assert "<title>A社</title>" in out

    def test_title_is_not_doubled_when_it_already_contains_site_name(self):
        """LLMが書くtitleはブランド名を含みがち。足すと3回出ることになる。

        実サイト(exbridge.jp)で「A社 | 事業内容 | A社」が出た件の再発防止。
        """
        out = seo.create_metadata(
            title="株式会社エクスブリッジ | AI駆動経営とシステム開発",
            description="B", site_name="株式会社エクスブリッジ")
        assert "<title>株式会社エクスブリッジ | AI駆動経営とシステム開発</title>" in out
        assert out.count("株式会社エクスブリッジ | AI駆動経営とシステム開発 | 株式会社") == 0

    def test_quotes_and_tags_in_content_are_escaped(self):
        """顧客の本文に " や < が入っていても、属性から抜け出せないこと。"""
        out = seo.create_metadata(title='A"><b>', description="B")
        assert '"><b>' not in out
        assert "&quot;" in out and "&lt;" in out

    def test_empty_title_is_rejected(self):
        with pytest.raises(ValueError):
            seo.create_metadata(title="  ", description="B")

    def test_twitter_handle_gets_at_mark(self):
        out = seo.create_metadata(title="A", description="B", twitter_handle="xb_bittensor")
        assert '<meta name="twitter:creator" content="@xb_bittensor">' in out
