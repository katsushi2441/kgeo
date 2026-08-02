from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("KGEO_DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.environ.get("KGEO_DB", DATA_DIR / "kgeo.db"))
STATIC_DIR = ROOT / "static"

HOST = os.environ.get("KGEO_HOST", "127.0.0.1")
PORT = int(os.environ.get("KGEO_PORT", "18308"))
INTERNAL_TOKEN = os.environ.get("KGEO_INTERNAL_TOKEN", "")
DEV_USER = os.environ.get("KGEO_DEV_USER", "local")
ADMIN_USERS = {value.strip() for value in os.environ.get("KGEO_ADMIN_USERS", "").split(",") if value.strip()}

LLM_BASE_URL = os.environ.get("KGEO_LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.environ.get("KGEO_LLM_API_KEY", "")
LLM_MODEL = os.environ.get("KGEO_LLM_MODEL", "")
LLM_TIMEOUT = float(os.environ.get("KGEO_LLM_TIMEOUT", "90"))

FREE_AUDITS_PER_MONTH = int(os.environ.get("KGEO_FREE_AUDITS_PER_MONTH", "3"))
FREE_MONITOR_RUNS_PER_MONTH = int(os.environ.get("KGEO_FREE_MONITOR_RUNS_PER_MONTH", "5"))
MAX_SITES_PER_USER = int(os.environ.get("KGEO_MAX_SITES_PER_USER", "20"))
