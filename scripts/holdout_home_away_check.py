"""Home/away check on the holdout (ids and team names only; no prices, results or statistics).

For every holdout Kalshi game with an ESPN kickoff (data/holdout_raw/events.csv: away/home from the event
sub_title) and every polymarket.com moneyline dated Aug 1 to Oct 3, 2026 (Gamma, current series 12185 NFL /
12756 CFB; outcomes listed [away, home]), find the ESPN competition (cached boards in data/holdout_raw/espn/,
same name scoring as ingest/kalshi_only_train.espn_kickoff) and compare who ESPN labels home and away.
  agree:     the venue's away team scores best against ESPN's away team
  mismatch:  it scores better against ESPN's home team (listed with the venue separator "at" / "vs")
  no match:  no ESPN competition within +-1 day scores >= 1.6
Usage: python scripts/holdout_home_away_check.py   (writes data/holdout_raw/home_away_check.csv, gitignored)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ingest import kalshi_only_train as T  # noqa: E402

HR = ROOT / "data" / "holdout_raw"
GAMMA = "https://gamma-api.polymarket.com"
PM_SERIES = {"NFL": "12185", "CFB": "12756"}


def boards(league: str, day: pd.Timestamp) -> list[dict]:
    p = HR / "espn" / f"{league.lower()}_{day:%Y%m%d}.json"
    return json.loads(p.read_text()).get("events", []) if p.exists() else []


def orient(league: str, day: pd.Timestamp, away: tuple[str, str], home: tuple[str, str]) -> tuple[str, float]:
    """('agree' | 'mismatch' | 'no match', best score)."""
    best, best_s, best_o = None, 0.0, "no match"
    for dd in (-1, 0, 1):
        for e in boards(league, day + pd.Timedelta(days=dd)):
            comp = (e.get("competitions") or [None])[0]
            if not comp or len(comp.get("competitors", [])) != 2:
                continue
            ha = {c.get("homeAway"): c["team"] for c in comp["competitors"]}
            if set(ha) != {"home", "away"}:
                continue
            same = T._name_score(*away, ha["away"]) + T._name_score(*home, ha["home"])
            swap = T._name_score(*away, ha["home"]) + T._name_score(*home, ha["away"])
            s = max(same, swap) - 0.02 * abs(dd)
            if s > best_s:
                best_s, best_o = s, ("agree" if same >= swap else "mismatch")
    return (best_o if best_s >= 1.6 else "no match"), round(best_s, 3)


def main() -> None:
    ev = pd.read_csv(HR / "events.csv")
    ev = ev[ev["espn_kickoff"].notna()]
    rows = []
    for r in ev.itertuples():
        o, s = orient(r.league, pd.Timestamp(r.k_date), (r.k_away, r.k_away_code), (r.k_home, r.k_home_code))
        rows.append({"venue": "kalshi", "id": r.k_event, "game_id": r.game_id, "sep": r.k_sep, "result": o, "score": s})
    for lg, sid in PM_SERIES.items():
        off = 0
        while True:
            b = requests.get(f"{GAMMA}/events", params={"series_id": sid, "limit": 100, "offset": off}, timeout=60).json()
            if not b:
                break
            off += len(b)
            for e in b:
                ml = [m for m in (e.get("markets") or []) if m.get("sportsMarketType") == "moneyline"]
                if not ml or not ml[0].get("gameStartTime"):
                    continue
                gs = pd.Timestamp(ml[0]["gameStartTime"])
                gs = gs.tz_localize("UTC") if gs.tzinfo is None else gs.tz_convert("UTC")
                if not (pd.Timestamp("2026-08-01", tz="UTC") <= gs <= pd.Timestamp("2026-10-04 04:00", tz="UTC")):
                    continue
                oc = json.loads(ml[0]["outcomes"]) if isinstance(ml[0]["outcomes"], str) else ml[0]["outcomes"]
                parts = e["slug"].split("-")
                sep = "vs" if re.search(r"\bvs\.?\b", e.get("title", "")) else "at"
                o, s = orient(lg, gs.tz_convert("America/New_York").tz_localize(None).normalize(),
                              (oc[0], parts[1]), (oc[1], parts[2]))
                rows.append({"venue": "polymarket.com", "id": e["slug"], "game_id": "", "sep": sep, "result": o,
                             "score": s})
    out = pd.DataFrame(rows)
    out.to_csv(HR / "home_away_check.csv", index=False)
    for v, d in out.groupby("venue"):
        print(f"{v}: {len(d)} checked; {d['result'].value_counts().to_dict()}")
        mm = d[d["result"] == "mismatch"]
        for r in mm.itertuples():
            print(f"  MISMATCH {r.id} ({r.game_id}) sep={r.sep} score={r.score}")
    nm = out[out["result"] == "no match"]
    if len(nm):
        print(f"no ESPN match: {len(nm)}: {list(nm['id'])}")


if __name__ == "__main__":
    main()
