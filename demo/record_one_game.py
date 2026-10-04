"""Live demo recorder (NOT a test): runs the existing collector (staleline collector/run.py) unchanged, but limited to
ONE game: Colts at Commanders, 2026-10-04 (Kalshi KXNFLGAME-26OCT04INDWAS, polymarket.com condition below).

Read-only market data. No orders: the collector has no order code; nothing here imports any order path.
Kalshi runs in public REST mode (KALSHI_API_KEY_ID set empty before import, so no key file is ever read).
Tiger Data is off (TIGER_DATABASE_URL set empty). Output goes to staleline/data/live_demo/ (gitignored), never data/live.
Polymarket US is not recorded (the demo covers polymarket.com and Kalshi only).

Usage (cwd = staleline repo root): nice -n 19 .venv-run/bin/python ../wt-mm-v4/demo/record_one_game.py --until-et 09:10
"""
import os
import sys
from pathlib import Path

ROOT = Path("/Users/divyamkataria/GQ HACKS/staleline")
os.environ["COLLECTOR_LIVE_DIR"] = str(ROOT / "data" / "live_demo")
os.environ["COLLECTOR_GAPS_MD"] = str(ROOT / "data" / "live_demo" / "GAPS_demo.md")
os.environ["TIGER_DATABASE_URL"] = ""
os.environ["KALSHI_API_KEY_ID"] = ""
os.environ["KALSHI_PRIVATE_KEY_PATH"] = ""
sys.path.insert(0, str(ROOT))

import argparse
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import collector.run as C

EVENT = "KXNFLGAME-26OCT04INDWAS"
PM_CONDITION = "0x0dc7d4a71a89164e7b02e2cb34911d5365895444c9da507436993ea47a6b06d3"   # "Colts vs. Commanders"

_kref = C.KalshiPoller.refresh_markets
def _kalshi_one(self):
    _kref(self)
    self.markets = {t: v for t, v in self.markets.items() if t.startswith(EVENT + "-")}
    C.log(f"demo filter: kalshi markets {sorted(self.markets)}")
C.KalshiPoller.refresh_markets = _kalshi_one

_pref = C.PolymarketWS.refresh
def _pm_one(self):
    _pref(self)
    self.tokens = {a: v for a, v in self.tokens.items() if v["condition"] == PM_CONDITION and not v["calib"]}
    C.log(f"demo filter: polymarket tokens {len(self.tokens)}")
    return True
C.PolymarketWS.refresh = _pm_one


async def _noop(self, stop):
    await stop.wait()
C.PolymarketUS.run = _noop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until-et", default="09:10")
    a = ap.parse_args()
    et = ZoneInfo("America/New_York")
    now = datetime.now(et)
    hh, mm = map(int, a.until_et.split(":"))
    end = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    minutes = max(0.5, (end - now).total_seconds() / 60)
    C.log(f"demo recorder: one game {EVENT}, until {a.until_et} ET ({minutes:.1f} min)")
    asyncio.run(C.main_async(minutes))


if __name__ == "__main__":
    main()
