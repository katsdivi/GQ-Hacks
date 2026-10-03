"""Measure D, the polymarket.com match-to-block delay (HYPOTHESIS_v2.md, "Block-time bias").

Uses only the calibration markets the recorder stores as venue "polymarket_dcal" (busiest
non-sports markets; never football). For each trade seen on the public websocket:

  D = block timestamp of its transaction (Polygon, whole seconds) - our websocket receipt time

Also reports block timestamp - the websocket event's own timestamp (D_src). Reads only
recv_ns, src_ts_ns and tx_hash; no prices.

Usage:
  python -m collector.measure_d                # all calibration trades on disk
  python -m collector.measure_d --min-trades 200
Writes out/d_measurement.csv (one row per transaction) and prints median and p90.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DCAL = ROOT / "data" / "live" / "polymarket_dcal"
OUT = ROOT / "out" / "d_measurement.csv"
CACHE = ROOT / "data" / "raw" / "polygon_block_ts.json"
RPCS = ["https://polygon-bor-rpc.publicnode.com", "https://polygon.drpc.org", "https://1rpc.io/matic"]


def rpc(method: str, params: list):
    for u in RPCS:
        try:
            r = requests.post(u, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout=20).json()
            if r.get("result") is not None:
                return r["result"]
        except (requests.RequestException, ValueError):
            continue
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-trades", type=int, default=200)
    a = ap.parse_args()
    files = sorted(DCAL.glob("*/*.parquet"))
    if not files:
        sys.exit("no calibration trades recorded yet (data/live/polymarket_dcal)")
    df = pd.concat([pd.read_parquet(f, columns=["recv_ns", "src_ts_ns", "tx_hash"]) for f in files], ignore_index=True)
    df = df.dropna(subset=["tx_hash"])
    # One transaction can carry several fills; use the first receipt of each transaction.
    tx = df.groupby("tx_hash").agg(recv_ns=("recv_ns", "min"), src_ts_ns=("src_ts_ns", "min")).reset_index()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    block_ts = []
    for h in tx["tx_hash"]:
        if h not in cache:
            t = rpc("eth_getTransactionByHash", [h])
            bn = t.get("blockNumber") if t else None
            b = rpc("eth_getBlockByNumber", [bn, False]) if bn else None
            cache[h] = int(b["timestamp"], 16) if b else None
        block_ts.append(cache[h])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache))
    tx["block_ts"] = block_ts
    tx = tx.dropna(subset=["block_ts"])
    tx["D_s"] = tx["block_ts"] - tx["recv_ns"] / 1e9
    tx["D_src_s"] = tx["block_ts"] - tx["src_ts_ns"].astype(float) / 1e9
    OUT.parent.mkdir(exist_ok=True)
    tx.to_csv(OUT, index=False)
    n = len(tx)
    q = tx["D_s"].quantile([0.1, 0.5, 0.9])
    qs = tx["D_src_s"].quantile([0.5, 0.9])
    print(f"transactions with block time: {n} (of {len(df):,} calibration fills)")
    print(f"D = block_ts - receipt:   p10 {q[0.1]:+.2f} s, median {q[0.5]:+.2f} s, p90 {q[0.9]:+.2f} s")
    print(f"D_src = block_ts - ws ts: median {qs[0.5]:+.2f} s, p90 {qs[0.9]:+.2f} s")
    print("note: block_ts is whole seconds, so D has up to 1 s of rounding; a negative D means the block "
          "time is earlier than our receipt (network delay to us exceeds the match-to-block delay)")
    if n < a.min_trades:
        print(f"NOT ENOUGH: {n} < {a.min_trades} trades required by HYPOTHESIS_v2.md; rerun later")


if __name__ == "__main__":
    main()
