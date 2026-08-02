from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Any, Iterator, Mapping

from .config import DATABASE_URL, DB_PATH
from .models import SiteCreate, now_iso

SCHEMA_TEMPLATE = """
CREATE TABLE IF NOT EXISTS users (
    owner TEXT PRIMARY KEY,
    plan TEXT NOT NULL DEFAULT 'free',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sites (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL REFERENCES users(owner) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    brand_name TEXT NOT NULL,
    competitors_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sites_owner_updated ON sites(owner, updated_at DESC);
CREATE TABLE IF NOT EXISTS audits (
    id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    owner TEXT NOT NULL,
    score INTEGER NOT NULL,
    band TEXT NOT NULL,
    http_status INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    score_breakdown_json TEXT NOT NULL DEFAULT '{{}}',
    recommendations_ja_json TEXT NOT NULL DEFAULT '[]',
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audits_site_created ON audits(site_id, created_at DESC);
CREATE TABLE IF NOT EXISTS monitored_prompts (
    id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    owner TEXT NOT NULL,
    prompt TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prompts_site ON monitored_prompts(site_id, created_at DESC);
CREATE TABLE IF NOT EXISTS prompt_runs (
    id TEXT PRIMARY KEY,
    prompt_id TEXT NOT NULL REFERENCES monitored_prompts(id) ON DELETE CASCADE,
    owner TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    brand_mentioned INTEGER NOT NULL DEFAULT 0,
    domain_cited INTEGER NOT NULL DEFAULT 0,
    citation_rank INTEGER,
    cited_urls_json TEXT NOT NULL DEFAULT '[]',
    response_text TEXT NOT NULL DEFAULT '',
    evaluation_mode TEXT NOT NULL DEFAULT 'legacy-unverified',
    analysis_json TEXT NOT NULL DEFAULT '{{}}',
    error TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_runs_prompt_created ON prompt_runs(prompt_id, created_at DESC);
CREATE TABLE IF NOT EXISTS usage_events (
    id {usage_id_type},
    owner TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref_id TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_owner_kind_created ON usage_events(owner, kind, created_at);
"""


class DatabaseConnection:
    """Small SQL adapter that keeps the existing queries portable."""

    def __init__(self, raw: Any, postgres: bool) -> None:
        self.raw = raw
        self.postgres = postgres

    def execute(self, query: str, params: tuple | list = ()) -> Any:
        if self.postgres:
            query = query.replace("?", "%s")
        return self.raw.execute(query, params)

    def executescript(self, script: str) -> None:
        if not self.postgres:
            self.raw.executescript(script)
            return
        for statement in script.split(";"):
            if statement.strip():
                self.raw.execute(statement)


def using_postgres() -> bool:
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))


@contextmanager
def connect() -> Iterator[DatabaseConnection]:
    postgres = using_postgres()
    if postgres:
        from psycopg import connect as pg_connect
        from psycopg.rows import dict_row

        raw = pg_connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15)
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(DB_PATH, timeout=30)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
    conn = DatabaseConnection(raw, postgres)
    try:
        yield conn
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def init_db() -> None:
    with connect() as conn:
        schema = SCHEMA_TEMPLATE.format(
            usage_id_type="BIGSERIAL PRIMARY KEY"
            if conn.postgres
            else "INTEGER PRIMARY KEY AUTOINCREMENT"
        )
        conn.executescript(schema)
        if conn.postgres:
            columns = {
                row["column_name"]
                for row in conn.execute(
                    """SELECT column_name FROM information_schema.columns
                       WHERE table_schema='public' AND table_name='prompt_runs'"""
                )
            }
        else:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(prompt_runs)")}
        if "evaluation_mode" not in columns:
            conn.execute(
                "ALTER TABLE prompt_runs ADD COLUMN evaluation_mode TEXT NOT NULL DEFAULT 'legacy-unverified'"
            )
        if "analysis_json" not in columns:
            conn.execute("ALTER TABLE prompt_runs ADD COLUMN analysis_json TEXT NOT NULL DEFAULT '{}'")


def ensure_user(owner: str) -> None:
    with connect() as conn:
        if conn.postgres:
            conn.execute(
                """INSERT INTO users(owner, plan, created_at) VALUES (?, 'free', ?)
                   ON CONFLICT (owner) DO NOTHING""",
                (owner, now_iso()),
            )
        else:
            conn.execute(
                "INSERT OR IGNORE INTO users(owner, plan, created_at) VALUES (?, 'free', ?)",
                (owner, now_iso()),
            )


def get_plan(owner: str) -> str:
    ensure_user(owner)
    with connect() as conn:
        row = conn.execute("SELECT plan FROM users WHERE owner = ?", (owner,)).fetchone()
    return str(row["plan"])


def create_site(owner: str, payload: SiteCreate) -> dict:
    ensure_user(owner)
    site_id = uuid.uuid4().hex[:12]
    created = now_iso()
    with connect() as conn:
        conn.execute(
            """INSERT INTO sites
               (id, owner, name, url, brand_name, competitors_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (site_id, owner, payload.name, str(payload.url), payload.brand_name,
             json.dumps(payload.competitors, ensure_ascii=False), created, created),
        )
    return get_site(owner, site_id)


def _site_dict(row: Mapping[str, Any]) -> dict:
    item = dict(row)
    item["competitors"] = json.loads(item.pop("competitors_json"))
    return item


def list_sites(owner: str) -> list[dict]:
    ensure_user(owner)
    with connect() as conn:
        rows = conn.execute(
            """SELECT s.*,
                      (SELECT score FROM audits a WHERE a.site_id=s.id ORDER BY created_at DESC LIMIT 1) latest_score,
                      (SELECT band FROM audits a WHERE a.site_id=s.id ORDER BY created_at DESC LIMIT 1) latest_band
               FROM sites s WHERE owner=? ORDER BY updated_at DESC""",
            (owner,),
        ).fetchall()
    return [_site_dict(row) for row in rows]


def get_site(owner: str, site_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            """SELECT s.*,
                      (SELECT score FROM audits a WHERE a.site_id=s.id ORDER BY created_at DESC LIMIT 1) latest_score,
                      (SELECT band FROM audits a WHERE a.site_id=s.id ORDER BY created_at DESC LIMIT 1) latest_band
               FROM sites s WHERE s.id=? AND s.owner=?""",
            (site_id, owner),
        ).fetchone()
    return _site_dict(row) if row else None


def save_audit(owner: str, site_id: str, result: dict, recommendations_ja: list[str]) -> dict:
    audit_id = uuid.uuid4().hex[:12]
    created = now_iso()
    with connect() as conn:
        conn.execute(
            """INSERT INTO audits
               (id, site_id, owner, score, band, http_status, error, score_breakdown_json,
                recommendations_ja_json, result_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (audit_id, site_id, owner, int(result.get("score", 0)), str(result.get("band", "critical")),
             int(result.get("http_status", 0)), result.get("error"),
             json.dumps(result.get("score_breakdown", {}), ensure_ascii=False),
             json.dumps(recommendations_ja, ensure_ascii=False),
             json.dumps(result, ensure_ascii=False), created),
        )
        conn.execute("UPDATE sites SET updated_at=? WHERE id=? AND owner=?", (created, site_id, owner))
    add_usage(owner, "audit", audit_id)
    return get_audit(owner, audit_id)


def _audit_dict(row: Mapping[str, Any], detail: bool = True) -> dict:
    item = dict(row)
    item["score_breakdown"] = json.loads(item.pop("score_breakdown_json"))
    item["recommendations_ja"] = json.loads(item.pop("recommendations_ja_json"))
    raw = item.pop("result_json")
    if detail:
        item["result"] = json.loads(raw)
    return item


def get_audit(owner: str, audit_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM audits WHERE id=? AND owner=?", (audit_id, owner)).fetchone()
    return _audit_dict(row) if row else None


def list_audits(owner: str, site_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audits WHERE site_id=? AND owner=? ORDER BY created_at DESC LIMIT 50",
            (site_id, owner),
        ).fetchall()
    return [_audit_dict(row, detail=False) for row in rows]


def create_prompt(owner: str, site_id: str, prompt: str) -> dict:
    prompt_id = uuid.uuid4().hex[:12]
    created = now_iso()
    with connect() as conn:
        conn.execute(
            "INSERT INTO monitored_prompts(id, site_id, owner, prompt, created_at) VALUES (?, ?, ?, ?, ?)",
            (prompt_id, site_id, owner, prompt, created),
        )
    return get_prompt(owner, prompt_id)


def get_prompt(owner: str, prompt_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM monitored_prompts WHERE id=? AND owner=?", (prompt_id, owner)
        ).fetchone()
    if not row:
        return None
    item = dict(row)
    item["active"] = bool(item["active"])
    return item


def list_prompts(owner: str, site_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM monitored_prompts WHERE site_id=? AND owner=? ORDER BY created_at DESC",
            (site_id, owner),
        ).fetchall()
    return [{**dict(row), "active": bool(row["active"])} for row in rows]


def save_prompt_run(owner: str, prompt_id: str, result: dict) -> dict:
    run_id = uuid.uuid4().hex[:12]
    created = now_iso()
    with connect() as conn:
        conn.execute(
            """INSERT INTO prompt_runs
               (id, prompt_id, owner, provider, model, brand_mentioned, domain_cited,
                citation_rank, cited_urls_json, response_text, evaluation_mode, analysis_json,
                error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, prompt_id, owner, result["provider"], result["model"],
             int(result["brand_mentioned"]), int(result["domain_cited"]), result["citation_rank"],
             json.dumps(result["cited_urls"], ensure_ascii=False), result["response_text"],
             result.get("evaluation_mode", "legacy-unverified"),
             json.dumps(result.get("analysis", {}), ensure_ascii=False),
             result.get("error"), created),
        )
    add_usage(owner, "monitor", run_id)
    return get_prompt_run(owner, run_id)


def get_prompt_run(owner: str, run_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM prompt_runs WHERE id=? AND owner=?", (run_id, owner)).fetchone()
    if not row:
        return None
    item = dict(row)
    item["brand_mentioned"] = bool(item["brand_mentioned"])
    item["domain_cited"] = bool(item["domain_cited"])
    item["cited_urls"] = json.loads(item.pop("cited_urls_json"))
    item["analysis"] = json.loads(item.pop("analysis_json", "{}"))
    return item


def list_prompt_runs(owner: str, prompt_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM prompt_runs WHERE prompt_id=? AND owner=? ORDER BY created_at DESC LIMIT 50",
            (prompt_id, owner),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["brand_mentioned"] = bool(item["brand_mentioned"])
        item["domain_cited"] = bool(item["domain_cited"])
        item["cited_urls"] = json.loads(item.pop("cited_urls_json"))
        item["analysis"] = json.loads(item.pop("analysis_json", "{}"))
        items.append(item)
    return items


def add_usage(owner: str, kind: str, ref_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO usage_events(owner, kind, ref_id, created_at) VALUES (?, ?, ?, ?)",
            (owner, kind, ref_id, now_iso()),
        )


def monthly_usage(owner: str, kind: str, month: str) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) count FROM usage_events WHERE owner=? AND kind=? AND substr(created_at,1,7)=?",
            (owner, kind, month),
        ).fetchone()
    return int(row["count"])
