#!/usr/bin/env python3
"""Copy the local KGeo SQLite database into Cloud SQL PostgreSQL."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from google.cloud.sql.connector import Connector, IPTypes

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SCHEMA_TEMPLATE  # noqa: E402

TABLES = (
    "users",
    "sites",
    "audits",
    "monitored_prompts",
    "prompt_runs",
    "usage_events",
)


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", default=os.getenv("KGEO_DB", "data/kgeo.db"))
    parser.add_argument("--instance", default=os.getenv("KGEO_CLOUD_SQL_INSTANCE", ""))
    parser.add_argument("--database", default=os.getenv("KGEO_CLOUD_SQL_DATABASE", "kgeo"))
    parser.add_argument("--user", default=os.getenv("KGEO_CLOUD_SQL_USER", "kgeo"))
    parser.add_argument("--private-ip", action="store_true")
    args = parser.parse_args()
    password = os.getenv("KGEO_CLOUD_SQL_PASSWORD", "")
    if not args.instance or not password:
        parser.error("KGEO_CLOUD_SQL_INSTANCE and KGEO_CLOUD_SQL_PASSWORD are required")

    sqlite_path = Path(args.sqlite).resolve()
    if not sqlite_path.is_file():
        parser.error(f"SQLite database not found: {sqlite_path}")
    source = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row

    connector = Connector(ip_type=IPTypes.PRIVATE if args.private_ip else IPTypes.PUBLIC)
    target = connector.connect(
        args.instance,
        "pg8000",
        user=args.user,
        password=password,
        db=args.database,
    )
    try:
        cursor = target.cursor()
        for statement in SCHEMA_TEMPLATE.format(
            usage_id_type="BIGSERIAL PRIMARY KEY"
        ).split(";"):
            if statement.strip():
                cursor.execute(statement)

        copied: dict[str, int] = {}
        for table in TABLES:
            names = columns(source, table)
            quoted = ", ".join(f'"{name}"' for name in names)
            placeholders = ", ".join(["%s"] * len(names))
            rows = source.execute(f'SELECT {quoted} FROM "{table}"').fetchall()
            for row in rows:
                cursor.execute(
                    f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders}) '
                    "ON CONFLICT DO NOTHING",
                    tuple(row[name] for name in names),
                )
            copied[table] = len(rows)

        cursor.execute(
            """SELECT setval(
                   pg_get_serial_sequence('usage_events', 'id'),
                   GREATEST(COALESCE((SELECT MAX(id) FROM usage_events), 1), 1),
                   true
               )"""
        )
        target.commit()

        for table, source_count in copied.items():
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            target_count = int(cursor.fetchone()[0])
            if target_count < source_count:
                raise RuntimeError(
                    f"migration verification failed: {table} source={source_count} target={target_count}"
                )
            print(f"{table}: source={source_count} target={target_count}")
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()
        connector.close()
        source.close()
    print("KGeo SQLite to Cloud SQL migration completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
