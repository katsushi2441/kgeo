#!/usr/bin/env python3
"""Update only the API endpoint in the ignored PHP runtime config."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "public" / "kgeo_config.php"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    args = parser.parse_args()
    parsed = urlparse(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"}:
        parser.error("a bare http(s) API origin is required")
    if not CONFIG.is_file():
        parser.error("public/kgeo_config.php is missing; run configure_runtime.py first")
    text = CONFIG.read_text(encoding="utf-8")
    updated, count = re.subn(
        r"(define\('KGEO_API_BASE', getenv\('KGEO_API_BASE'\) \?: ')[^']+('\);)",
        rf"\g<1>{args.url.rstrip('/')}\2",
        text,
        count=1,
    )
    if count != 1:
        parser.error("KGEO_API_BASE definition was not found")
    CONFIG.write_text(updated, encoding="utf-8")
    CONFIG.chmod(0o600)
    print("KGeo API endpoint updated (token hidden).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
