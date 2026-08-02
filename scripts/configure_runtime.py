#!/usr/bin/env python3
"""Create local runtime secrets without printing or committing them."""

from __future__ import annotations

import os
import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PHP_CONFIG = ROOT / "public" / "kgeo_config.php"


def read_values() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


values = read_values()
token = values.get("KGEO_INTERNAL_TOKEN", "")
if len(token) < 32:
    token = secrets.token_hex(32)
defaults = {
    "KGEO_HOST": "0.0.0.0",
    "KGEO_PORT": "18308",
    "KGEO_INTERNAL_TOKEN": token,
    "KGEO_DEV_USER": "local",
    "KGEO_DB": str(ROOT / "data" / "kgeo.db"),
    "KGEO_ADMIN_USERS": "xb_bittensor",
    "KGEO_RQDB4AI_URL": "http://127.0.0.1:18300",
    "KGEO_RQDB4AI_TOKEN": "",
    "KGEO_RQDB4AI_FUNCTION": "kgeo.jobs.ollama_chat_job",
    "KGEO_RQDB4AI_POLL_INTERVAL": "2",
    "KGEO_RQDB4AI_WAIT_TIMEOUT": "300",
    "KGEO_OLLAMA_BASE_URL": "http://192.168.0.14:11434",
    "KGEO_OLLAMA_MODEL": "gemma4:12b-it-qat",
    "KGEO_FREE_MONITOR_RUNS_PER_MONTH": "5",
    "KGEO_MAX_SITES_PER_USER": "20",
}
for key, value in defaults.items():
    values.setdefault(key, value)
ENV_PATH.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
os.chmod(ENV_PATH, 0o600)

if PHP_CONFIG.exists():
    php = PHP_CONFIG.read_text(encoding="utf-8")
    php, count = re.subn(
        r"(define\('KGEO_API_TOKEN', getenv\('KGEO_API_TOKEN'\) \?: ')[^']+('\);)",
        rf"\g<1>{token}\2",
        php,
        count=1,
    )
    if count != 1:
        raise SystemExit("KGEO_API_TOKEN definition was not found")
    PHP_CONFIG.write_text(php, encoding="utf-8")
else:
    php = f"""<?php
// Generated locally by scripts/configure_runtime.py. Never commit this file.
define('KGEO_API_BASE', getenv('KGEO_API_BASE') ?: 'http://exbridge.ddns.net:18308');
define('KGEO_API_TOKEN', getenv('KGEO_API_TOKEN') ?: '{token}');
"""
    PHP_CONFIG.write_text(php, encoding="utf-8")
os.chmod(PHP_CONFIG, 0o600)
print("Runtime configuration created (secret values hidden).")
