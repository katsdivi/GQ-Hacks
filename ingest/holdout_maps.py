"""Freeze the venue maps for the Amendment 2 holdout run (listing metadata only; no prices, no recorded rows).

Writes data/live/holdout_maps/:
  polymarket_com_map.json  Kalshi event -> polymarket.com moneyline (conditionId, slug, outcomes, token ids) and the
                           token the collector recorded as HOME (PolymarketWS.refresh: clobTokenIds[1], outcomes are
                           taken as [away, home]). orientation = "ok" if outcomes[1] names the Kalshi home team,
                           "flipped" if it names the away team (the recording's P(home) would then be 1 - truth),
                           "unclear" otherwise.
  polymarket_us_map.json   copy of data/live/polymarket_us_map.json (the collector rewrites that file on refresh).
Gamma is queried for open AND closed events, because a finished game drops out of the collector's open listing.
Run: python -m ingest.holdout_maps
"""
from __future__ import annotations

import json
import shutil
from datetime import timedelta

import pandas as pd

from ingest.download_all import _sim
from ingest.holdout_candidates import GAMMA, LIVE, WIN_END, WIN_START, jget, kalshi_events

OUT = LIVE / "holdout_maps"
CAND = LIVE / "holdout_candidates.csv"


def gamma_moneylines() -> list[dict]:
    out = []
    for sid, league in ((12185, "nfl"), (12756, "cfb")):
        for closed in ("false", "true"):
            off = 0
            while off < 3000:
                b = jget(GAMMA + "/events", {"series_id": sid, "closed": closed, "limit": 100, "offset": off,
                                            "order": "startTime", "ascending": "false"})
                if not b:
                    break
                off += len(b)
                for e in b:
                    for m in e.get("markets") or []:
                        if m.get("sportsMarketType") != "moneyline" or not m.get("gameStartTime"):
                            continue
                        gs = pd.Timestamp(m["gameStartTime"])
                        gs = gs.tz_localize("UTC") if gs.tzinfo is None else gs.tz_convert("UTC")
                        if not (WIN_START - timedelta(days=1) <= gs <= WIN_END + timedelta(days=1)):
                            continue
                        ids = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
                        oc = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
                        if len(ids) != 2 or len(oc) != 2:
                            continue
                        out.append({"league": league, "slug": m.get("slug"), "condition": m["conditionId"],
                                    "game_start": gs.isoformat(), "outcomes": oc, "token_ids": ids,
                                    "closed": closed == "true"})
                if closed == "true" and b and pd.Timestamp(b[-1].get("startTime") or "2000-01-01") < WIN_START - timedelta(days=3):
                    break
    seen, uniq = set(), []
    for m in out:
        if m["condition"] not in seen:
            seen.add(m["condition"])
            uniq.append(m)
    return uniq


def best(names: list[str], outcome: str) -> float:
    return max((_sim(n, outcome) for n in names if n), default=0.0)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cand = pd.read_csv(CAND)
    kev = kalshi_events()
    ml = gamma_moneylines()
    rows, missing = {}, []
    for c in cand.itertuples():
        e = kev[c.kalshi_ticker]
        an = [e["names"].get(e["away"], ""), e["away"]]
        hn = [e["names"].get(e["home"], ""), e["home"]]
        kick = pd.Timestamp(c.kickoff_utc)
        top, top_s = None, 0.0
        for m in ml:
            if m["league"] != c.league.lower() or abs((pd.Timestamp(m["game_start"]) - kick).total_seconds()) > 36 * 3600:
                continue
            o0, o1 = m["outcomes"]
            s = max((best(an, o0) + best(hn, o1)) / 2, (best(an, o1) + best(hn, o0)) / 2)
            if s > top_s:
                top, top_s = m, s
        if top is None or top_s < 0.8:
            missing.append(c.kalshi_ticker)
            continue
        o0, o1 = top["outcomes"]
        straight, swapped = (best(an, o0) + best(hn, o1)) / 2, (best(an, o1) + best(hn, o0)) / 2
        orient = "ok" if straight - swapped > 0.1 else "flipped" if swapped - straight > 0.1 else "unclear"
        rows[c.kalshi_ticker] = {**top, "game_id": c.game_id, "match_score": round(top_s, 3),
                                 "collector_home_token": top["token_ids"][1], "orientation": orient}
    (OUT / "polymarket_com_map.json").write_text(json.dumps(rows, indent=1))
    shutil.copyfile(LIVE / "polymarket_us_map.json", OUT / "polymarket_us_map.json")
    o = pd.Series([r["orientation"] for r in rows.values()]).value_counts().to_dict()
    print(f"candidates {len(cand)}; polymarket.com mapped {len(rows)}; not found {len(missing)}; orientation {o}")
    for t in missing:
        print("  not found:", t)
    for t, r in rows.items():
        if r["orientation"] != "ok":
            print(f"  {r['orientation']}: {t} outcomes={r['outcomes']}")


if __name__ == "__main__":
    main()
