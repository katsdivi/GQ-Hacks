"""Live paper maker for ONE polymarket.com game, Arms A and B (generalizes demo/paper_maker_live.py; NOT a test of
HYPOTHESIS_v4, which is decided only on test set 2, Oct 8 to 12).

Every minute: re-reads this game's local recorder chunks (data/live_oct4/<game>/polymarket), rebuilds top of book at
venue time, and runs scripts/posthoc_mm_v4.simulate unchanged from this process's start to now, home token only:
join best bid and ask (never improve), 10 contracts, inventory cap +/- 50, kickoff cut [T - 2 min, T + 20 min],
strict trade-through fills (rule F1), no Kalshi signal. Arm A: min_spread 0. Arm B: quote only while spread >= 3 c.
Running P&L = cash + inventory marked to the current mid, maker fee 0 (as in the demo). Log:
results/posthoc_mm_v4/live_oct4/<game>.log. Stops when Gamma reports the market closed, or at --until-utc.

Paper only: reads local parquet files and public Gamma metadata; places, changes and cancels no orders; imports no
order code; reads no key.
"""
import argparse
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

WT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WT / "scripts"))
sys.path.insert(0, str(WT / "demo"))
import posthoc_mm_v4 as M
from paper_maker_live import book_from

ET = ZoneInfo("America/New_York")
NS = M.NS
ARMS = (("A", 0.0), ("B", 0.03))


def gamma(cond: str) -> dict:
    return requests.get("https://gamma-api.polymarket.com/markets", params={"condition_ids": cond}, timeout=30).json()[0]


def load(live: Path, tok: str) -> pd.DataFrame:
    fs = sorted(glob.glob(str(live / "*" / "*.parquet")))
    if not fs:
        return pd.DataFrame()
    t = pd.concat([pd.read_parquet(f) for f in fs], ignore_index=True)
    return t[t["market_id"] == tok]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--condition", required=True)
    ap.add_argument("--until-utc", required=True)
    a = ap.parse_args()
    live = WT / "data" / "live_oct4" / a.game / "polymarket"
    log = WT / "results" / "posthoc_mm_v4" / "live_oct4" / f"{a.game}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    m = gamma(a.condition)
    ids = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
    outs = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
    gs = pd.Timestamp(m["gameStartTime"])
    tok, ko = ids[1], (gs.tz_localize("UTC") if gs.tzinfo is None else gs).value
    end_ns = pd.Timestamp(a.until_utc).value
    start = time.time_ns()

    def w(s: str) -> None:
        with log.open("a") as fh:
            fh.write(s + "\n")

    w(f"# live_oct4 paper maker, Arms A (always) and B (spread >= 3 c), polymarket.com {m.get('question')}, "
      f"home token ({outs[1]}) ...{tok[-8:]}, kickoff {pd.Timestamp(ko, tz='UTC').tz_convert(ET):%H:%M} ET; "
      f"start {datetime.now(ET):%H:%M:%S} ET; PAPER ONLY, no orders")
    seen = {k: 0 for k, _ in ARMS}
    last_gamma = 0.0
    while time.time_ns() < end_ns:
        now = time.time_ns()
        if time.time() - last_gamma > 300:
            last_gamma = time.time()
            try:
                if gamma(a.condition).get("closed"):
                    w(f"# market closed on Gamma at {datetime.now(ET):%H:%M:%S} ET")
                    break
            except Exception as e:  # metadata hiccup: keep running
                w(f"# gamma check failed: {type(e).__name__}")
        t = load(live, tok)
        line = f"{datetime.now(ET):%H:%M:%S} ET"
        if t.empty:
            w(line + " | no polymarket.com rows yet")
        else:
            bk = book_from(t)
            tr = t[(t["kind"] == "trade") & t["src_ts_ns"].notna()].sort_values("src_ts_ns", kind="stable")
            tts = tr["src_ts_ns"].astype("int64").to_numpy()
            mid = float(bk.mid(np.array([now]))[0]) if len(bk.ts) else float("nan")
            bi = bk.idx(np.array([now]))[0] if len(bk.ts) else -1
            quote = f"bid {bk.bid[bi]:.2f} / ask {bk.ask[bi]:.2f}" if bi >= 0 else "no book"
            parts = []
            for arm, ms in ARMS:
                fills = M.simulate(bk, tts, tr["price"].to_numpy(float), tr["size"].to_numpy(float), start, now, ko,
                                   None, None, "F1", ms)
                inv = sum(f["side"] * f["qty"] for f in fills)
                cash = sum(-f["side"] * f["qty"] * f["price"] for f in fills)
                pnl = cash + inv * mid if mid == mid else float("nan")
                for f in fills[seen[arm]:]:
                    w(f"  FILL arm {arm} {pd.Timestamp(f['t'], tz='UTC').tz_convert(ET):%H:%M:%S} "
                      f"{'BUY ' if f['side'] > 0 else 'SELL'} {f['qty']:.0f} @ {f['price']:.2f}")
                seen[arm] = len(fills)
                parts.append(f"arm {arm}: fills {len(fills)} inv {inv:+.0f} P&L ${pnl:+.2f}")
            w(f"{line} | book {quote} | trades seen {len(tts)} | " + " | ".join(parts) + f" (mid {mid:.3f})")
        time.sleep(max(1.0, 60 - (time.time_ns() - now) / NS))
    w(f"# stopped {datetime.now(ET):%H:%M:%S} ET")


if __name__ == "__main__":
    main()
