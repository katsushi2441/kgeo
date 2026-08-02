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
_admin_users = os.environ.get("KGEO_ADMIN_USERS", "").strip() or "xb_bittensor"
ADMIN_USERS = {
    value.strip().lstrip("@").lower() for value in _admin_users.split(",") if value.strip()
}

# The operator account uses the local Ollama host. Other users use DeepSeek so
# public traffic cannot occupy the operator's GPU indefinitely.
OLLAMA_BASE_URL = (
    os.environ.get("KGEO_OLLAMA_BASE_URL", "").strip() or "http://127.0.0.1:11434"
).rstrip("/")
OLLAMA_MODEL = os.environ.get("KGEO_OLLAMA_MODEL", "").strip() or "gemma4:12b-it-qat"
OLLAMA_TIMEOUT = float(os.environ.get("KGEO_OLLAMA_TIMEOUT", "180"))

DEEPSEEK_BASE_URL = (
    os.environ.get("KGEO_DEEPSEEK_BASE_URL", "").strip()
    or os.environ.get("KGEO_LLM_BASE_URL", "").strip()
    or "https://api.deepseek.com"
).rstrip("/")
DEEPSEEK_API_KEY = (
    os.environ.get("KGEO_DEEPSEEK_API_KEY", "").strip()
    or os.environ.get("KGEO_LLM_API_KEY", "").strip()
)
DEEPSEEK_API_KEY_FILE = os.environ.get("KGEO_DEEPSEEK_API_KEY_FILE", "").strip()
DEEPSEEK_API_KEY_NAME = (
    os.environ.get("KGEO_DEEPSEEK_API_KEY_NAME", "").strip() or "DEEPSEEK_API_KEY"
)
DEEPSEEK_MODEL = (
    os.environ.get("KGEO_DEEPSEEK_MODEL", "").strip()
    or os.environ.get("KGEO_LLM_MODEL", "").strip()
    or "deepseek-v4-flash"
)
DEEPSEEK_TIMEOUT = float(
    os.environ.get("KGEO_DEEPSEEK_TIMEOUT", "")
    or os.environ.get("KGEO_LLM_TIMEOUT", "")
    or "180"
)

FREE_AUDITS_PER_MONTH = int(os.environ.get("KGEO_FREE_AUDITS_PER_MONTH", "3"))
FREE_MONITOR_RUNS_PER_MONTH = int(os.environ.get("KGEO_FREE_MONITOR_RUNS_PER_MONTH", "5"))
MAX_SITES_PER_USER = int(os.environ.get("KGEO_MAX_SITES_PER_USER", "20"))
