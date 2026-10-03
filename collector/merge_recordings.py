"""Merge two or more live recorder output dirs into one, keeping every recorder's receipt time.

Inputs are recorder dirs as written by `python -m collector.run`:
  <input>/<venue>/<YYYYMMDD>/<unix_s>_<pid>.parquet
  columns ts, venue, market_id, kind, price, size, side, recv_ns
  (+ src_ts_ns, tx_hash on polymarket trades)

Output, one file per venue per UTC date of `ts`:
  <out>/<venue>/<YYYYMMDD>.parquet
  columns ts, venue, market_id, kind, price, size, side,
          recv_ns_<label> (one per input, null when that input missed the row),
          src_ts_ns, tx_hash (when any input has them; first non-null in --inputs order),
          sources (comma list of the labels that saw the row, in --inputs order)
  sorted by (ts, kind, market_id), stable. label = the input dir's name (data/live -> live,
  data/live_alden -> live_alden) unless --labels is given.

Dedupe key: (venue, market_id, ts, kind, price, size). Rows are paired, not collapsed: inside
each input, rows with the same key are numbered in receipt order (0, 1, 2, ...) and the n-th
copy in one input matches the n-th copy in another. So two real trades that happen to share
ts, price and size (one taker filling two makers) both survive, and a recorder that saw a row
twice (for example a Kalshi trade re-fetched by the restart backfill, which has no trade id
to drop it) keeps both copies, one of which will show up as "only in" that recorder.

What dedupes in practice:
  * trades: ts is the venue's own time (Kalshi created_time, polymarket.com event timestamp),
    so the same trade seen by two recorders has the same key and merges into one row with
    both recv_ns columns filled.
  * book rows (kind bid / ask): ts is the recorder's receipt time, so two recorders almost
    never produce the same key. Both copies are kept, each with only its own recv_ns column.
    Filter on `sources` (or pick one recorder's book rows) before using books from the merge.

Holdout rule: most recorded games are sealed test data. This script reads and writes rows but
prints counts only (rows only in each input, rows in 2+ inputs, total). It never prints prices
or any summary statistic of prices.

Usage:
  python -m collector.merge_recordings --inputs data/live data/live_alden --out data/live_merged
  python -m collector.merge_recordings --inputs data/live data/live_alden --labels divi alden --out data/live_merged
"""
from __future__ import annotations

import argparse
import re
from functools import reduce
from pathlib import Path

import pandas as pd

KEY = ["venue", "market_id", "ts", "kind", "price", "size"]
SHARED = ["ts", "venue", "market_id", "kind", "price", "size", "side"]
EXTRA = ["src_ts_ns", "tx_hash"]
TYPES = {"ts": "int64", "venue": "string", "market_id": "string", "kind": "string", "price": "float64",
         "size": "float64", "side": "string", "recv_ns": "Int64", "src_ts_ns": "Int64", "tx_hash": "string"}
SORT = ["ts", "kind", "market_id"]


def venues_in(d: Path) -> set[str]:
    return {p.name for p in d.iterdir() if p.is_dir() and any(p.glob("*/*.parquet"))} if d.is_dir() else set()


def load_venue(d: Path, venue: str) -> pd.DataFrame:
    """All chunks for one venue from one recorder dir, typed, in receipt order (stable)."""
    files = sorted((d / venue).glob("*/*.parquet"))
    cols = SHARED + ["recv_ns"] + EXTRA
    if not files:
        return pd.DataFrame({c: pd.Series(dtype=TYPES[c]) for c in cols})
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[cols].astype(TYPES)
    return df.sort_values("recv_ns", kind="stable").reset_index(drop=True)


def merge_venue(frames: list[pd.DataFrame], labels: list[str]) -> pd.DataFrame:
    """Outer-join one venue's rows across recorders on KEY + occurrence number."""
    parts = []
    for df, lab in zip(frames, labels):
        p = df.copy()
        p["_occ"] = p.groupby(KEY, dropna=False, sort=False).cumcount()
        p = p.rename(columns={"recv_ns": f"recv_ns_{lab}", "side": f"side_{lab}",
                              "src_ts_ns": f"src_ts_ns_{lab}", "tx_hash": f"tx_hash_{lab}"})
        parts.append(p)
    on = KEY + ["_occ"]
    m = reduce(lambda a, b: a.merge(b, on=on, how="outer", sort=False), parts)
    out = m[KEY].copy()

    def first_non_null(col: str) -> pd.Series:
        return reduce(lambda a, b: a.combine_first(b), [m[f"{col}_{lab}"] for lab in labels])

    out["side"] = first_non_null("side")
    for lab in labels:
        out[f"recv_ns_{lab}"] = m[f"recv_ns_{lab}"]
    has_extra = any(df[c].notna().any() for df in frames for c in EXTRA)
    if has_extra:
        for c in EXTRA:
            out[c] = first_non_null(c)
    seen = pd.DataFrame({lab: m[f"recv_ns_{lab}"].notna() for lab in labels})
    out["sources"] = seen.apply(lambda r: ",".join(lab for lab in labels if r[lab]), axis=1) if len(seen) else ""
    types = {**{c: TYPES[c] for c in SHARED}, **{f"recv_ns_{lab}": "Int64" for lab in labels}, "sources": "string"}
    if has_extra:
        types.update({c: TYPES[c] for c in EXTRA})
    out = out[SHARED + [f"recv_ns_{lab}" for lab in labels] + (EXTRA if has_extra else []) + ["sources"]]
    out = out.astype(types)
    return out.sort_values(SORT, kind="stable").reset_index(drop=True)


def write_venue(out: pd.DataFrame, out_dir: Path, venue: str) -> int:
    d = out_dir / venue
    d.mkdir(parents=True, exist_ok=True)
    date = pd.to_datetime(out["ts"], unit="ns", utc=True).dt.strftime("%Y%m%d")
    n = 0
    for day in sorted(date.unique()):
        out[date == day].reset_index(drop=True).to_parquet(d / f"{day}.parquet", index=False)
        n += 1
    return n


def merge(inputs: list[Path], out_dir: Path, labels: list[str] | None = None) -> dict[str, dict]:
    """Merge recorder dirs into out_dir. Returns counts per venue (no prices)."""
    labels = labels or [Path(p).resolve().name for p in inputs]
    labels = [re.sub(r"[^A-Za-z0-9_]", "_", lab) for lab in labels]
    if len(labels) != len(inputs):
        raise SystemExit("--labels must have one label per input")
    if len(set(labels)) != len(labels):
        raise SystemExit(f"duplicate input labels {labels}; pass --labels to name them apart")
    out_res = Path(out_dir).resolve()
    for p in inputs:
        if Path(p).resolve() == out_res:
            raise SystemExit(f"--out must differ from every input ({p})")
    venues = sorted(set().union(*(venues_in(Path(p)) for p in inputs)))
    counts: dict[str, dict] = {}
    for v in venues:
        frames = [load_venue(Path(p), v) for p in inputs]
        out = merge_venue(frames, labels)
        n_src = out["sources"].str.count(",") + 1
        c = {f"only_{lab}": int(((out["sources"] == lab)).sum()) for lab in labels}
        c["in_2plus"] = int((n_src >= 2).sum())
        if len(labels) > 2:
            c["in_all"] = int((n_src == len(labels)).sum())
        c["total"] = len(out)
        c["files"] = write_venue(out, Path(out_dir), v) if len(out) else 0
        counts[v] = c
    return counts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inputs", nargs="+", required=True, type=Path, help="recorder dirs (2 or more)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--labels", nargs="+", help="names for the recv_ns_<label> columns (default: dir names)")
    a = ap.parse_args()
    if len(a.inputs) < 2:
        ap.error("need at least two --inputs")
    for p in a.inputs:
        if not p.is_dir():
            ap.error(f"not a directory: {p}")
    counts = merge(a.inputs, a.out, a.labels)
    if not counts:
        print("no parquet chunks found in any input")
        return
    print(f"merged into {a.out} (counts only; rows matched on {', '.join(KEY)})")
    for v, c in counts.items():
        print(f"{v}: " + ", ".join(f"{k}={n:,}" for k, n in c.items()))


if __name__ == "__main__":
    main()
