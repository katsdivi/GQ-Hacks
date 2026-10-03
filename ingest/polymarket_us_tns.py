"""Polymarket US Time & Sales: public daily execution tape -> football-only parquet.

Source: https://www.polymarketexchange.com/time-and-sales.html (manifest at
/files/time-and-sales/manifest.json). One CSV per trading day (17:00 ET to 16:59 ET), posted about
6 PM ET. Columns: Transaction Time (timestamp of the executed trade, ISO with offset, nanoseconds),
Symbol (gateway market slug), Last Price, Last Quantity. No side or aggressor flag.

For each file this keeps only NFL/CFB rows (Symbol starting aec-nfl- or aec-cfb-) and writes
data/raw/polymarket_us_tns_football/<YYYYMMDD>.parquet with columns
  ts (int64 UTC ns), symbol, price, qty
then deletes the full CSV (all-market files total about 16 GB). Prices are stored, not examined.

Holdout: files dated on or after 2026-08-01 are skipped unless --holdout is passed; with
--holdout they are converted the same way and never read further (write-only).

Usage:
  python -m ingest.polymarket_us_tns              # training-period files
  python -m ingest.polymarket_us_tns --holdout    # also holdout files (write-only)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://www.polymarketexchange.com/files/time-and-sales"
RAW = ROOT / "data" / "raw" / "polymarket_us_tns"
OUT = ROOT / "data" / "raw" / "polymarket_us_tns_football"
TEST_FROM = "20260801"


def convert(csv: Path, out: Path) -> int:
    keep = []
    for chunk in pd.read_csv(csv, chunksize=500_000, dtype={"Symbol": "string"}):
        f = chunk[chunk["Symbol"].str.match(r"aec-(nfl|cfb)-", na=False)]
        if len(f):
            keep.append(f)
    df = pd.concat(keep, ignore_index=True) if keep else pd.DataFrame(
        columns=["Transaction Time", "Symbol", "Last Price", "Last Quantity"])
    ts = pd.to_datetime(df["Transaction Time"], format="ISO8601", utc=True).dt.as_unit("ns")
    pd.DataFrame({"ts": ts.astype("int64").to_numpy(), "symbol": df["Symbol"].astype("string").to_numpy(),
                  "price": pd.to_numeric(df["Last Price"]).to_numpy(),
                  "qty": pd.to_numeric(df["Last Quantity"]).to_numpy()}).to_parquet(out, index=False)
    return len(df)


def download(name: str, etag: str, dest: Path, s: requests.Session) -> None:
    tmp = dest.with_suffix(".part")
    for attempt in range(5):
        try:
            with s.get(f"{BASE}/{name}", params={"v": etag}, stream=True, timeout=(20, 120)) as r:
                r.raise_for_status()
                with open(tmp, "wb") as fh:
                    for block in r.iter_content(1 << 20):
                        fh.write(block)
            tmp.rename(dest)
            return
        except requests.RequestException as e:
            print(f"  {name}: {type(e).__name__}, retry {attempt + 1}", flush=True)
            time.sleep(min(2 ** attempt, 30))
    raise RuntimeError(f"{name}: download failed")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--holdout", action="store_true", help="also convert holdout files (write-only)")
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    manifest = s.get(f"{BASE}/manifest.json", timeout=60).json()
    (OUT / "manifest.json").write_text(json.dumps(manifest))
    files = sorted(manifest["files"], key=lambda f: f["filename"])
    log = []
    for f in files:
        day = f["filename"][:8]
        if day >= TEST_FROM and not a.holdout:
            continue
        out = OUT / f"{day}.parquet"
        if out.exists():
            continue
        csv = RAW / f["filename"]
        if not (csv.exists() and csv.stat().st_size == f["size"]):
            download(f["filename"], f["eTag"], csv, s)
        n = convert(csv, out)
        csv.unlink()
        log.append({"day": day, "csv_bytes": f["size"], "football_rows": n})
        print(f"{day}: {f['size'] / 1e6:.0f} MB csv -> {n:,} football rows", flush=True)
    if log:
        p = OUT / "conversion_log.csv"
        pd.DataFrame(log).to_csv(p, mode="a", header=not p.exists(), index=False)
    print(f"done: {len(list(OUT.glob('*.parquet')))} day files in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
