"""Kalshi trades for the 4 training games that have CME game contracts but no Kalshi training file.

Games (kickoff before 2026-08-01, so TRAINING games): CFP final (Jan 19, 2026), AFC and NFC championships
(Jan 25), Super Bowl (Feb 8). Kalshi's game-winner series (KXNFLGAME / KXNCAAFGAME) is empty for them:
KXNFLGAME-26JAN25LASEA has 0 volume, KXNCAAFGAME-26JAN19MIAIND has 18 contracts, and there is no KXNFLGAME
event for NE at DEN or the Super Bowl. Kalshi traded these games in championship series instead, which for
a single deciding game pay exactly like a game-winner contract:
  KXNCAAF-26-{IND,MIA} (CFP champion), KXNFLAFCCHAMP-25-{NE,DEN}, KXNFLNFCCHAMP-25-{LA,SEA}, KXSB-26-{NE,SEA}.
Same tick contract and window as ingest/kalshi_only_train.py: ESPN kickoff; kickoff - 2 h to + 5 h; both
teams' markets; price flipped to P(ESPN home team wins); settlement read from the home market (yes = 1).
Free public Kalshi API; no vendor spend.

Writes ONLY data/raw/cme_train_v2/kalshi/<game_id>.parquet, data/raw/cme_train_v2/kalshi_games.csv and an
ESPN scoreboard cache under data/raw/cme_train_v2/espn/. data/raw/kalshi_only* is never touched.

Usage (cwd = worktree root): PYTHONPATH=. python scripts/cme_train_kalshi_extra.py --data ../staleline/data
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ingest import kalshi as K
import ingest.kalshi_only_train as T

# league, ET date, (team code, Kalshi name, Kalshi ticker) x 2, Kalshi series event
GAMES = [
    ("CFB", "2026-01-19", ("IND", "Indiana", "KXNCAAF-26-IND"), ("MIA", "Miami (FL)", "KXNCAAF-26-MIA"), "KXNCAAF-26"),
    ("NFL", "2026-01-25", ("NE", "New England", "KXNFLAFCCHAMP-25-NE"), ("DEN", "Denver", "KXNFLAFCCHAMP-25-DEN"),
     "KXNFLAFCCHAMP-25"),
    ("NFL", "2026-01-25", ("LA", "Los Angeles Rams", "KXNFLNFCCHAMP-25-LA"), ("SEA", "Seattle", "KXNFLNFCCHAMP-25-SEA"),
     "KXNFLNFCCHAMP-25"),
    ("NFL", "2026-02-08", ("NE", "New England", "KXSB-26-NE"), ("SEA", "Seattle", "KXSB-26-SEA"), "KXSB-26"),
]


def espn_game(league: str, day: pd.Timestamp, a: tuple, b: tuple):
    """ESPN kickoff and which of a/b is ESPN's home team (date +-1 day, name/code match >= 1.6)."""
    best = None
    for dd in (-1, 0, 1):
        for e in T.espn_board(league, day + pd.Timedelta(days=dd)):
            comp = (e.get("competitions") or [None])[0]
            if not comp or len(comp.get("competitors", [])) != 2:
                continue
            side = {c["homeAway"]: c["team"] for c in comp["competitors"]}
            s1 = T._name_score(a[1], a[0], side["home"]) + T._name_score(b[1], b[0], side["away"])
            s2 = T._name_score(b[1], b[0], side["home"]) + T._name_score(a[1], a[0], side["away"])
            s, home = (s1, a) if s1 >= s2 else (s2, b)
            if best is None or s > best[0]:
                best = (s, K._utc(comp.get("date") or e["date"]), home)
    return (best[1], best[2]) if best and best[0] >= 1.6 else (None, None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../staleline/data")
    args = ap.parse_args()
    out = Path(args.data) / "raw" / "cme_train_v2"
    (out / "kalshi").mkdir(parents=True, exist_ok=True)
    T.ESPN_DIR = out / "espn"
    rows = []
    for league, day, a, b, event in GAMES:
        ko, home = espn_game(league, pd.Timestamp(day, tz="UTC"), a, b)
        assert ko is not None, f"no ESPN match for {event}"
        assert ko < T.SEAL
        away = b if home is a else a
        gid = f"{league.lower()}_{ko.tz_convert('America/New_York'):%Y%m%d}_{away[0].lower()}_{home[0].lower()}"
        p = out / "kalshi" / f"{gid}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
        else:
            s, e = ko - T.PRE, ko + T.POST
            df = pd.concat([K.fetch_trades(home[2], s, e, away=False), K.fetch_trades(away[2], s, e, away=True)],
                           ignore_index=True).sort_values("ts", kind="stable").reset_index(drop=True)
            df.to_parquet(p, index=False)
        res = T._kget(f"/historical/markets/{home[2]}")["market"].get("result", "")
        rows.append({"game_id": gid, "league": league, "home": home[0], "away": away[0], "kalshi_event": event,
                     "kalshi_ticker": home[2], "away_ticker": away[2],
                     "kickoff_utc_espn": ko.strftime("%Y-%m-%dT%H:%M:%SZ"), "kickoff_source": "espn",
                     "settlement_result": {"yes": 1.0, "no": 0.0}.get(res), "n_trades": len(df),
                     "market_type": "championship series (pays as game winner)"})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(out / "kalshi_games.csv", index=False)


if __name__ == "__main__":
    main()
