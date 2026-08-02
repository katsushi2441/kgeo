"""Language-aware AEO (answer engine optimization) analysis.

日本語ページは日本語の言い回しで、英語ページは英語の言い回しで採点する。
英語ページを日本語の正規表現で測ると、結論先出しも定義文も検出できず不当に低く出る
（実例: kurage.exbridge.jp の英語トップが44点、同内容の日本語版が79点）。

公開関数は analyze_aeo()。analyze_japanese_aeo() は後方互換のエイリアス。
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from bs4 import BeautifulSoup, Tag

JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")

# ── 日本語パターン ───────────────────────────────────────────────
JA_SENTENCE_RE = re.compile(r"[^。！？!?]+[。！？!?]?")
JA_QUESTION_RE = re.compile(
    r"(?:[？?]|とは|なぜ|どうして|どのように|どうやって|いくら|料金|費用|"
    r"おすすめ|選び方|違い|比較|どこ|いつ|誰|何を|何が|できますか|でしょうか)"
)
JA_DEFINITION_RE = re.compile(
    r"(?:とは[、,\s]*|を指します|を指す|のことです|のことをいう|意味します|"
    r"意味する|定義されます|定義される|という(?:手法|方法|仕組み|概念|サービス))"
)
JA_ASSERTIVE_RE = re.compile(
    r"(?:です|ます|である|となります|できます|必要です|有効です|提供します|"
    r"対応します|含みます|利用できます|\d|[０-９]|[%％]|円)"
)
JA_SOURCE_RE = re.compile(
    r"(?:出典|参考|参照|引用|調査|研究|統計|報告|によると|によれば|"
    r"https?://|doi|総務省|経済産業省|厚生労働省)"
)
JA_ABSOLUTE_CLAIM_RE = re.compile(
    r"(?:必ず|絶対(?:に)?|完全(?:に)?|確実(?:に)?|唯一|業界初|日本初|世界初|"
    r"日本一|世界一|No\.?\s*1|100[%％]|間違いなく|誰でも)"
)
JA_STAT_RE = re.compile(
    r"(?:[0-9０-９]+(?:[.,．][0-9０-９]+)?\s*(?:[%％]|人|社|件|倍|円|万円|億円)|"
    r"[一二三四五六七八九十百千万億]+(?:割|人|社|件|倍|円))"
)
JA_INTENT_PATTERNS = {
    "informational": re.compile(r"(?:とは|意味|方法|仕組み|理由|なぜ|解説|ガイド|使い方|手順|基礎)"),
    "navigational": re.compile(r"(?:ログイン|登録|問い合わせ|会社概要|運営会社|アクセス|プロフィール)"),
    "transactional": re.compile(r"(?:購入|注文|申込|申し込み|契約|料金|価格|費用|見積|無料相談|資料請求|導入)"),
    "commercial": re.compile(r"(?:おすすめ|比較|違い|選び方|ランキング|評判|口コミ|メリット|デメリット|代替)"),
}

# ── 英語パターン ─────────────────────────────────────────────────
EN_SENTENCE_RE = re.compile(r"[^.!?]+[.!?]?")
EN_QUESTION_RE = re.compile(
    r"(?:\?|\b(?:what|how|why|when|where|who|which|whose|"
    r"is|are|was|were|can|could|do|does|did|should|will|would|"
    r"pricing|price|cost|faq|vs\.?|versus|compare|comparison|guide|tutorial)\b)",
    re.IGNORECASE,
)
EN_DEFINITION_RE = re.compile(
    r"(?:\b(?:is|are)\s+(?:a|an|the)\b|\brefers?\s+to\b|\bmeans\b|\bstands?\s+for\b|"
    r"\bis\s+defined\s+as\b|\bis\s+known\s+as\b|\bdescribes?\b|\bconsists?\s+of\b)",
    re.IGNORECASE,
)
EN_ASSERTIVE_RE = re.compile(
    r"(?:\b(?:is|are|was|were|has|have|can|will|provides?|offers?|supports?|"
    r"includes?|delivers?|runs?|costs?|takes?|uses?)\b|\d|[%$€£¥])",
    re.IGNORECASE,
)
EN_SOURCE_RE = re.compile(
    r"(?:\b(?:source|sources|according\s+to|based\s+on|study|studies|research|"
    r"report|survey|statistics|documentation|reference|cited)\b|https?://|doi)",
    re.IGNORECASE,
)
EN_ABSOLUTE_CLAIM_RE = re.compile(
    r"(?:\b(?:always|never|guaranteed|guarantee|100\s*%|the\s+best|world'?s\s+first|"
    r"industry'?s\s+first|no\.?\s*1|#1|the\s+only|everyone|anybody\s+can|risk[- ]free)\b)",
    re.IGNORECASE,
)
EN_STAT_RE = re.compile(
    r"(?:[$€£¥]\s?[0-9][0-9,.]*|[0-9][0-9,.]*\s*(?:%|percent|x|times|users?|customers?|"
    r"companies|hours?|minutes?|seconds?|days?|years?|JPY|USD|EUR))",
    re.IGNORECASE,
)
EN_INTENT_PATTERNS = {
    "informational": re.compile(
        r"\b(?:what\s+is|how\s+to|why|guide|tutorial|documentation|docs|learn|overview|introduction|explained)\b",
        re.IGNORECASE,
    ),
    "navigational": re.compile(
        r"\b(?:login|log\s+in|sign\s+in|sign\s+up|contact|about\s+us|about|company|careers|support)\b",
        re.IGNORECASE,
    ),
    "transactional": re.compile(
        r"\b(?:pricing|price|buy|purchase|order|subscribe|plan|plans|free\s+trial|get\s+started|request\s+a\s+quote|demo)\b",
        re.IGNORECASE,
    ),
    "commercial": re.compile(
        r"\b(?:vs\.?|versus|compare|comparison|alternative|alternatives|best|review|reviews|pros\s+and\s+cons|benefits)\b",
        re.IGNORECASE,
    ),
}

INTENT_LABELS_JA = {
    "informational": "解説",
    "navigational": "会社・問い合わせ",
    "transactional": "料金・申込",
    "commercial": "比較・選び方",
}


class _Profile:
    """言語ごとの判定パターンと閾値をまとめたもの。"""

    def __init__(self, language: str) -> None:
        self.language = language
        if language == "en":
            self.sentence = EN_SENTENCE_RE
            self.question = EN_QUESTION_RE
            self.definition = EN_DEFINITION_RE
            self.assertive = EN_ASSERTIVE_RE
            self.source = EN_SOURCE_RE
            self.absolute = EN_ABSOLUTE_CLAIM_RE
            self.stat = EN_STAT_RE
            self.intents = EN_INTENT_PATTERNS
            # 英語は語数で数える
            self.unit = "words"
            self.sentence_range = (8, 30)
            self.paragraph_range = (15, 120)
            self.answer_window = 220
            self.definition_window = 240
            self.concise_answer_range = (5, 40)
        else:
            self.sentence = JA_SENTENCE_RE
            self.question = JA_QUESTION_RE
            self.definition = JA_DEFINITION_RE
            self.assertive = JA_ASSERTIVE_RE
            self.source = JA_SOURCE_RE
            self.absolute = JA_ABSOLUTE_CLAIM_RE
            self.stat = JA_STAT_RE
            self.intents = JA_INTENT_PATTERNS
            # 日本語は文字数で数える
            self.unit = "chars"
            self.sentence_range = (15, 80)
            self.paragraph_range = (30, 260)
            self.answer_window = 160
            self.definition_window = 180
            self.concise_answer_range = (20, 180)

    def size(self, value: str) -> int:
        """言語に応じた長さ（日本語は文字数、英語は語数）。"""
        if self.unit == "words":
            return len(value.split())
        return len(re.sub(r"\s+", "", value))


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip()


def _text(node: Tag | None) -> str:
    return _normalize(node.get_text(" ", strip=True) if node else "")


def _next_content(heading: Tag) -> str:
    node = heading.find_next(["p", "li", "div"])
    return _text(node)[:240]


def _ratio_score(value: float, maximum: int) -> int:
    return min(maximum, max(0, round(value * maximum)))


def detect_language(html: str, body_text: str) -> tuple[str, float]:
    """本文の日本語比率とhtml lang属性からページ言語を判定する。

    本文を優先する。lang属性は間違って設定されていることが多いため、
    日本語比率がはっきりしている場合はそちらを信用する。
    """
    japanese_chars = len(JAPANESE_RE.findall(body_text))
    visible_chars = len(re.sub(r"\s+", "", body_text))
    japanese_ratio = japanese_chars / max(visible_chars, 1)

    if japanese_ratio >= 0.15:
        return "ja", japanese_ratio
    if visible_chars >= 200:
        # 日本語がほぼ無く、十分な本文量があれば英語系として扱う
        return "en", japanese_ratio

    # 本文が短くて判断できないときだけ lang 属性に頼る
    match = re.search(r"<html[^>]*\blang\s*=\s*[\"']([a-zA-Z-]+)", html or "")
    declared = (match.group(1).lower() if match else "")
    if declared.startswith("ja"):
        return "ja", japanese_ratio
    if declared.startswith("en"):
        return "en", japanese_ratio
    return "unknown", japanese_ratio


def analyze_aeo(html: str, base_result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate answer-engine readiness using the page's own language rules.

    This score is a deterministic readiness proxy. It does not claim to measure
    live rankings or responses from ChatGPT, Gemini, or other external engines.
    """

    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    body_text = _text(root)
    visible_chars = len(re.sub(r"\s+", "", body_text))

    language, japanese_ratio = detect_language(html, body_text)
    profile = _Profile("en" if language == "en" else "ja")

    headings = [tag for tag in root.find_all(["h1", "h2", "h3"]) if _text(tag)]
    section_headings = [tag for tag in headings if tag.name in {"h2", "h3"}]
    paragraphs = [_text(tag) for tag in root.find_all("p") if len(_text(tag)) >= 10]

    answer_first_count = 0
    definition_count = 0
    question_count = 0
    concise_answer_count = 0
    for heading in section_headings:
        heading_text = _text(heading)
        answer = _next_content(heading)
        if answer and (
            profile.assertive.search(answer[: profile.answer_window])
            or profile.stat.search(answer[: profile.answer_window])
        ):
            answer_first_count += 1
        if answer and profile.definition.search(answer[: profile.definition_window]):
            definition_count += 1
        if profile.question.search(heading_text):
            question_count += 1
            low, high = profile.concise_answer_range
            if low <= profile.size(answer) <= high:
                concise_answer_count += 1

    section_total = max(len(section_headings), 1)
    answer_first_ratio = answer_first_count / section_total
    definition_ratio = definition_count / section_total
    question_ratio = concise_answer_count / max(question_count, 1)

    sentences = [
        _normalize(match.group(0))
        for match in profile.sentence.finditer(body_text)
        if profile.size(match.group(0)) >= (3 if profile.unit == "words" else 4)
    ]
    avg_sentence_size = round(
        sum(profile.size(sentence) for sentence in sentences) / max(len(sentences), 1), 1
    )
    s_low, s_high = profile.sentence_range
    readable_sentences = sum(1 for sentence in sentences if s_low <= profile.size(sentence) <= s_high)
    readable_ratio = readable_sentences / max(len(sentences), 1)
    p_low, p_high = profile.paragraph_range
    readable_paragraphs = sum(1 for paragraph in paragraphs if p_low <= profile.size(paragraph) <= p_high)
    paragraph_ratio = readable_paragraphs / max(len(paragraphs), 1)
    readability_score = round((readable_ratio * 0.65 + paragraph_ratio * 0.35) * 100)

    intent_hits = {name: len(pattern.findall(body_text)) for name, pattern in profile.intents.items()}
    intents_found = [name for name, count in intent_hits.items() if count]
    intent_score = round(len(intents_found) / len(profile.intents) * 100)

    statistics = list(profile.stat.finditer(body_text))
    source_signals = len(profile.source.findall(body_text))
    external_links = 0
    for link in root.find_all("a", href=True):
        href = str(link.get("href") or "")
        if href.startswith(("http://", "https://")):
            external_links += 1
    evidence_score = min(100, source_signals * 18 + external_links * 5 + min(len(statistics), 5) * 5)

    absolute_claims = [_normalize(match.group(0)) for match in profile.absolute.finditer(body_text)]
    unsourced_statistics = len(statistics) if statistics and not (source_signals or external_links) else 0
    risk_score = min(100, len(absolute_claims) * 20 + unsourced_statistics * 12)

    answer_score = _ratio_score(answer_first_ratio, 100)
    definition_score = _ratio_score(definition_ratio, 100)
    question_answer_score = _ratio_score(question_ratio, 100) if question_count else 0
    total_score = round(
        answer_score * 0.25
        + definition_score * 0.15
        + question_answer_score * 0.15
        + evidence_score * 0.20
        + readability_score * 0.15
        + intent_score * 0.10
        - risk_score * 0.10
    )
    total_score = max(0, min(100, total_score))

    # 改善案は管理画面の表示言語（日本語）に合わせる。判定自体はページの言語で行う。
    size_label = "語" if profile.unit == "words" else "文字"
    recommendations: list[str] = []
    if answer_first_ratio < 0.5:
        recommendations.append("各見出しの直後に、結論を1〜2文で先に書いてください。")
    if definition_count == 0:
        if profile.language == "en":
            recommendations.append('重要語に "X is a ..." / "X refers to ..." のような定義文を追加してください。')
        else:
            recommendations.append("重要語に「○○とは〜を指します」の定義文を追加してください。")
    if question_count == 0:
        if profile.language == "en":
            recommendations.append('"How much does it cost?" のような利用者の質問を見出しとして追加してください。')
        else:
            recommendations.append("「料金はいくらですか？」など、利用者の質問を見出しとして追加してください。")
    elif concise_answer_count < question_count:
        high = profile.concise_answer_range[1]
        recommendations.append(f"質問見出しの直後に、{high}{size_label}以内の直接回答を置いてください。")
    if evidence_score < 50:
        recommendations.append("数値・比較・主張に、調査名、更新日、出典URLを添えてください。")
    if readability_score < 65:
        recommendations.append(
            f"長い文を分割し、1段落を{p_low}〜{p_high}{size_label}程度に整理してください。"
        )
    if len(intents_found) < 3:
        missing = [INTENT_LABELS_JA[name] for name in profile.intents if name not in intents_found]
        recommendations.append(f"不足している検索意図（{'、'.join(missing)}）に答えるページを追加してください。")
    if absolute_claims or unsourced_statistics:
        if profile.language == "en":
            recommendations.append(
                '"always" "guaranteed" "#1" などの断定や出典のない数値を、検証可能な根拠付き表現へ直してください。'
            )
        else:
            recommendations.append(
                "「必ず」「No.1」などの断定や出典のない数値を、検証可能な根拠付き表現へ直してください。"
            )

    language_label = {"ja": "日本語", "en": "英語"}.get(profile.language, profile.language)
    notice = (
        f"{language_label}コンテンツとして判定した決定論的なAEO準備度であり、"
        "外部AI検索の掲載順位ではありません。"
    )
    if language == "unknown":
        notice = (
            "本文が短く言語を判別できなかったため、日本語基準で判定しました。"
            "外部AI検索の掲載順位ではありません。"
        )

    return {
        "checked": bool(body_text),
        "language": language,
        "analyzed_as": profile.language,
        "notice": notice,
        "score": total_score,
        "band": "excellent" if total_score >= 85 else "good" if total_score >= 70 else "foundation" if total_score >= 45 else "critical",
        "metrics": {
            "answer_first": {"score": answer_score, "found": answer_first_count, "total": len(section_headings)},
            "definitions": {"score": definition_score, "found": definition_count, "total": len(section_headings)},
            "question_answers": {"score": question_answer_score, "questions": question_count, "concise_answers": concise_answer_count},
            "evidence": {"score": evidence_score, "statistics": len(statistics), "source_signals": source_signals, "external_links": external_links},
            "readability": {
                "score": readability_score,
                "sentences": len(sentences),
                "avg_sentence_chars": avg_sentence_size,
                "unit": profile.unit,
            },
            "intent_coverage": {"score": intent_score, "found": intents_found, "hits": intent_hits},
            "claim_risk": {"score": risk_score, "absolute_claims": absolute_claims[:10], "unsourced_statistics": unsourced_statistics},
        },
        "recommendations": recommendations[:8],
        "source": {
            "visible_characters": visible_chars,
            "japanese_character_ratio": round(japanese_ratio, 3),
            "headings": len(headings),
            "paragraphs": len(paragraphs),
        },
        "base_geo_score": int((base_result or {}).get("score") or 0),
    }


# 後方互換: 既存の呼び出し名を残す
analyze_japanese_aeo = analyze_aeo
