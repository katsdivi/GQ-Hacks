"""Build out/strategy_b/b_games_espn.csv: the 977 T8 games (data/raw/t8_game_plan.csv) with their ESPN kickoffs,
matched by ingest/kalshi_only_train.espn_kickoff from the cached ESPN boards (data/raw/espn/). This is the committed
form of the snippet that produced the file used by run_strategy_b.py (ids and kickoff times only).

Usage: python scripts/build_b_games_espn.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import ingest.kalshi_only_train as T  # noqa: E402

OUT = ROOT / "out" / "strategy_b" / "b_games_espn.csv"


def main() -> None:
    p = pd.read_csv(ROOT / "data" / "raw" / "t8_game_plan.csv")
    p["k_date"] = pd.to_datetime(p["k_date"])
    cache, out = {}, []
    for _, r in p.iterrows():
        ko, src = T.espn_kickoff(r.league, r, cache)
        out.append({"game_id": r.game_id, "kalshi_event": r.k_event, "kalshi_home_ticker": r.k_home_ticker,
                    "kalshi_away_ticker": r.k_away_ticker, "league": r.league, "t8_kickoff": r.kickoff_utc,
                    "espn_kickoff": ko, "espn_source": src})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    o = pd.DataFrame(out)
    o.to_csv(OUT, index=False)
    print(f"{OUT}: {len(o)} games, ESPN kickoff found {o['espn_kickoff'].notna().sum()}")


if __name__ == "__main__":
    main()
