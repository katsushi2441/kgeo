#!/usr/bin/env python3
"""Rotate the KGeo internal gateway token in ignored local configs."""

from __future__ import annotations

import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PHP_CONFIG = ROOT / "public" / "kgeo_config.php"


def main() -> int:
    token = secrets.token_hex(32)
    env = ENV_PATH.read_text(encoding="utf-8")
    env, env_count = re.subn(
        r"^KGEO_INTERNAL_TOKEN=.*$", f"KGEO_INTERNAL_TOKEN={token}", env, count=1, flags=re.MULTILINE
    )
    php = PHP_CONFIG.read_text(encoding="utf-8")
    php, php_count = re.subn(
        r"(define\('KGEO_API_TOKEN', getenv\('KGEO_API_TOKEN'\) \?: ')[^']+('\);)",
        rf"\g<1>{token}\2",
        php,
        count=1,
    )
    if env_count != 1 or php_count != 1:
        raise SystemExit("internal token definitions were not found")
    ENV_PATH.write_text(env, encoding="utf-8")
    PHP_CONFIG.write_text(php, encoding="utf-8")
    ENV_PATH.chmod(0o600)
    PHP_CONFIG.chmod(0o600)
    print("KGeo internal token rotated (value hidden).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
