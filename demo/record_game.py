"""Live recorder for ONE polymarket.com game (generalizes demo/record_one_game.py; NOT a test of HYPOTHESIS_v4).

Runs the existing collector (collector/run.py in this worktree) unchanged, limited to one polymarket.com condition.
Read-only market data. No orders: the collector has no order code; nothing here imports any order path.
No key is read: KALSHI_API_KEY_ID / KALSHI_PRIVATE_KEY_PATH are blanked before import, and this worktree has no .env or
secrets/. Kalshi and Polymarket US feeds are switched off (v4 uses no Kalshi signal). Tiger Data is off.
Output: wt-mm-v4/data/live_oct4/<game>/ (gitignored). Nothing is written to the staleline checkout.

Usage (cwd = wt-mm-v4): nice -n 19 <python> demo/record_game.py --game nfl-ind-was-2026-10-04 --condition 0x... --until-utc <iso>
"""
import os
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[1]
_a = sys.argv
GAME = _a[_a.index("--game") + 1]
os.environ["COLLECTOR_LIVE_DIR"] = str(WT / "data" / "live_oct4" / GAME)
os.environ["COLLECTOR_GAPS_MD"] = str(WT / "data" / "live_oct4" / GAME / "GAPS.md")
os.environ["TIGER_DATABASE_URL"] = ""
os.environ["KALSHI_API_KEY_ID"] = ""
os.environ["KALSHI_PRIVATE_KEY_PATH"] = ""
sys.path.insert(0, str(WT))

import argparse
import asyncio
import time

import pandas as pd

import collector.run as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", required=True)
    ap.add_argument("--condition", required=True)
    ap.add_argument("--until-utc", required=True)
    a = ap.parse_args()

    _pref = C.PolymarketWS.refresh

    def _pm_one(self):
        _pref(self)
        self.tokens = {t: v for t, v in self.tokens.items() if v["condition"] == a.condition and not v["calib"]}
        C.log(f"live_oct4 filter {a.game}: polymarket tokens {len(self.tokens)}")
        return True
    C.PolymarketWS.refresh = _pm_one

    async def _noop(self, stop):
        await stop.wait()
    C.KalshiPoller.run = _noop
    C.PolymarketUS.run = _noop
    C.KalshiPoller.save_state = lambda self: None

    minutes = max(1.0, (pd.Timestamp(a.until_utc).value - time.time_ns()) / 60e9)
    C.log(f"live_oct4 recorder {a.game}: polymarket.com only, until {a.until_utc} ({minutes:.0f} min)")
    asyncio.run(C.main_async(minutes))


if __name__ == "__main__":
    main()
