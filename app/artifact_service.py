"""監査で不足していた llms.txt と JSON-LD を、実際に設置できる形で生成する。

「/llms.txt を設置してください」という定型文のアドバイスで終わらせず、
中身そのものを渡す。生成物は決定論的な監査器で検証できるので、
設置後に再監査すれば点数が上がったことを数字で示せる
(競合のAEO/GEOツールは自前の採点器を持たないためこれができない)。

生成はgemma4/deepseek級で足りる。求めているのは創造性ではなく
「サイトの実際の内容から、決められた書式に落とす」制約付きの作業で、
正しさの判定は監査器側が担うため。
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import audit_service, monitor_service, seo

# 生成物の種類。監査の不足項目と対応する。
LLMS_TXT = "llms_txt"
JSON_LD = "json_ld"
META = "meta"

MAX_CONTEXT_CHARS = 6000


def missing_artifacts(audit_result: dict[str, Any]) -> list[str]:
    """この監査結果で、生成する価値がある成果物。

    すでに揃っているサイトに「生成しますか」と出しても売れないし、
    不信感につながる。不足しているものだけを対象にする。
    """
    result = audit_result.get("result") or audit_result
    missing = []
    if not (result.get("llms") or {}).get("found"):
        missing.append(LLMS_TXT)
    schema = result.get("schema") or {}
    if not schema.get("has_organization") or not schema.get("has_website"):
        missing.append(JSON_LD)
    meta = result.get("meta") or {}
    if not all(meta.get(k) for k in ("has_description", "has_og_title", "has_og_description")):
        missing.append(META)
    return missing


def _llms_prompt(site_url: str, brand_name: str, context: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "あなたはWebサイトの llms.txt を書く編集者です。"
                "llms.txt は、AIがサイトを理解するためにルート直下へ置くMarkdownファイルです。"
                "次の書式を厳守してください。\n"
                "1行目は `# サイト名`。\n"
                "2行目は空行、3行目に `> ` で始まる1文の要約。\n"
                "その後に `## セクション名` と `- [ページ名](URL): 説明` の箇条書き。\n"
                "本文に含まれない情報を創作しないこと。日本語で書くこと。"
                "Markdown以外の前置きや説明を出力しないこと。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"サイトURL: {site_url}\n"
                f"ブランド名: {brand_name}\n\n"
                f"--- ページ本文 ---\n{context[:MAX_CONTEXT_CHARS]}"
            ),
        },
    ]


def _jsonld_prompt(site_url: str, brand_name: str, context: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "あなたは構造化データを書く技術者です。"
                "schema.org の Organization と WebSite を1つの @graph にまとめた "
                "JSON-LD だけを出力してください。\n"
                "Organization には name, url, description, logo(あれば) を、"
                "WebSite には name, url, inLanguage を必ず入れること。\n"
                "本文から読み取れない値は入れないこと。"
                "JSON以外の文字（説明・コードフェンス）を出力しないこと。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"サイトURL: {site_url}\n"
                f"ブランド名: {brand_name}\n\n"
                f"--- ページ本文 ---\n{context[:MAX_CONTEXT_CHARS]}"
            ),
        },
    ]


def _meta_prompt(site_url: str, brand_name: str, context: str) -> list[dict[str, str]]:
    """メタ情報の文面だけをLLMに書かせる。タグの組み立ては seo.create_metadata が行う。

    文面（何と書くか）は本文を読んで決める必要があるが、タグの並べ方は
    決まりきっている。決まっている方を生成に任せると、抜けや綴り間違いが
    そのまま顧客サイトに乗る。
    """
    return [
        {
            "role": "system",
            "content": (
                "あなたはWebサイトのメタ情報を書く編集者です。"
                "次のJSONだけを出力してください。\n"
                '{"title": "...", "description": "..."}\n'
                "title は30文字以内で、そのページが何かが分かる日本語。\n"
                "description は60〜120文字で、ページ内容を端的に要約した日本語。\n"
                "本文に含まれない情報を創作しないこと。"
                "JSON以外の文字（説明・コードフェンス）を出力しないこと。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"サイトURL: {site_url}\n"
                f"ブランド名: {brand_name}\n\n"
                f"--- ページ本文 ---\n{context[:MAX_CONTEXT_CHARS]}"
            ),
        },
    ]


def _strip_fence(text: str) -> str:
    """```json ... ``` のコードフェンスを外す。モデルが付けがちなため。"""
    stripped = text.strip()
    match = re.match(r"^```[a-zA-Z]*\s*\n(.*?)\n?```$", stripped, re.S)
    return match.group(1).strip() if match else stripped


def _valid_jsonld(text: str) -> tuple[bool, str]:
    """JSON-LDとして成立しているか。壊れたまま渡すと設置しても効かない。"""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"JSONとして解釈できません: {exc.msg}"
    graph = data.get("@graph") if isinstance(data, dict) else None
    types = set()
    for node in (graph if isinstance(graph, list) else [data]):
        if isinstance(node, dict):
            node_type = node.get("@type")
            types.update(node_type if isinstance(node_type, list) else [node_type])
    missing = {"Organization", "WebSite"} - types
    if missing:
        return False, f"{' と '.join(sorted(missing))} が含まれていません"
    return True, ""


async def generate(
    site_url: str,
    brand_name: str,
    kinds: list[str],
    owner: str,
    *,
    paid: bool,
) -> dict[str, Any]:
    """不足していた成果物を生成する。無料枠はローカルGemma、課金はDeepSeek。"""
    if not monitor_service.configured(owner, paid=paid):
        raise RuntimeError("生成用のLLMが設定されていません")
    import asyncio

    context = await asyncio.to_thread(audit_service.fetch_site_context, site_url)
    artifacts: dict[str, Any] = {}
    provider = model = ""

    if LLMS_TXT in kinds:
        text, provider, model = await monitor_service.run_messages(
            _llms_prompt(site_url, brand_name, context), owner, paid=paid
        )
        artifacts[LLMS_TXT] = {
            "filename": "llms.txt",
            "content": _strip_fence(text),
            "placement": f"{site_url.rstrip('/')}/llms.txt としてサイトのルートに置きます。",
        }

    if JSON_LD in kinds:
        text, provider, model = await monitor_service.run_messages(
            _jsonld_prompt(site_url, brand_name, context), owner, paid=paid
        )
        body = _strip_fence(text)
        ok, reason = _valid_jsonld(body)
        artifacts[JSON_LD] = {
            "filename": "jsonld.html",
            # LLMの出力をそのまま <script> へ入れない。本文に `</script>` が
            # 混じるとタグが途中で閉じ、顧客サイトへ任意のHTMLが差し込める。
            "content": seo.json_ld_script(body),
            "valid": ok,
            "invalid_reason": reason,
            "placement": "各ページの <head> の中に貼り付けます。WordPressならテーマの head 追加欄、"
                         "CMSなら構造化データの設定欄に入れます。",
        }

    if META in kinds:
        text, provider, model = await monitor_service.run_messages(
            _meta_prompt(site_url, brand_name, context), owner, paid=paid
        )
        artifacts[META] = _build_meta_artifact(text, site_url, brand_name)

    return {"artifacts": artifacts, "provider": provider, "model": model}


def _build_meta_artifact(text: str, site_url: str, brand_name: str) -> dict[str, Any]:
    """LLMが書いた文面を、seo.create_metadata でタグに組み上げる。"""
    try:
        payload = json.loads(_strip_fence(text))
        content = seo.create_metadata(
            title=str(payload["title"]),
            description=str(payload["description"]),
            url=site_url,
            site_name=brand_name,
        )
        valid, reason = True, ""
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        content = ""
        valid, reason = False, f"メタ情報を組み立てられませんでした: {exc}"
    return {
        "filename": "meta.html",
        "content": content,
        "valid": valid,
        "invalid_reason": reason,
        "placement": "各ページの <head> の中に貼り付けます。既に同じ名前のタグがある場合は"
                     "置き換えてください。og:image は 1200×630 の画像URLを追記します。",
    }
