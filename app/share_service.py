"""GEO監査結果をXへ投稿するための本文を組み立てる。

多ユーザーSaaSなので、利用者はそれぞれ自分のXアカウントへ投稿する。
認証情報を預かるべきではないため、こちらは本文を作るところまでを担い、
投稿はXの投稿画面(web intent)に本文を渡して利用者自身が確定する。

2回以上監査していれば「最初 → 最新」の比較を出す。改善したことを
自分で示せるようにするのが目的で、全項目ではなく主要項目だけに絞る。
"""

from __future__ import annotations

from urllib.parse import quote

from .audit_service import CATEGORY_LABELS

X_LIMIT = 280
# 比較で出す主要カテゴリ。全8項目を並べると読まれないので、
# GEOで効きが大きく、かつ直せば確実に動く順に上位だけ出す。
PRIMARY_CATEGORIES = ["llms", "schema", "robots", "content"]
MAX_CATEGORY_LINES = 3


def _band_label(band: str) -> str:
    return {
        "foundation": "土台づくり",
        "developing": "改善中",
        "competitive": "競争力あり",
        "leading": "先行",
    }.get(str(band or "").lower(), str(band or ""))


def _delta(new: int, old: int) -> str:
    diff = new - old
    if diff > 0:
        return f"+{diff}"
    if diff < 0:
        return str(diff)
    return "±0"


def _breakdown(row: dict) -> dict[str, int]:
    raw = row.get("score_breakdown") or {}
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    return {k: int(v) for k, v in raw.items() if isinstance(v, (int, float))}


def build_text(site: dict, audits: list[dict], page_url: str = "") -> dict:
    """投稿本文を作る。audits は新しい順。

    1回だけなら現状の点数、2回以上なら最初と最新の比較を出す。
    """
    if not audits:
        raise ValueError("監査結果がありません")

    latest = audits[0]
    name = str(site.get("name") or site.get("brand_name") or site.get("url") or "").strip()
    lines: list[str] = []
    compared = len(audits) >= 2

    if not compared:
        lines.append(f"🔎 {name} のAI検索対応(GEO)を診断しました")
        lines.append(f"総合スコア {latest.get('score')}/100（{_band_label(latest.get('band'))}）")
    else:
        first = audits[-1]
        lines.append(f"🔎 {name} のAI検索対応(GEO)を改善しました")
        lines.append(
            f"総合スコア {first.get('score')} → {latest.get('score')}/100"
            f"（{_delta(int(latest.get('score') or 0), int(first.get('score') or 0))}）"
        )
        old = _breakdown(first)
        new = _breakdown(latest)
        moved = []
        for key in PRIMARY_CATEGORIES:
            if key in new and key in old and new[key] != old[key]:
                moved.append(
                    f"・{CATEGORY_LABELS.get(key, key)} {old[key]} → {new[key]}"
                    f"（{_delta(new[key], old[key])}）"
                )
        lines.extend(moved[:MAX_CATEGORY_LINES])
        lines.append(f"計{len(audits)}回の診断で確認")

    lines.append("")
    lines.append("診断: Kurage GEO")
    if page_url:
        lines.append(page_url)

    text = "\n".join(lines)
    # Xの上限を超えたら、可変部(カテゴリ行)から削る。末尾のURLと出典は残す。
    while len(text) > X_LIMIT and len(lines) > 4:
        for index in range(len(lines) - 1, -1, -1):
            if lines[index].startswith("・"):
                lines.pop(index)
                break
        else:
            break
        text = "\n".join(lines)

    return {
        "text": text[:X_LIMIT],
        "compared": compared,
        "audit_count": len(audits),
        "intent_url": "https://x.com/intent/post?text=" + quote(text[:X_LIMIT], safe=""),
    }
