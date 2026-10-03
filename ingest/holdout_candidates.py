"""Holdout candidate games: schedule metadata only. No prices, trades or recorded rows are read.

Writes data/live/holdout_candidates.csv, one row per game with kickoff in
[2026-10-02 22:00 UTC, 2026-10-04 10:00 UTC] (Fri 18:00 ET to Sun 06:00 ET) that has a Kalshi
KXNCAAFGAME or KXNFLGAME event. Kickoff comes from the ESPN public scoreboard.

Sources (all listing metadata):
  Kalshi   GET /events?series_ticker=..&with_nested_markets=true (open + settled) + data/live/kalshi_events.json
  ESPN     site.api.espn.com scoreboard, several CFB groups unioned
  Poly US  data/live/polymarket_us_map.json (written by the collector), match on kalshi_event
  Poly com the collector persists NO mapping (it keys tokens by conditionId only), so this reproduces
           PolymarketWS.refresh's universe (Gamma events in series 12185 NFL / 12756 CFB, moneyline
           markets with gameStartTime) and matches to Kalshi by team names. Gamma listing only.
Run: python -m ingest.holdout_candidates
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

from ingest.download_all import NFL_ALIAS, _sim

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "data" / "live"
OUT = LIVE / "holdout_candidates.csv"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/{}/scoreboard"
GAMMA = "https://gamma-api.polymarket.com"
SERIES = {"KXNFLGAME": "nfl", "KXNCAAFGAME": "cfb"}
MONTHS = {m: i + 1 for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"])}

# Explicit window (UTC): Fri Oct 2 18:00 ET = 22:00 UTC, Sun Oct 4 06:00 ET = 10:00 UTC.
WIN_START = pd.Timestamp("2026-10-02 22:00", tz="UTC")
WIN_END = pd.Timestamp("2026-10-04 10:00", tz="UTC")
# Kalshi events whose team names do not fuzzy-match ESPN (ESPN "Long Island University", "UL Monroe"; UNA at EKY
# missing from every scoreboard group). ESPN event ids hand-checked on 2026-10-03 against both teams' ESPN
# schedules; kickoff is read from the ESPN summary endpoint for that event.
ESPN_EVENT_OVERRIDE = {
    "KXNCAAFGAME-26OCT03MHULIU": "401867910",   # Mercyhurst at Long Island University
    "KXNCAAFGAME-26OCT03ULMUSA": "401871089",   # UL Monroe at South Alabama
    "KXNCAAFGAME-26OCT03UNAEKY": "401868143",   # North Alabama at Eastern Kentucky
}
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary"
ESPN_DATES = ["20261002", "20261003", "20261004"]
# ESPN caps each scoreboard response at 25 events (groups=80/81 alone return 25 of ~90), so union many
# conference group ids by event id.
CFB_GROUPS = [None] + [str(i) for i in range(1, 161)]
S = requests.Session()


def jget(url: str, params: dict | None = None):
    r = S.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def kalshi_events() -> dict[str, dict]:
    """event_ticker -> {league, away, home, names:{code:name}} for ET date codes Oct 2..4."""
    cache = json.loads((LIVE / "kalshi_events.json").read_text()) if (LIVE / "kalshi_events.json").exists() else {}
    out: dict[str, dict] = {}
    for series, league in SERIES.items():
        for status in ("open", "closed", "settled"):
            cur = None
            for _ in range(50):
                p = {"series_ticker": series, "status": status, "limit": 200, "with_nested_markets": "true"}
                if cur:
                    p["cursor"] = cur
                d = jget(KALSHI + "/events", p)
                for e in d.get("events", []):
                    ev = e["event_ticker"]
                    code = ev.split("-")[1]
                    try:
                        day = datetime(2000 + int(code[:2]), MONTHS[code[2:5]], int(code[5:7])).date()
                    except (KeyError, ValueError):
                        continue
                    if not (datetime(2026, 10, 2).date() <= day <= datetime(2026, 10, 4).date()):
                        continue
                    m = re.match(r"\s*(\S+)\s+(at|vs\.?)\s+(\S+)", e.get("sub_title", ""))
                    ah = cache.get(ev) or ([m.group(1), m.group(3)] if m else None)
                    if not ah:
                        continue
                    names = {mk["ticker"].rsplit("-", 1)[1]: mk.get("yes_sub_title") or "" for mk in e.get("markets", [])}
                    out[ev] = {"league": league, "away": ah[0], "home": ah[1], "names": names, "day": day,
                               "tickers": sorted(mk["ticker"] for mk in e.get("markets", []))}
                cur = d.get("cursor")
                if not cur:
                    break
    return out


def espn_games() -> list[dict]:
    from concurrent.futures import ThreadPoolExecutor
    games: dict[tuple, dict] = {}
    jobs = [(league, path, dt, g) for league, path in (("nfl", "nfl"), ("cfb", "college-football"))
            for dt in ESPN_DATES for g in (CFB_GROUPS if league == "cfb" else [None])]

    def fetch(j):
        league, path, dt, g = j
        p = {"dates": dt, "limit": 1000}
        if g:
            p["groups"] = g
        try:
            return league, jget(ESPN.format(path), p).get("events", [])
        except requests.RequestException:
            return league, []

    with ThreadPoolExecutor(8) as ex:
        for league, evs in ex.map(fetch, jobs):
            for e in evs:
                if e:
                    comp = e["competitions"][0]["competitors"]
                    t = {c["homeAway"]: c["team"] for c in comp}
                    if "home" not in t or "away" not in t:
                        continue
                    games[(league, e["id"])] = {"league": league, "kick": pd.Timestamp(e["date"]).tz_convert("UTC"),
                                                "away": t["away"], "home": t["home"]}
    return list(games.values())


def _names(t: dict) -> list[str]:
    return [t.get(k) or "" for k in ("location", "displayName", "shortDisplayName", "name")]


def _best(kname: str, team: dict) -> float:
    return max(_sim(kname, n) for n in _names(team))


def match_espn(ev: dict, games: list[dict]) -> dict | None:
    best, score = None, 0.0
    for g in games:
        if g["league"] != ev["league"]:
            continue
        if ev["league"] == "nfl":
            an, hn = ev["names"].get(ev["away"], ""), ev["names"].get(ev["home"], "")
            s1 = (_best(an, g["away"]) + _best(hn, g["home"])) / 2
            s2 = (_best(an, g["home"]) + _best(hn, g["away"])) / 2
            sc = max(s1, s2) if an and hn else 0.0
        else:
            an, hn = ev["names"].get(ev["away"], ""), ev["names"].get(ev["home"], "")
            if not an or not hn:
                continue
            s1 = (_best(an, g["away"]) + _best(hn, g["home"])) / 2
            s2 = (_best(an, g["home"]) + _best(hn, g["away"])) / 2   # Kalshi "vs" sometimes lists neutral-site order
            sc = max(s1, s2)
        if sc > score:
            best, score = g, sc
    return best if score >= 0.8 else None


def poly_us_mapped() -> set[str]:
    f = LIVE / "polymarket_us_map.json"
    m = json.loads(f.read_text()) if f.exists() else {}
    return {v["kalshi_event"] for v in m.values() if v.get("kalshi_event")}


def poly_com_games() -> list[dict]:
    """Reproduce PolymarketWS.refresh's universe (series 12185 NFL, 12756 CFB), listing metadata only."""
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
                    st = pd.Timestamp(e["startTime"]) if e.get("startTime") else None
                    if st is None or not (WIN_START - timedelta(days=1) <= st <= WIN_END + timedelta(days=1)):
                        continue
                    if not any(m.get("sportsMarketType") == "moneyline" and m.get("gameStartTime") for m in e.get("markets") or []):
                        continue
                    tm = {t.get("ordering"): t for t in e.get("teams") or []}
                    if "away" in tm and "home" in tm:
                        out.append({"league": league, "start": st, "away": tm["away"], "home": tm["home"], "title": e.get("title", "")})
                if closed == "true" and b and pd.Timestamp(b[-1].get("startTime") or "2000-01-01") < WIN_START - timedelta(days=3):
                    break
    return out


def match_poly(ev: dict, kick, pgames: list[dict]) -> bool:
    for g in pgames:
        if g["league"] != ev["league"]:
            continue
        if kick is not None and abs((g["start"] - kick).total_seconds()) > 36 * 3600:
            continue
        if ev["league"] == "nfl":
            an, hn = ev["names"].get(ev["away"], ""), ev["names"].get(ev["home"], "")
            pn = lambda t: [t.get("alias") or "", t.get("name") or ""]
            if an and hn and max((max(_sim(an, x) for x in pn(g["away"])) + max(_sim(hn, x) for x in pn(g["home"]))) / 2,
                                 (max(_sim(an, x) for x in pn(g["home"])) + max(_sim(hn, x) for x in pn(g["away"]))) / 2) >= 0.8:
                return True
        else:
            an, hn = ev["names"].get(ev["away"], ""), ev["names"].get(ev["home"], "")
            if not an or not hn:
                continue
            pn = lambda t: [t.get("alias") or "", t.get("name") or ""]
            s1 = (max(_sim(an, x) for x in pn(g["away"])) + max(_sim(hn, x) for x in pn(g["home"]))) / 2
            s2 = (max(_sim(an, x) for x in pn(g["home"])) + max(_sim(hn, x) for x in pn(g["away"]))) / 2
            if max(s1, s2) >= 0.8:
                return True
    return False


def main() -> None:
    kev = kalshi_events()
    games = espn_games()
    pus = poly_us_mapped()
    pgames = poly_com_games()
    rows, unmatched, outside = [], [], []
    for ev, e in sorted(kev.items()):
        if ev in ESPN_EVENT_OVERRIDE:
            d = jget(ESPN_SUMMARY, {"event": ESPN_EVENT_OVERRIDE[ev]})
            kick = pd.Timestamp(d["header"]["competitions"][0]["date"]).tz_convert("UTC")
        else:
            g = match_espn(e, games)
            kick = g["kick"] if g else None
        if kick is not None and not (WIN_START <= kick <= WIN_END):
            outside.append((ev, kick))
            continue
        day = kick if kick is not None else pd.Timestamp(e["day"], tz="UTC")
        gid = f"{e['league']}_{day:%Y%m%d}_{e['away'].lower()}_{e['home'].lower()}"
        if kick is None:
            unmatched.append(ev)
        rows.append({"game_id": gid, "league": e["league"].upper(), "kickoff_utc": kick.strftime("%Y-%m-%dT%H:%M:%SZ") if kick is not None else "",
                     "kalshi_ticker": ev, "polymarket_com_mapped": "y" if match_poly(e, kick, pgames) else "n",
                     "polymarket_us_mapped": "y" if ev in pus else "n",
                     "window_start_utc": (kick - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ") if kick is not None else ""})
    cols = ["game_id", "league", "kickoff_utc", "kalshi_ticker", "polymarket_com_mapped", "polymarket_us_mapped", "window_start_utc"]
    df = pd.DataFrame(rows, columns=cols)
    # Window assertion on every row that has a kickoff.
    k = pd.to_datetime(df.kickoff_utc.replace("", pd.NA).dropna(), utc=True)
    assert ((k >= WIN_START) & (k <= WIN_END)).all(), "kickoff outside holdout window"
    # The candidate set is fixed by this file, so no game may lack a kickoff.
    assert not unmatched, f"games with no ESPN kickoff: {unmatched}"
    df.to_csv(OUT, index=False)
    print(f"wrote {OUT}")
    print(f"rows: {len(df)}")
    print("by league:", df.league.value_counts().to_dict())
    com, us = df.polymarket_com_mapped.eq("y"), df.polymarket_us_mapped.eq("y")
    print(f"polymarket_com_mapped=y: {com.sum()}  polymarket_us_mapped=y: {us.sum()}  both: {(com & us).sum()}")
    print(f"Kalshi events dated Oct 2-4 (ET) with ESPN kickoff outside window (dropped): {len(outside)}")
    for ev, kk in outside:
        print("  outside:", ev, kk.strftime("%Y-%m-%dT%H:%MZ"))
    print(f"unmatched (no ESPN kickoff): {len(unmatched)}")
    for ev in unmatched:
        print("  unmatched:", ev)


if __name__ == "__main__":
    main()
