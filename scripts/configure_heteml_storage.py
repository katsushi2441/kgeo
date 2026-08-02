#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
PHP_CONFIG = ROOT / "public" / "kgeo_db_config.php"


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def php_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the private Heteml KGeo storage API")
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--user", required=True)
    args = parser.parse_args()

    password = getpass.getpass("Heteml database password: ")
    if not password:
        raise SystemExit("Database password is required")
    values = read_env()
    token = values.get("KGEO_STORAGE_API_TOKEN", "")
    if len(token) < 32:
        token = secrets.token_hex(32)
    values["KGEO_STORAGE_API_URL"] = "https://kurage.exbridge.jp/kgeo_store.php"
    values["KGEO_STORAGE_API_TOKEN"] = token
    values.pop("KGEO_DATABASE_URL", None)
    ENV_PATH.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    os.chmod(ENV_PATH, 0o600)

    php = """<?php
// Generated locally. Never commit or expose this file.
define('KGEO_DB_HOST', '%s');
define('KGEO_DB_NAME', '%s');
define('KGEO_DB_USER', '%s');
define('KGEO_DB_PASSWORD', '%s');
define('KGEO_STORAGE_TOKEN', '%s');
""" % tuple(php_quote(value) for value in (args.host, args.database, args.user, password, token))
    PHP_CONFIG.write_text(php, encoding="utf-8")
    os.chmod(PHP_CONFIG, 0o600)
    print("Heteml storage configuration created (secret values hidden).")


if __name__ == "__main__":
    main()
