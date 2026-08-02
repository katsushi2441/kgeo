#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import config, remote_store  # noqa: E402

TABLES = ("users", "sites", "audits", "monitored_prompts", "prompt_runs", "usage_events")


def main() -> None:
    if not remote_store.enabled():
        raise SystemExit("KGEO_STORAGE_API_URL and KGEO_STORAGE_API_TOKEN are required")
    connection = sqlite3.connect(config.DB_PATH)
    connection.row_factory = sqlite3.Row
    tables = {
        table: [dict(row) for row in connection.execute(f"SELECT * FROM {table}")]
        for table in TABLES
    }
    connection.close()
    source_counts = {table: len(rows) for table, rows in tables.items()}
    target_counts = {}
    for table, rows in tables.items():
        document = json.dumps(
            {"tables": {table: rows}}, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        target_counts = remote_store.call(
            "import_snapshot_b64", {"data": base64.b64encode(document).decode("ascii")}
        )
    for table, count in source_counts.items():
        if int(target_counts.get(table, -1)) != count:
            raise RuntimeError(
                f"Migration count mismatch for {table}: source={count} target={target_counts.get(table)}"
            )
        print(f"{table}: source={count} target={target_counts[table]}")
    print("KGeo SQLite to Heteml MySQL migration completed.")


if __name__ == "__main__":
    main()
