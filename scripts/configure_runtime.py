#!/usr/bin/env python3
"""Create local runtime secrets without printing or committing them."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PHP_CONFIG = ROOT / "public" / "kgeo_config.php"


def existing_token() -> str | None:
    if not ENV_PATH.exists():
        return None
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("KGEO_INTERNAL_TOKEN="):
            value = line.split("=", 1)[1].strip()
            if len(value) >= 32:
                return value
    return None


token = existing_token() or secrets.token_hex(32)
env = f"""KGEO_HOST=0.0.0.0
KGEO_PORT=18308
KGEO_INTERNAL_TOKEN={token}
KGEO_DEV_USER=local
KGEO_DB={ROOT / 'data' / 'kgeo.db'}
KGEO_LLM_BASE_URL=
KGEO_LLM_API_KEY=
KGEO_LLM_MODEL=
KGEO_LLM_TIMEOUT=90
KGEO_FREE_AUDITS_PER_MONTH=3
KGEO_FREE_MONITOR_RUNS_PER_MONTH=5
KGEO_MAX_SITES_PER_USER=20
"""
ENV_PATH.write_text(env, encoding="utf-8")
os.chmod(ENV_PATH, 0o600)

php = f"""<?php
// Generated locally by scripts/configure_runtime.py. Never commit this file.
define('KGEO_API_BASE', getenv('KGEO_API_BASE') ?: 'http://exbridge.ddns.net:18308');
define('KGEO_API_TOKEN', getenv('KGEO_API_TOKEN') ?: '{token}');
"""
PHP_CONFIG.write_text(php, encoding="utf-8")
os.chmod(PHP_CONFIG, 0o600)
print("Runtime configuration created (secret values hidden).")
