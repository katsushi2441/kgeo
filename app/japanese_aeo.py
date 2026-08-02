from __future__ import annotations

import re
import unicodedata
from typing import Any

from bs4 import BeautifulSoup, Tag

JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
SENTENCE_RE = re.compile(r"[^。！？!?]+[。！？!?]?")
QUESTION_RE = re.compile(
    r"(?:[？?]|とは|なぜ|どうして|どのように|どうやって|いくら|料金|費用|"
    r"おすすめ|選び方|違い|比較|どこ|いつ|誰|何を|何が|できますか|でしょうか)"
)
DEFINITION_RE = re.compile(
    r"(?:とは[、,\s]*|を指します|を指す|のことです|のことをいう|意味します|"
    r"意味する|定義されます|定義される|という(?:手法|方法|仕組み|概念|サービス))"
)
ASSERTIVE_RE = re.compile(
    r"(?:です|ます|である|となります|できます|必要です|有効です|提供します|"
    r"対応します|含みます|利用できます|\d|[０-９]|[%％]|円)"
)
SOURCE_RE = re.compile(
    r"(?:出典|参考|参照|引用|調査|研究|統計|報告|によると|によれば|"
    r"https?://|doi|総務省|経済産業省|厚生労働省)"
)
ABSOLUTE_CLAIM_RE = re.compile(
    r"(?:必ず|絶対(?:に)?|完全(?:に)?|確実(?:に)?|唯一|業界初|日本初|世界初|"
    r"日本一|世界一|No\.?\s*1|100[%％]|間違いなく|誰でも)"
)
STAT_RE = re.compile(
    r"(?:[0-9０-９]+(?:[.,．][0-9０-９]+)?\s*(?:[%％]|人|社|件|倍|円|万円|億円)|"
    r"[一二三四五六七八九十百千万億]+(?:割|人|社|件|倍|円))"
)

INTENT_PATTERNS = {
    "informational": re.compile(r"(?:とは|意味|方法|仕組み|理由|なぜ|解説|ガイド|使い方|手順|基礎)"),
    "navigational": re.compile(r"(?:ログイン|登録|問い合わせ|会社概要|運営会社|アクセス|プロフィール)"),
    "transactional": re.compile(r"(?:購入|注文|申込|申し込み|契約|料金|価格|費用|見積|無料相談|資料請求|導入)"),
    "commercial": re.compile(r"(?:おすすめ|比較|違い|選び方|ランキング|評判|口コミ|メリット|デメリット|代替)"),
}


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip()


def _text(node: Tag | None) -> str:
    return _normalize(node.get_text(" ", strip=True) if node else "")


def _next_content(heading: Tag) -> str:
    node = heading.find_next(["p", "li", "div"])
    return _text(node)[:240]


def _ratio_score(value: float, maximum: int) -> int:
    return min(maximum, max(0, round(value * maximum)))


def analyze_japanese_aeo(html: str, base_result: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate Japanese answer-engine readiness with Japanese-specific rules.

    This score is a deterministic readiness proxy. It does not claim to measure
    live rankings or responses from ChatGPT, Gemini, or other external engines.
    """

    soup = BeautifulSoup(html or "", "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    body_text = _text(root)
    japanese_chars = len(JAPANESE_RE.findall(body_text))
    visible_chars = len(re.sub(r"\s+", "", body_text))
    japanese_ratio = japanese_chars / max(visible_chars, 1)

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
        if answer and (ASSERTIVE_RE.search(answer[:160]) or STAT_RE.search(answer[:160])):
            answer_first_count += 1
        if answer and DEFINITION_RE.search(answer[:180]):
            definition_count += 1
        if QUESTION_RE.search(heading_text):
            question_count += 1
            if 20 <= len(re.sub(r"\s+", "", answer)) <= 180:
                concise_answer_count += 1

    section_total = max(len(section_headings), 1)
    answer_first_ratio = answer_first_count / section_total
    definition_ratio = definition_count / section_total
    question_ratio = concise_answer_count / max(question_count, 1)

    sentences = [
        _normalize(match.group(0))
        for match in SENTENCE_RE.finditer(body_text)
        if len(re.sub(r"\s+", "", match.group(0))) >= 4
    ]
    avg_sentence_chars = round(
        sum(len(re.sub(r"\s+", "", sentence)) for sentence in sentences) / max(len(sentences), 1), 1
    )
    readable_sentences = sum(1 for sentence in sentences if 15 <= len(re.sub(r"\s+", "", sentence)) <= 80)
    readable_ratio = readable_sentences / max(len(sentences), 1)
    readable_paragraphs = sum(1 for paragraph in paragraphs if 30 <= len(paragraph) <= 260)
    paragraph_ratio = readable_paragraphs / max(len(paragraphs), 1)
    readability_score = round((readable_ratio * 0.65 + paragraph_ratio * 0.35) * 100)

    intent_hits = {
        name: len(pattern.findall(body_text)) for name, pattern in INTENT_PATTERNS.items()
    }
    intents_found = [name for name, count in intent_hits.items() if count]
    intent_score = round(len(intents_found) / len(INTENT_PATTERNS) * 100)

    statistics = list(STAT_RE.finditer(body_text))
    source_signals = len(SOURCE_RE.findall(body_text))
    external_links = 0
    for link in root.find_all("a", href=True):
        href = str(link.get("href") or "")
        if href.startswith(("http://", "https://")):
            external_links += 1
    evidence_score = min(100, source_signals * 18 + external_links * 5 + min(len(statistics), 5) * 5)

    absolute_claims = [_normalize(match.group(0)) for match in ABSOLUTE_CLAIM_RE.finditer(body_text)]
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

    recommendations: list[str] = []
    if answer_first_ratio < 0.5:
        recommendations.append("各見出しの直後に、結論を1〜2文で先に書いてください。")
    if definition_count == 0:
        recommendations.append("重要語に「○○とは〜を指します」の定義文を追加してください。")
    if question_count == 0:
        recommendations.append("「料金はいくらですか？」など、利用者の質問を見出しとして追加してください。")
    elif concise_answer_count < question_count:
        recommendations.append("質問見出しの直後に、180文字以内の直接回答を置いてください。")
    if evidence_score < 50:
        recommendations.append("数値・比較・主張に、調査名、更新日、出典URLを添えてください。")
    if readability_score < 65:
        recommendations.append("長い文を分割し、1段落を30〜260文字程度に整理してください。")
    if len(intents_found) < 3:
        missing_labels = {
            "informational": "解説",
            "navigational": "会社・問い合わせ",
            "transactional": "料金・申込",
            "commercial": "比較・選び方",
        }
        missing = [missing_labels[name] for name in INTENT_PATTERNS if name not in intents_found]
        recommendations.append(f"不足している検索意図（{'、'.join(missing)}）に答えるページを追加してください。")
    if absolute_claims or unsourced_statistics:
        recommendations.append("「必ず」「No.1」などの断定や出典のない数値を、検証可能な根拠付き表現へ直してください。")

    return {
        "checked": bool(body_text),
        "language": "ja" if japanese_ratio >= 0.15 else "unknown",
        "score": total_score,
        "band": "excellent" if total_score >= 85 else "good" if total_score >= 70 else "foundation" if total_score >= 45 else "critical",
        "notice": "日本語コンテンツの決定論的なAEO準備度であり、外部AI検索の掲載順位ではありません。",
        "metrics": {
            "answer_first": {"score": answer_score, "found": answer_first_count, "total": len(section_headings)},
            "definitions": {"score": definition_score, "found": definition_count, "total": len(section_headings)},
            "question_answers": {"score": question_answer_score, "questions": question_count, "concise_answers": concise_answer_count},
            "evidence": {"score": evidence_score, "statistics": len(statistics), "source_signals": source_signals, "external_links": external_links},
            "readability": {"score": readability_score, "sentences": len(sentences), "avg_sentence_chars": avg_sentence_chars},
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
