"""Tiger Data (Timescale) store for live ticks.

Table (created by `ensure_schema`, safe to run repeatedly):
  ticks(ts TIMESTAMPTZ, ts_ns BIGINT, venue, market_id, kind, price DOUBLE PRECISION,
        size DOUBLE PRECISION, side), hypertable on ts. ts_ns keeps nanoseconds because
        Postgres timestamps stop at microseconds.

Connection string comes from TIGER_DATABASE_URL in .env
(postgres://tsdbadmin:<password>@<host>:<port>/tsdb?sslmode=require).

Usage:
  python -m store.timescale init      # create table + hypertable + index
  python -m store.timescale health    # SELECT venue, count(*), max(ts) FROM ticks GROUP BY venue
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

COLS = ("ts", "ts_ns", "venue", "market_id", "kind", "price", "size", "side")

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticks (
  ts TIMESTAMPTZ NOT NULL, ts_ns BIGINT NOT NULL, venue TEXT NOT NULL,
  market_id TEXT NOT NULL, kind TEXT NOT NULL, price DOUBLE PRECISION,
  size DOUBLE PRECISION, side TEXT
);
SELECT create_hypertable('ticks', by_range('ts'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ticks_venue_market_ts ON ticks (venue, market_id, ts DESC);
"""


def configured() -> bool:
    return bool(os.getenv("TIGER_DATABASE_URL"))


def connect():
    import psycopg
    url = os.getenv("TIGER_DATABASE_URL")
    if not url:
        raise RuntimeError("TIGER_DATABASE_URL missing from .env")
    return psycopg.connect(url, autocommit=True, connect_timeout=10)


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        for stmt in [s.strip() for s in SCHEMA.split(";") if s.strip()]:
            cur.execute(stmt)


def write_rows(conn, rows: list[tuple]) -> int:
    """COPY rows into ticks. Each row: (ts_ns, venue, market_id, kind, price, size, side)."""
    if not rows:
        return 0
    from datetime import datetime, timezone
    with conn.cursor() as cur:
        with cur.copy(f"COPY ticks ({', '.join(COLS)}) FROM STDIN") as cp:
            for ts_ns, venue, market_id, kind, price, size, side in rows:
                ts = datetime.fromtimestamp(ts_ns / 1e9, tz=timezone.utc)
                cp.write_row((ts, int(ts_ns), venue, market_id, kind, price, size, side))
    return len(rows)


def latest_per_venue(conn) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute("SELECT venue, count(*), max(ts) FROM ticks GROUP BY venue ORDER BY venue")
        return cur.fetchall()


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "health"
    with connect() as conn:
        if cmd == "init":
            ensure_schema(conn)
            print("ticks table ready")
        for venue, n, mx in latest_per_venue(conn):
            print(f"{venue:10} {n:>12,}  max(ts) {mx}")


if __name__ == "__main__":
    main()
