from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from . import config

URL_RE = re.compile(r"https?://[^\s\]\[()<>{}\"']+")


def configured() -> bool:
    return bool(config.LLM_BASE_URL and config.LLM_MODEL)


def analyze_response(text: str, brand_name: str, site_url: str) -> dict:
    urls = [value.rstrip(".,、。") for value in URL_RE.findall(text)]
    urls = list(dict.fromkeys(urls))
    domain = (urlparse(site_url).hostname or "").lower().removeprefix("www.")
    matching = [url for url in urls if (urlparse(url).hostname or "").lower().removeprefix("www.") == domain]
    rank = urls.index(matching[0]) + 1 if matching else None
    return {
        "brand_mentioned": brand_name.casefold() in text.casefold(),
        "domain_cited": bool(matching),
        "citation_rank": rank,
        "cited_urls": urls[:30],
    }


async def run_prompt(prompt: str, brand_name: str, site_url: str) -> dict:
    if not configured():
        raise RuntimeError("AI検索モニタリング用LLMが設定されていません")
    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    payload = {
        "model": config.LLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "あなたは一般利用者向けの検索回答アシスタントです。質問に日本語で答え、"
                    "根拠として参照した公開WebページがあればURLを本文に記載してください。"
                    "指定ブランドを無理に含めず、確認できる情報だけを述べてください。"
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=config.LLM_TIMEOUT) as client:
        response = await client.post(f"{config.LLM_BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
    text = body["choices"][0]["message"]["content"]
    analysis = analyze_response(text, brand_name, site_url)
    return {
        "provider": urlparse(config.LLM_BASE_URL).hostname or "openai-compatible",
        "model": config.LLM_MODEL,
        "response_text": text,
        "error": None,
        **analysis,
    }
