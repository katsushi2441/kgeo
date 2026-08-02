from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .japanese_aeo import analyze_aeo

VENDOR_SRC = Path(__file__).resolve().parents[1] / "vendor" / "geo-optimizer-skill" / "src"
if str(VENDOR_SRC) not in sys.path:
    sys.path.insert(0, str(VENDOR_SRC))

from geo_optimizer.core.audit import run_full_audit  # noqa: E402
from geo_optimizer.utils.http import fetch_url  # noqa: E402
from geo_optimizer.utils.validators import validate_public_url  # noqa: E402

CATEGORY_LABELS = {
    "robots": "AIクローラー許可",
    "llms": "llms.txt",
    "schema": "構造化データ",
    "meta": "メタ情報",
    "content": "コンテンツ",
    "signals": "更新・配信シグナル",
    "ai_discovery": "AI向け発見性",
    "brand_entity": "ブランド・エンティティ",
}


def validate_target(url: str) -> str:
    normalized = url.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.username or parsed.password:
        raise ValueError("認証情報を含むURLは利用できません")
    ok, error = validate_public_url(normalized)
    if not ok:
        raise ValueError(error or "公開URLではありません")
    return normalized


def run_audit(url: str) -> dict:
    target = validate_target(url)
    result = run_full_audit(target, use_cache=False)
    data = dataclasses.asdict(result)
    response, error = fetch_url(target, timeout=15, max_size=2 * 1024 * 1024)
    if response is not None and not error:
        aeo = analyze_aeo(response.text, data)
    else:
        aeo = {
            "checked": False,
            "language": "unknown",
            "analyzed_as": "unknown",
            "score": 0,
            "band": "critical",
            "notice": f"AEO判定用の本文を取得できませんでした: {error or 'unknown error'}",
            "metrics": {},
            "recommendations": [],
        }
    # aeo が正式キー。japanese_aeo は既存の保存済み監査・画面との互換用に残す。
    data["aeo"] = aeo
    data["japanese_aeo"] = aeo
    data["schema_version"] = 2
    return data


def fetch_site_context(url: str, max_chars: int = 12000) -> str:
    """Fetch public page text for a grounded local-LLM evaluation."""

    target = validate_target(url)
    response, error = fetch_url(target, timeout=15, max_size=2 * 1024 * 1024)
    if response is None or error:
        raise RuntimeError(f"対象ページを取得できませんでした: {error or 'unknown error'}")
    soup = BeautifulSoup(response.text, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "template", "form"]):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    parts: list[str] = []
    if soup.title and soup.title.string:
        parts.append(f"ページタイトル: {soup.title.string.strip()}")
    description = soup.find("meta", attrs={"name": "description"})
    if description and description.get("content"):
        parts.append(f"概要: {str(description['content']).strip()}")
    for node in root.find_all(["h1", "h2", "h3", "p", "li", "th", "td"]):
        value = " ".join(node.get_text(" ", strip=True).split())
        if value and (not parts or value != parts[-1]):
            prefix = "見出し: " if node.name in {"h1", "h2", "h3"} else ""
            parts.append(prefix + value)
    context = "\n".join(parts)
    if not context.strip():
        raise RuntimeError("対象ページから評価可能な本文を抽出できませんでした")
    return context[:max_chars]


def japanese_recommendations(result: dict) -> list[str]:
    """Return concise Japanese actions based on deterministic audit facts."""
    actions: list[str] = []
    robots = result.get("robots") or {}
    llms = result.get("llms") or {}
    schema = result.get("schema") or {}
    meta = result.get("meta") or {}
    content = result.get("content") or {}
    signals = result.get("signals") or {}
    brand = result.get("brand_entity") or {}
    ai = result.get("ai_discovery") or {}
    aeo = result.get("aeo") or result.get("japanese_aeo") or {}
    if result.get("error"):
        return [f"対象ページを取得できませんでした: {result['error']}"]
    if not robots.get("citation_bots_ok"):
        actions.append("robots.txtを確認し、必要なAI検索クローラーを許可してください。")
    if not llms.get("found"):
        actions.append("サイトの要点と主要ページを整理した /llms.txt を設置してください。")
    if not schema.get("has_organization"):
        actions.append("OrganizationのJSON-LDを追加し、組織名・URL・ロゴを明示してください。")
    if not schema.get("has_website"):
        actions.append("WebSiteのJSON-LDを追加してサイトの正式名称とURLを示してください。")
    if not meta.get("has_description"):
        actions.append("ページ内容を端的に表すmeta descriptionを追加してください。")
    if not meta.get("has_canonical"):
        actions.append("重複URLを避けるためcanonical URLを設定してください。")
    if not content.get("has_h1"):
        actions.append("ページの主題を一つのH1見出しで明示してください。")
    if int(content.get("word_count") or 0) < 300:
        actions.append("根拠・具体例・数値を加え、AIが引用しやすい十分な本文量にしてください。")
    if not signals.get("has_freshness"):
        actions.append("dateModifiedなどで更新日を機械可読にしてください。")
    if not brand.get("brand_name_consistent", True):
        actions.append("title・H1・構造化データでブランド名の表記を統一してください。")
    if int(ai.get("endpoints_found") or 0) == 0:
        actions.append("必要に応じてAI向け概要・FAQなどの発見用エンドポイントを整備してください。")
    for item in aeo.get("recommendations") or []:
        if item not in actions:
            actions.append(item)
    return actions[:12]
