#!/usr/bin/env python3
"""Provision a dedicated operate token for KGeo without printing it."""

from __future__ import annotations

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KGEO_ENV = ROOT / ".env"
RQDB_ENV = ROOT.parent / "rqdb4ai" / "rqdb4ai.env"
RQDB_WORKER_LAUNCHER = ROOT.parent / "rqdb4ai" / "run_worker_with_aixec_env.sh"
FUNCTION = "kgeo.jobs.ollama_chat_job"
KGEO_PYTHONPATH = "/home/kojima/work/kgeo"


def read_env(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return lines, values


def update_env(path: Path, changes: dict[str, str]) -> None:
    lines, _ = read_env(path)
    pending = dict(changes)
    updated: list[str] = []
    for line in lines:
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in pending:
                updated.append(f"{key}={pending.pop(key)}")
                continue
        updated.append(line)
    if pending:
        if updated and updated[-1]:
            updated.append("")
        updated.extend(f"{key}={value}" for key, value in pending.items())
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    path.chmod(0o600)


def add_csv(existing: str, value: str) -> str:
    items = [item.strip() for item in existing.split(",") if item.strip()]
    if value not in items:
        items.append(value)
    return ",".join(items)


def main() -> int:
    if not KGEO_ENV.is_file() or not RQDB_ENV.is_file():
        raise SystemExit("KGeo or RQDB4AI environment file is missing")
    _, kgeo = read_env(KGEO_ENV)
    _, rqdb = read_env(RQDB_ENV)
    token = kgeo.get("KGEO_RQDB4AI_TOKEN", "")
    if len(token) < 32:
        token = secrets.token_hex(32)
    update_env(
        KGEO_ENV,
        {
            "KGEO_RQDB4AI_URL": "http://127.0.0.1:18300",
            "KGEO_RQDB4AI_TOKEN": token,
            "KGEO_RQDB4AI_FUNCTION": FUNCTION,
            "KGEO_RQDB4AI_POLL_INTERVAL": "2",
            "KGEO_RQDB4AI_WAIT_TIMEOUT": "300",
            "KGEO_OLLAMA_BASE_URL": "http://192.168.0.14:11434",
            "KGEO_OLLAMA_MODEL": "gemma4:12b-it-qat",
        },
    )
    update_env(
        RQDB_ENV,
        {
            "RQDB4AI_OPERATE_TOKEN": add_csv(rqdb.get("RQDB4AI_OPERATE_TOKEN", ""), token),
            "RQDB4AI_OPERATE_ENQUEUE_FUNCTIONS": add_csv(
                rqdb.get("RQDB4AI_OPERATE_ENQUEUE_FUNCTIONS", ""), FUNCTION
            ),
        },
    )
    if RQDB_WORKER_LAUNCHER.is_file():
        launcher = RQDB_WORKER_LAUNCHER.read_text(encoding="utf-8")
        if KGEO_PYTHONPATH not in launcher:
            updated = launcher.replace(":/tmp", f":{KGEO_PYTHONPATH}:/tmp", 1)
            if updated == launcher:
                raise SystemExit("RQDB4AI worker PYTHONPATH could not be updated")
            RQDB_WORKER_LAUNCHER.write_text(updated, encoding="utf-8")
            RQDB_WORKER_LAUNCHER.chmod(0o755)
    print("Dedicated KGeo RQDB4AI access configured (token hidden).")
    print("Restart rqdb4ai-api.service and rqdb4ai-web-worker.service to apply it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
