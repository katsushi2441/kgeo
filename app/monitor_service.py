from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from . import config

URL_RE = re.compile(r"https?://[^\s\]\[()<>{}\"']+")


def normalize_owner(owner: str) -> str:
    return owner.strip().lstrip("@").lower()


def provider_for(owner: str) -> str:
    return "ollama" if normalize_owner(owner) in config.ADMIN_USERS else "deepseek"


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


def configured(owner: str) -> bool:
    if provider_for(owner) == "ollama":
        return bool(config.OLLAMA_BASE_URL and config.OLLAMA_MODEL)
    return bool(config.DEEPSEEK_BASE_URL and config.DEEPSEEK_MODEL and deepseek_api_key())


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


def _messages(prompt: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "あなたは一般利用者向けの検索回答アシスタントです。質問に日本語で答え、"
                "根拠として参照した公開WebページがあればURLを本文に記載してください。"
                "指定ブランドを無理に含めず、確認できる情報だけを述べてください。"
            ),
        },
        {"role": "user", "content": prompt},
    ]


async def _run_ollama(prompt: str) -> tuple[str, str, str]:
    payload = {
        "model": config.OLLAMA_MODEL,
        "messages": _messages(prompt),
        "stream": False,
        "think": False,
        "options": {"temperature": 0.2, "num_predict": 1600},
    }
    async with httpx.AsyncClient(timeout=config.OLLAMA_TIMEOUT) as client:
        response = await client.post(f"{config.OLLAMA_BASE_URL}/api/chat", json=payload)
        response.raise_for_status()
        body = response.json()
    text = str((body.get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError(f"Ollama returned an empty response ({body.get('done_reason', 'unknown')})")
    return text, "ollama-local", config.OLLAMA_MODEL


async def _run_deepseek(prompt: str) -> tuple[str, str, str]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {deepseek_api_key()}",
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": _messages(prompt),
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


async def run_prompt(prompt: str, brand_name: str, site_url: str, owner: str) -> dict:
    if not configured(owner):
        raise RuntimeError("AI検索モニタリング用LLMが設定されていません")
    if provider_for(owner) == "ollama":
        text, provider, model = await _run_ollama(prompt)
    else:
        text, provider, model = await _run_deepseek(prompt)
    analysis = analyze_response(text, brand_name, site_url)
    return {
        "provider": provider,
        "model": model,
        "response_text": text,
        "error": None,
        **analysis,
    }
