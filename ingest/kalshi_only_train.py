"""Kalshi-only TRAINING data for v3 Strategy A.

Downloads every KXNFLGAME / KXNCAAFGAME event with kickoff < 2026-08-01: trades for both
team markets (flipped to P(home wins), same tick contract as data/ticks) plus the settlement
result, and ESPN scoreboard kickoff times.

Outputs (nothing under data/ticks or data/games.csv is touched):
  data/raw/kalshi_only/<game_id>.parquet   Kalshi trades, columns ts,venue,market_id,kind,price,size,side
  data/raw/kalshi_only_games.csv           game_id, league, home, away, kalshi_event, kalshi_ticker,
                                           kickoff_utc_espn, kickoff_source, settlement_result, n_trades
  data/raw/espn/<league>_<YYYYMMDD>.json   raw ESPN scoreboard cache (write-skip)
  out/kalshi_only_train.log                progress log (stdout is also the log when run with nohup)

Trade window per game is kickoff - 2h to kickoff + 5h, the same as ingest/download_all.py.

SEALED TEST SET: events whose kickoff (ESPN, else the Kalshi event date) is on or after
2026-08-01T00:00Z are dropped BEFORE any trade download, and no ESPN scoreboard for a date on or
after 2026-08-01 is fetched. Asserted in code.

Usage: python -m ingest.kalshi_only_train [--limit N] [--rate R]
Idempotent and resumable: an existing per-game parquet is skipped.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from ingest import download_all as da
from ingest import kalshi as K

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUTD = RAW / "kalshi_only"
ESPN_DIR = RAW / "espn"
GAMES_OUT = RAW / "kalshi_only_games.csv"
PLAN = RAW / "t8_game_plan.csv"
LOG = ROOT / "out" / "kalshi_only_train.log"
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
PRE, POST = pd.Timedelta(hours=2), pd.Timedelta(hours=5)
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/{sport}/scoreboard"
SPORT = {"NFL": "nfl", "CFB": "college-football"}
# groups=80 and limit=1000 each cut the board to ~25 games; groups=90 alone gives the full FBS+FCS day (checked vs Kalshi counts).
ESPN_EXTRA = {"NFL": {}, "CFB": {"groups": "90"}}

_s = requests.Session()
_espn_next = [0.0]
_k_next = [0.0]
K_RATE = [2.5]


def log(msg: str) -> None:
    line = f"{pd.Timestamp.now(tz='UTC'):%Y-%m-%d %H:%M:%S}Z {msg}"
    print(line, flush=True)


# ---------- throttled, backoff-aware Kalshi GET (replaces ingest.kalshi._get for this run) ----------

def _kget(path: str, params: dict | None = None) -> dict:
    for attempt in range(8):
        w = _k_next[0] - time.monotonic()
        if w > 0:
            time.sleep(w)
        _k_next[0] = max(_k_next[0], time.monotonic()) + 1.0 / K_RATE[0]
        try:
            r = K._session.get(K.BASE + path, params=params, timeout=60)
        except requests.RequestException:
            time.sleep(min(2 ** attempt, 60))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(2 ** attempt, 60))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"GET {path} failed after retries")


K._get = _kget  # fetch_trades and trades_cutoff look this up at call time


# ---------- ESPN ----------

def espn_board(league: str, day: pd.Timestamp) -> list[dict]:
    assert day < SEAL, f"refusing to fetch ESPN scoreboard for sealed date {day}"
    ESPN_DIR.mkdir(parents=True, exist_ok=True)
    path = ESPN_DIR / f"{league.lower()}_{day:%Y%m%d}.json"
    if path.exists():
        return json.loads(path.read_text()).get("events", [])
    params = {"dates": f"{day:%Y%m%d}", **ESPN_EXTRA[league]}
    for attempt in range(7):
        w = _espn_next[0] - time.monotonic()
        if w > 0:
            time.sleep(w)
        _espn_next[0] = time.monotonic() + 0.3
        try:
            r = _s.get(ESPN.format(sport=SPORT[league]), params=params, timeout=60)
        except requests.RequestException:
            time.sleep(min(2 ** attempt, 60))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(2 ** attempt, 60))
            continue
        r.raise_for_status()
        path.write_text(json.dumps(r.json()))
        return r.json().get("events", [])
    raise RuntimeError(f"ESPN {params} failed after retries")


def _norm(x: str) -> str:
    x = x.lower().replace("&", " and ").replace("'", "").replace("\u2019", "")
    x = re.sub(r"\bst\b\.?", "state", x)
    x = re.sub(r"[^a-z0-9() ]", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return x.replace("north carolina state", "nc state")


def _names(team: dict) -> list[str]:
    return [_norm(str(team.get(k, ""))) for k in ("displayName", "location", "shortDisplayName", "name", "abbreviation")
            if team.get(k)]


def _name_score(kname: str, kcode: str, team: dict) -> float:
    kn = _norm(kname)
    if kcode and kcode.lower() == str(team.get("abbreviation", "")).lower():
        return 1.0
    best = 0.0
    for n in _names(team):
        if n.startswith(kn) or kn.startswith(n):
            best = max(best, 0.97 if len(kn) >= 4 or n == kn else 0.5)
        best = max(best, difflib.SequenceMatcher(None, kn, n).ratio())
    return best


# Hand-checked ESPN event ids for games ESPN has but our name match misses (docs/strategy_a_rules.md).
ESPN_EVENT_OVERRIDE = {
    "KXNCAAFGAME-25AUG30ALBYIOWA": "401752799",   # UAlbany Great Danes at Iowa Hawkeyes
}
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/{}/summary"


def espn_kickoff(league: str, ev: pd.Series, cache: dict) -> tuple[pd.Timestamp | None, str]:
    """Best ESPN game for a Kalshi event: date within +-1 day, both teams matched by name/code."""
    if ev["k_event"] in ESPN_EVENT_OVERRIDE:
        path = "nfl" if league.lower() == "nfl" else "college-football"
        d = requests.get(ESPN_SUMMARY.format(path), params={"event": ESPN_EVENT_OVERRIDE[ev["k_event"]]}, timeout=30).json()
        return K._utc(d["header"]["competitions"][0]["date"]), "espn_event_id"
    best, best_s = None, 0.0
    for dd in (-1, 0, 1):
        day = ev["k_date"].tz_localize("UTC") + pd.Timedelta(days=dd)
        if day >= SEAL:
            continue
        key = (league, day)
        if key not in cache:
            cache[key] = espn_board(league, day)
        for e in cache[key]:
            if not e.get("competitions"):
                continue
            comp = e["competitions"][0]
            teams = [c["team"] for c in comp["competitors"]]
            if len(teams) != 2:
                continue
            a, h = (ev["k_away"], ev["k_away_code"]), (ev["k_home"], ev["k_home_code"])
            s1 = _name_score(*a, teams[0]) + _name_score(*h, teams[1])
            s2 = _name_score(*a, teams[1]) + _name_score(*h, teams[0])
            s = max(s1, s2) - (0.02 * abs(dd))
            if s > best_s:
                best, best_s = comp.get("date") or e.get("date"), s
    if best is not None and best_s >= 1.6:
        return K._utc(best), "espn"
    return None, "none"


# ---------- plan ----------

def build_plan() -> pd.DataFrame:
    da.RATE[0] = K_RATE[0]
    frames = []
    for league in ("NFL", "CFB"):
        ev = da.kalshi_events(league)
        ev["k_date"] = pd.to_datetime(ev["k_date"])
        log(f"{league}: {len(ev)} Kalshi events listed (2-market events)")
        frames.append(ev)
    ev = pd.concat(frames, ignore_index=True)
    # Kalshi lists the same game twice (zero-volume duplicate with another event ticker). Keep the busiest.
    ev["_key"] = ev["league"] + ev["k_date"].dt.strftime("%Y%m%d") + ev.apply(
        lambda r: "|".join(sorted([r.k_away_code, r.k_home_code])), axis=1)
    ev = ev.sort_values("k_volume", ascending=False).drop_duplicates("_key").drop(columns="_key")
    n_zero = int((ev["k_volume"] <= 0).sum())
    ev = ev[ev["k_volume"] > 0].copy()
    log(f"dropped duplicate games, then {n_zero} zero-volume events")
    # Seal, step 1: Kalshi event date on or after Aug 1 is out before any ESPN or trade request.
    before = len(ev)
    ev = ev[ev["k_date"] < SEAL.tz_localize(None)].copy()
    log(f"seal: dropped {before - len(ev)} events dated on/after 2026-08-01 by Kalshi event date")

    cache: dict = {}
    ko, src = [], []
    for _, r in ev.sort_values("k_date").iterrows():
        t, s = espn_kickoff(r["league"], r, cache)
        ko.append(t)
        src.append(s)
    ev = ev.sort_values("k_date").reset_index(drop=True)
    ev["kickoff"] = ko
    ev["kickoff_source"] = src
    miss = ev["kickoff"].isna()
    # Fallback: Kalshi event date at 12:00Z (window then covers the whole US game day).
    ev.loc[miss, "kickoff"] = ev.loc[miss, "k_date"].dt.tz_localize("UTC") + pd.Timedelta(hours=12)
    ev.loc[miss, "kickoff_source"] = "kalshi_date"
    log(f"ESPN kickoff matched {int((~miss).sum())}, fallback to Kalshi date {int(miss.sum())}")
    # Seal, step 2: the real filter on kickoff.
    n0 = len(ev)
    ev = ev[ev["kickoff"] < SEAL].copy().reset_index(drop=True)
    log(f"seal: dropped {n0 - len(ev)} events with kickoff >= 2026-08-01Z")
    assert (ev["kickoff"] < SEAL).all()

    # game ids: reuse the T8 id when the Kalshi event is already there, else same scheme.
    old = pd.read_csv(PLAN, usecols=["k_event", "game_id"]) if PLAN.exists() else pd.DataFrame(columns=["k_event", "game_id"])
    idmap = dict(zip(old["k_event"], old["game_id"]))
    ev["in_t8"] = ev["k_event"].isin(idmap)

    def gid(r):
        if r.k_event in idmap:
            return idmap[r.k_event]
        pre = "nfl" if r.league == "NFL" else "cfb"
        return f"{pre}_{r.kickoff:%Y%m%d}_{r.k_away_code.lower()}_{r.k_home_code.lower()}"
    ev["game_id"] = ev.apply(gid, axis=1)
    assert ev["game_id"].is_unique, ev[ev["game_id"].duplicated(keep=False)][["k_event", "game_id"]]
    return ev


# ---------- settlement ----------

def settlement(home_ticker: str, away_ticker: str) -> str:
    """yes/no only. Kalshi "scalar" settlements (ties) are applied later by strategy_a.apply_scalar_settlements
    from data/raw/kalshi_market_meta.csv (ingest/kalshi_market_meta.py); this file is never edited for them."""
    def res(t):
        for path in (f"/historical/markets/{t}", f"/markets/{t}"):
            try:
                return _kget(path)["market"].get("result", "") or ""
            except requests.HTTPError:
                continue
        return ""
    h = res(home_ticker)
    if h in ("yes", "no"):
        return "1" if h == "yes" else "0"
    a = res(away_ticker)
    if a in ("yes", "no"):
        return "0" if a == "yes" else "1"
    return ""


# ---------- download ----------

def append_row(row: dict) -> None:
    pd.DataFrame([row]).to_csv(GAMES_OUT, mode="a", header=not GAMES_OUT.exists(), index=False)


def run(limit: int | None) -> None:
    OUTD.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(exist_ok=True)
    plan = build_plan()
    log("events per league (training): " + plan.groupby("league").size().to_dict().__repr__()
        + f"; already in T8 plan: {int(plan['in_t8'].sum())}")
    done = set(pd.read_csv(GAMES_OUT, dtype=str)["game_id"]) if GAMES_OUT.exists() else set()
    todo = plan[~plan["game_id"].isin(done)]
    if limit:
        todo = todo.head(limit)
    log(f"{len(plan)} planned, {len(done)} already in games table, {len(todo)} to process")
    max_ko, n_ok = None, 0
    for i, r in enumerate(todo.itertuples(), 1):
        assert r.kickoff < SEAL, f"sealed game reached download: {r.k_event}"
        path = OUTD / f"{r.game_id}.parquet"
        try:
            if path.exists():
                df = pd.read_parquet(path)
            else:
                start, end = r.kickoff - PRE, r.kickoff + POST
                df = pd.concat([K.fetch_trades(r.k_home_ticker, start, end, away=False),
                                K.fetch_trades(r.k_away_ticker, start, end, away=True)], ignore_index=True)
                df = df.sort_values("ts", kind="stable").reset_index(drop=True)
                df.to_parquet(path, index=False)
            sett = settlement(r.k_home_ticker, r.k_away_ticker)
        except Exception as e:
            log(f"ERROR {r.game_id} {r.k_event}: {type(e).__name__}: {str(e)[:200]}")
            continue
        append_row({"game_id": r.game_id, "league": r.league, "home": r.k_home_code, "away": r.k_away_code,
                    "kalshi_event": r.k_event, "kalshi_ticker": r.k_home_ticker,
                    "kickoff_utc_espn": r.kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "kickoff_source": r.kickoff_source, "settlement_result": sett, "n_trades": len(df)})
        n_ok += 1
        max_ko = r.kickoff if max_ko is None else max(max_ko, r.kickoff)
        if i % 10 == 0 or i == len(todo):
            log(f"{i}/{len(todo)} games done (last {r.game_id}, {len(df)} trades)")
    g = pd.read_csv(GAMES_OUT, dtype=str) if GAMES_OUT.exists() else pd.DataFrame()
    if len(g):
        mk = pd.to_datetime(g["kickoff_utc_espn"], utc=True).max()
        assert mk < SEAL
        log(f"games table rows {len(g)}; MAX kickoff of downloaded games: {mk} (seal {SEAL})")
        log("kickoff_source counts: " + g["kickoff_source"].value_counts().to_dict().__repr__())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, help="process only the first N games not yet done (testing)")
    ap.add_argument("--rate", type=float, default=K_RATE[0], help="max Kalshi requests per second")
    a = ap.parse_args()
    K_RATE[0] = a.rate
    run(a.limit)


if __name__ == "__main__":
    main()
