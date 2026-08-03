from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import httpx

from . import audit_service, config, rqdb4ai_client

URL_RE = re.compile(r"https?://[^\s\]\[()<>{}\"']+")


def normalize_owner(owner: str) -> str:
    return owner.strip().lstrip("@").lower()


def provider_for(owner: str, *, paid: bool = True) -> str:
    """この1回の実行にどのLLMを使うか。

    無料枠の実行は自社GPUのGemmaで賄い、課金された実行だけホスト型の
    DeepSeekを使う。無料枠でDeepSeekを呼ぶとAPI原価がそのまま赤字になり、
    ローカルGPUを持っている利点も消える(2026-08-04にユーザー指摘で判明)。

    管理者は常にGemma(無料・内部利用)。有料レールはDeepSeekという
    ワークスペース方針は「課金された実行」に対して適用する。
    """
    if normalize_owner(owner) in config.ADMIN_USERS:
        return "ollama"
    return "deepseek" if paid else "ollama"


def _read_key_file(path: str, name: str) -> str:
    if not path:
        return ""
    try:
        for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == name:
                return value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def deepseek_api_key() -> str:
    return config.DEEPSEEK_API_KEY or _read_key_file(
        config.DEEPSEEK_API_KEY_FILE, config.DEEPSEEK_API_KEY_NAME
    )


def configured(owner: str, *, paid: bool = True) -> bool:
    if provider_for(owner, paid=paid) == "ollama":
        return rqdb4ai_client.configured()
    return bool(config.DEEPSEEK_BASE_URL and config.DEEPSEEK_MODEL and deepseek_api_key())


def analyze_response(
    text: str, brand_name: str, site_url: str, brand_aliases: list[str] | None = None
) -> dict:
    urls = [value.rstrip(".,、。") for value in URL_RE.findall(text)]
    urls = list(dict.fromkeys(urls))
    domain = (urlparse(site_url).hostname or "").lower().removeprefix("www.")
    matching = [url for url in urls if (urlparse(url).hostname or "").lower().removeprefix("www.") == domain]
    rank = urls.index(matching[0]) + 1 if matching else None
    normalized_text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).casefold())
    aliases = [brand_name, *(brand_aliases or [])]
    normalized_aliases = [
        re.sub(r"\s+", "", unicodedata.normalize("NFKC", alias).casefold())
        for alias in aliases
        if alias.strip()
    ]
    matched_alias = next((alias for alias in normalized_aliases if alias in normalized_text), "")
    return {
        "brand_mentioned": bool(matched_alias),
        "domain_cited": bool(matching),
        "citation_rank": rank,
        "cited_urls": urls[:30],
    }


async def run_messages(
    messages: list[dict[str, str]], owner: str, *, paid: bool
) -> tuple[str, str, str]:
    """任意のメッセージ列を、無料枠/課金に応じたLLMで実行する。

    monitorの回答シミュレーション以外(llms.txt・JSON-LDの生成など)からも
    同じ出し分けを使うために切り出した。
    """
    if provider_for(owner, paid=paid) == "ollama":
        return await _run_ollama(messages)
    return await _run_deepseek(messages)


def _messages(prompt: str, brand_name: str, site_url: str, site_context: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "あなたは日本語AEO（回答エンジン最適化）の評価者です。"
                "与えられた対象ページ本文だけを根拠に質問へ回答し、ページが質問へどの程度"
                "答えられるかを評価してください。本文にない事実を補わないでください。"
                "必ずJSONのみを返し、answerability_scoreは0〜100の整数にしてください。"
                "形式: {\"answer\":\"回答\",\"answerability_score\":0,"
                "\"supported_points\":[\"本文で確認できる根拠\"],"
                "\"missing_information\":[\"不足情報\"],"
                "\"improvement_suggestions\":[\"具体的改善案\"]}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"質問: {prompt}\n対象ブランド: {brand_name}\n対象URL: {site_url}\n\n"
                f"対象ページ本文:\n---\n{site_context}\n---"
            ),
        },
    ]


async def _run_ollama(messages: list[dict[str, str]]) -> tuple[str, str, str]:
    text, _job_id = await rqdb4ai_client.run_ollama_chat(messages)
    return text, "ollama-rqdb4ai", config.OLLAMA_MODEL


async def _run_deepseek(messages: list[dict[str, str]]) -> tuple[str, str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {deepseek_api_key()}",
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2048,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=config.DEEPSEEK_TIMEOUT) as client:
        response = await client.post(
            f"{config.DEEPSEEK_BASE_URL}/chat/completions", headers=headers, json=payload
        )
        response.raise_for_status()
        body = response.json()
    choice = (body.get("choices") or [{}])[0]
    text = str((choice.get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError(
            f"DeepSeek returned an empty response ({choice.get('finish_reason', 'unknown')})"
        )
    return text, "deepseek", config.DEEPSEEK_MODEL


def _parse_evaluation(text: str, site_url: str, content_chars: int) -> tuple[str, dict]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    try:
        body = json.loads(cleaned[start : end + 1]) if start >= 0 and end > start else {}
    except json.JSONDecodeError:
        body = {}
    answer = str(body.get("answer") or text).strip()
    try:
        answerability_score = max(0, min(100, int(body.get("answerability_score") or 0)))
    except (TypeError, ValueError):
        answerability_score = 0

    def string_list(name: str) -> list[str]:
        value = body.get(name)
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()][:10]

    analysis = {
        "evaluation_mode": "grounded-site-simulation",
        "answerability_score": answerability_score,
        "supported_points": string_list("supported_points"),
        "missing_information": string_list("missing_information"),
        "improvement_suggestions": string_list("improvement_suggestions"),
        "source_url": site_url,
        "source_content_chars": content_chars,
        "notice": "対象ページ本文を与えたLLMシミュレーションであり、外部AI検索での掲載結果ではありません。",
        "structured_response": bool(body),
    }
    return answer, analysis


async def run_prompt(
    prompt: str,
    brand_name: str,
    site_url: str,
    owner: str,
    brand_aliases: list[str] | None = None,
    *,
    paid: bool = True,
) -> dict:
    if not configured(owner, paid=paid):
        raise RuntimeError("AI検索モニタリング用LLMが設定されていません")
    site_context = await asyncio.to_thread(audit_service.fetch_site_context, site_url)
    messages = _messages(prompt, brand_name, site_url, site_context)
    if provider_for(owner, paid=paid) == "ollama":
        text, provider, model = await _run_ollama(messages)
    else:
        text, provider, model = await _run_deepseek(messages)
    answer, evaluation = _parse_evaluation(text, site_url, len(site_context))
    analysis = analyze_response(answer, brand_name, site_url, brand_aliases)
    return {
        "provider": provider,
        "model": model,
        "response_text": answer,
        "evaluation_mode": "grounded-site-simulation",
        "analysis": evaluation,
        "error": None,
        **analysis,
    }
