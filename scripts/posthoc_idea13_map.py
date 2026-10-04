"""Post-hoc Idea 13: map Kalshi NFL games to nflverse games (closing moneylines). No Kalshi trades are read.

post-hoc, exploratory; sportsbook closing line used as a signal only; selected on training only.

Match: same unordered team pair (Kalshi code aliases JAC -> JAX, LAR -> LA) and nflverse gameday equal to the
US Eastern date of the ESPN kickoff (+-1 day allowed, nearest wins). Orientation is by team code, never by the
home/away label, so neutral-site games map correctly.

Usage (cwd = repo root): python scripts/posthoc_idea13_map.py   (prints STEP 0 counts and 10 random matches)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
NFLVERSE = Path("data/nflverse_raw/games.csv")
ALIAS = {"JAC": "JAX", "LAR": "LA"}
AB_CUTOFF = pd.Timestamp("2026-10-03 20:00", tz="America/New_York")


def nfl_code(c: str) -> str:
    return ALIAS.get(c, c)


def training_nfl() -> pd.DataFrame:
    g = pd.read_csv(DATA / "raw" / "kalshi_only_games.csv")
    g = g[g["league"] == "NFL"]
    return pd.DataFrame({"game_id": g["game_id"], "home": g["home"], "away": g["away"],
                         "kickoff": pd.to_datetime(g["kickoff_utc_espn"], utc=True)})


def holdout_nfl() -> pd.DataFrame:
    """The v3 A4 holdout A set's NFL games (as posthoc_idea4.holdout_games), metadata only."""
    ev = pd.read_csv(DATA / "holdout_raw" / "events.csv")
    ev = ev[ev["espn_kickoff"].notna() & (ev["league"] == "NFL")]
    ev = ev[pd.to_datetime(ev["espn_kickoff"], utc=True) <= AB_CUTOFF]
    return pd.DataFrame({"game_id": ev["game_id"], "home": ev["k_home_code"], "away": ev["k_away_code"],
                         "kickoff": pd.to_datetime(ev["espn_kickoff"], utc=True)})


def nflverse() -> pd.DataFrame:
    v = pd.read_csv(NFLVERSE)
    v = v[v["season"] >= 2025].copy()
    v["gameday"] = pd.to_datetime(v["gameday"]).dt.date
    return v


def match(games: pd.DataFrame, v: pd.DataFrame) -> pd.DataFrame:
    """One row per Kalshi game: nflverse game_id and each Kalshi team's moneyline (NaN if unmatched)."""
    out = []
    for r in games.itertuples():
        h, a = nfl_code(r.home), nfl_code(r.away)
        d = r.kickoff.tz_convert("America/New_York").date()
        c = v[((v["home_team"] == h) & (v["away_team"] == a)) | ((v["home_team"] == a) & (v["away_team"] == h))]
        c = c.assign(_dd=[abs((x - d).days) for x in c["gameday"]])
        c = c[c["_dd"] <= 1].sort_values("_dd")
        row = {"game_id": r.game_id, "kalshi_home": r.home, "kalshi_away": r.away, "nflverse_id": None,
               "gameday": None, "ml_home": float("nan"), "ml_away": float("nan"), "nfl_game_type": None}
        if len(c):
            m = c.iloc[0]
            ml = {m["home_team"]: m["home_moneyline"], m["away_team"]: m["away_moneyline"]}
            row.update(nflverse_id=m["game_id"], gameday=str(m["gameday"]), ml_home=ml[h], ml_away=ml[a],
                       nfl_game_type=m["game_type"])
        out.append(row)
    return pd.DataFrame(out)


def main() -> None:
    v = nflverse()
    for name, g in (("training", training_nfl()), ("holdout", holdout_nfl())):
        m = match(g, v)
        ok = m["nflverse_id"].notna()
        ml = ok & m["ml_home"].notna() & m["ml_away"].notna()
        print(f"{name}: NFL games {len(m)}, matched {int(ok.sum())}, with both moneylines {int(ml.sum())}, "
              f"unmatched {int((~ok).sum())}")
        print(m[ml].sample(min(10, int(ml.sum())), random_state=20261004).to_string(index=False))


if __name__ == "__main__":
    main()
