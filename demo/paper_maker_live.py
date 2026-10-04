"""Live paper maker demo (NOT a test; HYPOTHESIS_v4 Arm A rule): every minute, re-reads the demo recorder's local
polymarket.com chunks for Colts at Commanders (home token = Commanders), rebuilds top of book at venue time, and
runs scripts/posthoc_mm_v4.simulate (join best bid/ask, 10 contracts, cap +/- 50, strict trade-through fills,
kickoff cut, no signal) from the demo start to now. Prints fills and running P&L (cash + inventory marked to the
current mid, maker fee 0 per the Oct 3 Gamma fee data) to results/posthoc_mm_v4/demo.log.

Paper only: reads local parquet files; places no orders; imports no order code.
"""
import glob
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

WT = Path("/Users/divyamkataria/GQ HACKS/wt-mm-v4")
sys.path.insert(0, str(WT / "scripts"))
import posthoc_mm_v4 as M

ROOT = Path("/Users/divyamkataria/GQ HACKS/staleline")
LIVE = ROOT / "data/live_demo/polymarket"
LOG = WT / "results/posthoc_mm_v4/demo.log"
ET = ZoneInfo("America/New_York")
COND = "0x0dc7d4a71a89164e7b02e2cb34911d5365895444c9da507436993ea47a6b06d3"
NS = M.NS


def home_token() -> tuple[str, int]:
    m = requests.get("https://gamma-api.polymarket.com/markets", params={"condition_ids": COND}, timeout=30).json()[0]
    ids = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
    return ids[1], pd.Timestamp(m["gameStartTime"]).value     # outcomes [away, home]; collector treats ids[1] as home


def load(tok: str) -> pd.DataFrame:
    fs = sorted(glob.glob(str(LIVE / "*" / "*.parquet")))
    if not fs:
        return pd.DataFrame()
    t = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    return t[t["market_id"] == tok]


def book_from(t: pd.DataFrame) -> M.Book:
    b = t[t["kind"].isin(["bid", "ask"]) & t["src_ts_ns"].notna()]
    g = b.groupby("ts")
    out = pd.DataFrame({"src": g["src_ts_ns"].max()})
    for k in ("bid", "ask"):
        s = b[b["kind"] == k].groupby("ts").last()
        out[k] = s["price"].reindex(out.index)
        out[f"{k}_sz"] = s["size"].reindex(out.index)
    out[["bid", "ask"]] = out[["bid", "ask"]].ffill()
    out = out.dropna(subset=["bid", "ask"])
    return M.Book(out["src"].astype("int64").to_numpy(), out["bid"].to_numpy(float), out["ask"].to_numpy(float),
                  out["bid_sz"].fillna(0).to_numpy(float), out["ask_sz"].fillna(0).to_numpy(float))


def main(until_et: str = "09:10") -> None:
    tok, ko = home_token()
    hh, mm = map(int, until_et.split(":"))
    end = datetime.now(ET).replace(hour=hh, minute=mm, second=0, microsecond=0)
    start = time.time_ns()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(f"# demo paper maker (Arm A), polymarket.com Colts at Commanders, home token ...{tok[-8:]}, "
                f"kickoff {pd.Timestamp(ko, tz='UTC').tz_convert(ET):%H:%M} ET; start {datetime.now(ET):%H:%M:%S} ET; "
                f"PAPER ONLY, no orders\n")
    seen = 0
    while datetime.now(ET) < end:
        now = time.time_ns()
        t = load(tok)
        line = f"{datetime.now(ET):%H:%M:%S} ET"
        if t.empty:
            line += " | no polymarket.com rows yet"
        else:
            bk = book_from(t)
            tr = t[(t["kind"] == "trade") & t["src_ts_ns"].notna()].sort_values("src_ts_ns", kind="stable")
            tts = tr["src_ts_ns"].astype("int64").to_numpy()
            fills = M.simulate(bk, tts, tr["price"].to_numpy(float), tr["size"].to_numpy(float), start, now, ko,
                               None, None, "F1")
            mid = float(bk.mid(np.array([now]))[0]) if len(bk.ts) else float("nan")
            inv = sum(f["side"] * f["qty"] for f in fills)
            cash = sum(-f["side"] * f["qty"] * f["price"] for f in fills)
            pnl = cash + inv * mid if mid == mid else float("nan")
            for f in fills[seen:]:
                with LOG.open("a") as fh:
                    fh.write(f"  FILL {pd.Timestamp(f['t'], tz='UTC').tz_convert(ET):%H:%M:%S} "
                             f"{'BUY ' if f['side'] > 0 else 'SELL'} {f['qty']:.0f} @ {f['price']:.2f}\n")
            seen = len(fills)
            bi = bk.idx(np.array([now]))[0]
            quote = f"bid {bk.bid[bi]:.2f} x{bk.bsz[bi]:.0f} / ask {bk.ask[bi]:.2f} x{bk.asz[bi]:.0f}" if bi >= 0 else "no book"
            line += (f" | book {quote} | trades seen {len(tts)} | fills {len(fills)} | inventory {inv:+.0f} | "
                     f"running P&L ${pnl:+.2f} (marked to mid {mid:.3f})")
        with LOG.open("a") as fh:
            fh.write(line + "\n")
        time.sleep(max(1.0, 60 - (time.time_ns() - now) / NS))
    with LOG.open("a") as fh:
        fh.write(f"# demo stopped {datetime.now(ET):%H:%M:%S} ET\n")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "09:10")
