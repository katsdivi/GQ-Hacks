"""Recorder health from the local parquet backup: row counts and latest receipt time.

Counts only, by design: recorded games are mostly holdout data (kickoff >= 2026-08-01),
which stays write-only. No prices are read or printed.

Usage:
  python -m collector.health                 # all rows on disk
  python -m collector.health --minutes 30    # rows received in the last 30 minutes
  python -m collector.health --since 2026-10-03T03:00 --until 2026-10-03T03:30
  python -m collector.health --dir data/live_alden --minutes 30   # any recorder's live dir
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = ROOT / "data" / "live"


def load_meta(live_dir: Path = LIVE_DIR) -> pd.DataFrame:
    files = sorted(Path(live_dir).glob("*/*/*.parquet"))
    if not files:
        return pd.DataFrame(columns=["venue", "kind", "market_id", "recv_ns"])
    return pd.concat([pd.read_parquet(f, columns=["venue", "kind", "market_id", "recv_ns"]) for f in files],
                     ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float)
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--dir", type=Path, default=LIVE_DIR,
                    help="live dir to read (default data/live; e.g. data/live_<recorder-id>)")
    a = ap.parse_args()
    if not a.dir.is_dir():
        print(f"no such live dir: {a.dir}")
        return
    df = load_meta(a.dir)
    recv = pd.to_datetime(df["recv_ns"], utc=True)
    if a.minutes:
        lo = pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=a.minutes)
        df, recv = df[recv >= lo], recv[recv >= lo]
    if a.since:
        lo = pd.Timestamp(a.since, tz="UTC")
        df, recv = df[recv >= lo], recv[recv >= lo]
    if a.until:
        hi = pd.Timestamp(a.until, tz="UTC")
        df, recv = df[recv < hi], recv[recv < hi]
    if df.empty:
        print("no rows in window")
        return
    g = df.assign(recv=recv).groupby(["venue", "kind"]).agg(rows=("kind", "size"), markets=("market_id", "nunique"),
                                                            first_recv=("recv", "min"), last_recv=("recv", "max"))
    print(g.to_string())
    per_min = pd.Series(1, index=recv).resample("1min").size()
    print(f"minutes with zero rows: {(per_min == 0).sum()} of {len(per_min)}")


if __name__ == "__main__":
    main()
