"""Post-hoc Idea 6: ESPN event id per game (from cached scoreboards) and the ESPN summary cache.

post-hoc, exploratory; designed and selected on training only. See results/posthoc_idea6/SPEC.md.

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea6_ids.py            training: map ids, fetch summaries to data/espn_raw/
  python scripts/posthoc_idea6_ids.py --holdout  holdout set (only after "run idea6 holdout")
"""
from __future__ import annotations

import argparse
import glob
import json
import time
from pathlib import Path

import pandas as pd
import requests

import ingest.kalshi_only_train as T

DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
CACHE = Path("data/espn_raw")
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/{}/summary"
AB_CUTOFF = pd.Timestamp("2026-10-03 20:00", tz="America/New_York")


def kalshi_names(holdout: bool) -> dict[str, str]:
    """Kalshi ticker -> team name (training: yes_sub_title of the historical market files; holdout: events.csv)."""
    if holdout:
        ev = pd.read_csv(DATA / "holdout_raw" / "events.csv")
        return {**dict(zip(ev["k_home_ticker"], ev["k_home"])), **dict(zip(ev["k_away_ticker"], ev["k_away"]))}
    out = {}
    for f in ("kalshi_kxncaafgame_historical.parquet", "kalshi_kxnflgame_historical.parquet"):
        d = pd.read_parquet(DATA / "raw" / f, columns=["ticker", "yes_sub_title"])
        out.update(dict(zip(d["ticker"], d["yes_sub_title"])))
    return out


def games(holdout: bool) -> pd.DataFrame:
    if not holdout:
        g = pd.read_csv(DATA / "raw" / "kalshi_only_games.csv")
        assert (pd.to_datetime(g["kickoff_utc_espn"], utc=True) < pd.Timestamp("2026-08-01", tz="UTC")).all()
        return g[["game_id", "league", "home", "away", "kalshi_event", "kickoff_utc_espn"]]
    ev = pd.read_csv(DATA / "holdout_raw" / "events.csv")
    ev = ev[ev["espn_kickoff"].notna()]
    ev = ev[pd.to_datetime(ev["espn_kickoff"], utc=True) <= AB_CUTOFF]
    return pd.DataFrame({"game_id": ev["game_id"], "league": ev["league"], "home": ev["k_home_code"],
                         "away": ev["k_away_code"], "kalshi_event": ev["k_event"], "kickoff_utc_espn": ev["espn_kickoff"]})


def boards(holdout: bool) -> list[tuple[str, str, pd.Timestamp, dict]]:
    d = DATA / ("holdout_raw/espn" if holdout else "raw/espn")
    out = {}
    for f in glob.glob(str(d / "*.json")):
        lg = Path(f).name.split("_")[0].upper()
        for e in json.loads(Path(f).read_text()).get("events", []):
            c = (e.get("competitions") or [None])[0]
            if c and len(c.get("competitors", [])) == 2:
                out[(lg, e["id"])] = (lg, e["id"], pd.Timestamp(c.get("date") or e["date"]).tz_convert("UTC"), c)
    return list(out.values())


def map_ids(holdout: bool) -> pd.DataFrame:
    g, B, names = games(holdout), boards(holdout), kalshi_names(holdout)
    rows = []
    for r in g.itertuples():
        k = pd.Timestamp(r.kickoff_utc_espn).tz_convert("UTC")
        cand = [b for b in B if b[0] == r.league and b[2] == k]
        hn = names.get(f"{r.kalshi_event}-{r.home}", r.home)
        an = names.get(f"{r.kalshi_event}-{r.away}", r.away)
        how = "kickoff"
        if len(cand) > 1:
            sc = []
            for b in cand:
                t = {x["homeAway"]: x["team"] for x in b[3]["competitors"]}
                s = max(T._name_score(hn, r.home, t["home"]) + T._name_score(an, r.away, t["away"]),
                        T._name_score(hn, r.home, t["away"]) + T._name_score(an, r.away, t["home"]))
                sc.append((s, b))
            sc.sort(key=lambda x: -x[0])
            cand = [sc[0][1]] if sc[0][0] > sc[1][0] else []
            how = "kickoff+name"
        rows.append({"game_id": r.game_id, "league": r.league, "espn_id": cand[0][1] if cand else None,
                     "id_how": how if cand else "none", "k_home_name": hn, "k_away_name": an})
    return pd.DataFrame(rows)


def summary_path(league: str, eid: str) -> Path:
    return CACHE / f"{league.lower()}_{eid}.json"


def fetch(ids: pd.DataFrame) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    todo = [r for r in ids.itertuples() if r.espn_id and not summary_path(r.league, r.espn_id).exists()]
    print(f"fetching {len(todo)} summaries", flush=True)
    for i, r in enumerate(todo):
        sport = "nfl" if r.league == "NFL" else "college-football"
        for attempt in range(6):
            try:
                resp = s.get(SUMMARY.format(sport), params={"event": r.espn_id}, timeout=30)
                if resp.status_code == 200:
                    summary_path(r.league, r.espn_id).write_text(resp.text)
                    break
            except requests.RequestException:
                pass
            time.sleep(2 ** attempt)
        time.sleep(0.4)
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true")
    a = ap.parse_args()
    ids = map_ids(a.holdout)
    CACHE.mkdir(parents=True, exist_ok=True)
    ids.to_csv(CACHE / f"ids_{'holdout' if a.holdout else 'training'}.csv", index=False)
    print(ids["id_how"].value_counts().to_dict(), flush=True)
    fetch(ids)


if __name__ == "__main__":
    main()
