"""Kalshi market metadata for the Strategy A training markets: settlement, tick and liquidity fields only.

For every game in data/raw/kalshi_only_games.csv (training, kickoff < 2026-08-01), both team markets
(home = kalshi_ticker, away = f"{kalshi_event}-{away}"): GET /historical/markets/<t>, else /markets/<t>.

Kept fields: status, result, settlement_value_dollars (v3 Amendment 3 section 1, scalar settlement),
price_level_structure and price_ranges (tick; section 3 fill cap = 1 - tick), volume_fp and open_interest_fp
(report.py liquidity section). Every other field (last, bid, ask and previous prices, sizes) is dropped in
memory and never written or printed.

Output: data/raw/kalshi_market_meta.csv (gitignored). A market Kalshi does not return gets status "not found".

Usage: python -m ingest.kalshi_market_meta [--rate 4]
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import pandas as pd
import requests

from ingest import kalshi_only_train as T

OUT = T.RAW / "kalshi_market_meta.csv"
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
KEEP = ("status", "result", "settlement_value_dollars", "price_level_structure", "volume_fp", "open_interest_fp")


def fetch(ticker: str) -> dict:
    for path in (f"/historical/markets/{ticker}", f"/markets/{ticker}"):
        try:
            m = T._kget(path)["market"]
        except requests.HTTPError:
            continue
        row = {k: m.get(k) for k in KEEP}
        row["price_ranges"] = json.dumps(m.get("price_ranges"))
        del m
        return row
    return {"status": "not found"}


def markets(games: pd.DataFrame) -> list[tuple[str, str, str]]:
    out = []
    for r in games.itertuples():
        out += [(r.game_id, "home", r.kalshi_ticker), (r.game_id, "away", f"{r.kalshi_event}-{r.away}")]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rate", type=float, default=4.0)
    a = ap.parse_args()
    T.K_RATE[0] = a.rate
    g = pd.read_csv(T.GAMES_OUT, dtype=str)
    assert (pd.to_datetime(g["kickoff_utc_espn"], utc=True) < SEAL).all(), "training games only"
    rows = []
    for gid, side, t in markets(g):
        rows.append({"game_id": gid, "side": side, "ticker": t, **fetch(t),
                     "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"{OUT}: {len(rows)} markets, not found {sum(r['status'] == 'not found' for r in rows)}")


if __name__ == "__main__":
    main()
