"""SEALED holdout download for Strategies A and B (games with kickoff 2026-08-01 to 2026-10-03). Save only.

Requires --holdout-download. Writes ONLY under data/holdout_raw/ (gitignored); every write path is asserted to be
inside it. Prints and logs counts and ids only, never prices, results or statistics. Nothing here evaluates a
strategy: strategy_a / strategy_b still refuse these games unless final_test=True.

Steps (resumable; a game whose files exist is skipped):
  1. Kalshi game events (KXNFLGAME, KXNCAAFGAME) dated Aug 1 to Oct 3 with exactly two team markets: ids, title,
     yes_sub_title (team names) -> events.csv. No price fields kept.
  2. ESPN scoreboards for Jul 31 to Oct 4 -> espn/<league>_<date>.json; ESPN kickoff per event (same matching as
     ingest/kalshi_only_train.espn_kickoff). No ESPN match -> listed, not downloaded.
  3. Kalshi trades of both team markets in [ESPN kickoff - 2 h, + 5 h] -> kalshi/<game_id>.parquet (tick contract,
     P(home)). Settlement fields (status, result, settlement_value_dollars) -> settlements.csv.
  4. polymarket.com (current series 12185 NFL, 12756 CFB) moneylines matched to the Kalshi games
     (download_all.match_games) -> pm_map.csv; taker trades in the same window -> polymarket/<game_id>.parquet.
Throttle: Kalshi 4 requests/s (basic read limit 20/s; the backup collector shares this IP), polymarket.com and
ESPN 2/s. Every 10 min the collector is checked: a Kalshi feed outage (kalshi_ws not connected, or no delivered
message for > 60 s) or a new "429" line in out/collector.log pauses the download for 5 min, then rechecks.
Late games with no settlement yet stay unsettled (excluded by the existing rules); re-run later for settlements.

Usage: nice -n 19 python -m ingest.holdout_download --holdout-download
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import pandas as pd
import requests

from ingest import download_all as DA
from ingest import kalshi_only_train as T
from ingest.kalshi import trades_to_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "holdout_raw"
LOG = OUT / "download.log"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA, PMDATA = DA.GAMMA, DA.PMDATA
ESPN = "https://site.api.espn.com/apis/site/v2/sports/football/{}/scoreboard"
LO, HI = pd.Timestamp("2026-08-01"), pd.Timestamp("2026-10-03")
PRE, POST = pd.Timedelta(hours=2), pd.Timedelta(hours=5)
K_SERIES = {"NFL": "KXNFLGAME", "CFB": "KXNCAAFGAME"}
PM_SERIES = {"NFL": "12185", "CFB": "12756"}
MON = {m: i for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split(), 1)}
RATE = {"kalshi": 4.0, "pm": 2.0, "espn": 2.0}
CHECK_EVERY_S, PAUSE_S = 600, 300
HB_DIR = ROOT / "data" / "live" / "heartbeat"
COLLECTOR_LOG = ROOT / "out" / "collector.log"

_s = requests.Session()
_next = {k: 0.0 for k in RATE}
_state = {"last_check": 0.0, "n429": None, "pauses": 0}


def _path(p: Path) -> Path:
    p = p.resolve()
    assert OUT.resolve() in p.parents or p == OUT.resolve(), f"refusing to write outside {OUT}: {p}"
    return p


def log(msg: str) -> None:
    line = f"{pd.Timestamp.now(tz='America/New_York'):%H:%M:%S} {msg}"
    print(line, flush=True)
    with open(_path(LOG), "a") as f:
        f.write(line + "\n")


def collector_ok() -> tuple[bool, str]:
    files = sorted(HB_DIR.glob("*.jsonl"))
    last = {}
    if files:
        for line in open(files[-1]):
            try:
                r = json.loads(line)
                last[r["venue"]] = r
            except (ValueError, KeyError):
                continue
    now = pd.Timestamp.now(tz="UTC")
    k = last.get("kalshi_ws", {})
    ok_age = (now - pd.Timestamp(k["last_ok_utc"])).total_seconds() if k.get("last_ok_utc") else 1e9
    n429 = sum(1 for line in open(COLLECTOR_LOG) if "429" in line) if COLLECTOR_LOG.exists() else 0
    new429 = 0 if _state["n429"] is None else n429 - _state["n429"]
    _state["n429"] = n429
    if not k.get("connected") or ok_age > 60:
        return False, f"kalshi_ws connected={k.get('connected')} last_ok_age={ok_age:.0f}s"
    if new429 > 0:
        return False, f"{new429} new 429 lines in out/collector.log"
    return True, f"kalshi_ws ok (last_ok {ok_age:.0f}s), no new 429"


def guard() -> None:
    if time.monotonic() - _state["last_check"] < CHECK_EVERY_S:
        return
    while True:
        ok, why = collector_ok()
        _state["last_check"] = time.monotonic()
        log(f"collector check: {'OK' if ok else 'PAUSE'} ({why})")
        if ok:
            return
        _state["pauses"] += 1
        time.sleep(PAUSE_S)


def get(kind: str, url: str, params=None):
    guard()
    for attempt in range(8):
        w = _next[kind] - time.monotonic()
        if w > 0:
            time.sleep(w)
        _next[kind] = max(_next[kind], time.monotonic()) + 1.0 / RATE[kind]
        try:
            r = _s.get(url, params=params, timeout=60)
        except requests.RequestException:
            time.sleep(min(2 ** attempt, 60))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(2 ** attempt, 60))
            continue
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"giving up on {url}")


# ---------- 1. Kalshi events ----------

def kalshi_events() -> pd.DataFrame:
    rows = []
    for lg, series in K_SERIES.items():
        for status in ("settled", "closed", "open"):
            cur = None
            while True:
                p = {"series_ticker": series, "status": status, "limit": 1000}
                if cur:
                    p["cursor"] = cur
                d = get("kalshi", KALSHI + "/markets", p) or {}
                for m in d.get("markets", []):
                    code = m["event_ticker"].split("-")[1]
                    try:
                        dt = pd.Timestamp(2000 + int(code[:2]), MON[code[2:5]], int(code[5:7]))
                    except (KeyError, ValueError):
                        continue
                    if LO <= dt <= HI:
                        rows.append({"league": lg, "event": m["event_ticker"], "ticker": m["ticker"], "k_date": dt,
                                     "title": m.get("title") or "", "yes_sub_title": m.get("yes_sub_title") or ""})
                cur = d.get("cursor")
                if not cur:
                    break
    m = pd.DataFrame(rows).drop_duplicates("ticker")
    out, bad = [], []
    for ev, g in m.groupby("event"):
        if len(g) != 2:
            bad.append((ev, f"{len(g)} markets"))
            continue
        # Current-season titles are "<team> wins"; away/home come from the event sub_title ("LIB at DEL (Oct 2)"),
        # as in collector/run.py event_away_home. \S+ keeps hyphenated codes (M-OH).
        e = (get("kalshi", KALSHI + f"/events/{ev}") or {}).get("event", {})
        t = re.match(r"\s*(\S+)\s+(at|vs\.?)\s+(\S+)", e.get("sub_title") or "")
        names = dict(zip(g["ticker"], g["yes_sub_title"]))
        at, ht = (f"{ev}-{t.group(1)}", f"{ev}-{t.group(3)}") if t else (None, None)
        if not t or at not in names or ht not in names:
            bad.append((ev, "cannot place away/home"))
            continue
        out.append({"league": g["league"].iloc[0], "k_event": ev, "k_date": g["k_date"].iloc[0], "k_sep": t.group(2),
                    "k_away": names[at], "k_home": names[ht], "k_away_ticker": at, "k_home_ticker": ht,
                    "k_away_code": t.group(1), "k_home_code": t.group(3)})
    if bad:
        log(f"kalshi events not used: {len(bad)}: {bad}")
    return pd.DataFrame(out)


# ---------- 2. ESPN ----------

def espn_board(league: str, day: pd.Timestamp) -> list[dict]:
    path = _path(OUT / "espn" / f"{league.lower()}_{day:%Y%m%d}.json")
    if path.exists():
        return json.loads(path.read_text()).get("events", [])
    sport = "nfl" if league == "NFL" else "college-football"
    d = get("espn", ESPN.format(sport), {"dates": f"{day:%Y%m%d}", **T.ESPN_EXTRA[league]}) or {}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d))
    return d.get("events", [])


def espn_kickoff(ev, cache: dict):
    """ingest/kalshi_only_train.espn_kickoff without its training-only date filter (holdout download only)."""
    best, best_s = None, 0.0
    for dd in (-1, 0, 1):
        day = ev["k_date"] + pd.Timedelta(days=dd)
        key = (ev["league"], day)
        if key not in cache:
            cache[key] = espn_board(ev["league"], day)
        for e in cache[key]:
            comp = (e.get("competitions") or [None])[0]
            if not comp or len(comp.get("competitors", [])) != 2:
                continue
            teams = [c["team"] for c in comp["competitors"]]
            a, h = (ev["k_away"], ev["k_away_code"]), (ev["k_home"], ev["k_home_code"])
            s = max(T._name_score(*a, teams[0]) + T._name_score(*h, teams[1]),
                    T._name_score(*a, teams[1]) + T._name_score(*h, teams[0])) - 0.02 * abs(dd)
            if s > best_s:
                best, best_s = comp.get("date") or e.get("date"), s
    return (pd.Timestamp(best).tz_convert("UTC") if best is not None and best_s >= 1.6 else None)


# ---------- 3. Kalshi trades and settlements ----------

def kalshi_trades(ticker: str, start: pd.Timestamp, end: pd.Timestamp, away: bool) -> pd.DataFrame:
    raw = []
    for path in ("/historical/trades", "/markets/trades"):
        cur = None
        while True:
            p = {"ticker": ticker, "min_ts": int(start.timestamp()), "max_ts": int(end.timestamp()), "limit": 1000}
            if cur:
                p["cursor"] = cur
            d = get("kalshi", KALSHI + path, p) or {}
            raw += d.get("trades", [])
            cur = d.get("cursor")
            if not cur:
                break
    df = trades_to_rows(raw, ticker, away=away)
    return df[(df["ts"] >= start.value) & (df["ts"] <= end.value)].drop_duplicates()


def settlement_fields(ticker: str) -> dict:
    for path in (f"/historical/markets/{ticker}", f"/markets/{ticker}"):
        d = get("kalshi", KALSHI + path)
        if d and d.get("market"):
            m = d["market"]
            return {k: m.get(k) for k in ("status", "result", "settlement_value_dollars")}
    return {"status": "not found"}


# ---------- 4. polymarket.com ----------

def pm_events(league: str) -> pd.DataFrame:
    evs, off = [], 0
    while True:
        b = get("pm", f"{GAMMA}/events", {"series_id": PM_SERIES[league], "limit": 100, "offset": off})
        if not b:
            break
        evs += b
        off += len(b)
    rows = []
    for e in evs:
        ml = [m for m in (e.get("markets") or []) if m.get("sportsMarketType") == "moneyline"]
        dm = re.search(r"(\d{4}-\d{2}-\d{2})$", e.get("slug", ""))
        if not ml or not dm or not ml[0].get("gameStartTime"):
            continue
        m = ml[0]
        gs = pd.Timestamp(m["gameStartTime"]).tz_convert("UTC") if pd.Timestamp(m["gameStartTime"]).tzinfo \
            else pd.Timestamp(m["gameStartTime"]).tz_localize("UTC")
        if not (pd.Timestamp("2026-07-31", tz="UTC") <= gs <= pd.Timestamp("2026-10-05", tz="UTC")):
            continue
        oc = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
        parts = e["slug"].split("-")
        rows.append({"pm_slug": e["slug"], "pm_date": pd.Timestamp(dm.group(1)), "kickoff_utc": gs,
                     "pm_condition": m["conditionId"], "pm_away": oc[0], "pm_home": oc[1],
                     "pm_away_code": parts[1], "pm_home_code": parts[2]})
    return pd.DataFrame(rows)


def pm_trades(condition: str, home_index: int, start, end) -> tuple[pd.DataFrame, bool]:
    raw = []
    for off in (0, 10_000):
        b = get("pm", f"{PMDATA}/trades", {"market": condition, "limit": 10_000, "offset": off, "takerOnly": "true"})
        if not isinstance(b, list) or not b:
            break
        raw += b
        if len(b) < 10_000:
            break
    if not raw:
        return pd.DataFrame(columns=DA.COLS), False
    t = pd.DataFrame(raw).drop_duplicates(["transactionHash", "asset", "size", "price", "side", "outcomeIndex"])
    is_home = t["outcomeIndex"].astype(int) == home_index
    price = t["price"].astype(float).where(is_home, 1.0 - t["price"].astype(float))
    side = t["side"].str.lower().map({"buy": "buy", "sell": "sell"}).fillna("unknown")
    side = side.where(is_home, side.map({"buy": "sell", "sell": "buy", "unknown": "unknown"}))
    df = pd.DataFrame({"ts": t["timestamp"].astype("int64").to_numpy() * 1_000_000_000, "venue": "polymarket",
                       "market_id": condition, "kind": "trade", "price": price.round(4).to_numpy(),
                       "size": t["size"].astype(float).to_numpy(), "side": side.to_numpy()})
    truncated = len(raw) >= 20_000 and df["ts"].min() > start.value
    return df[(df["ts"] >= start.value) & (df["ts"] <= end.value)].sort_values("ts", kind="stable"), truncated


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout-download", action="store_true", required=True,
                    help="required: download the SEALED holdout (save only)")
    ap.parse_args()
    for d in ("kalshi", "polymarket", "espn"):
        _path(OUT / d).mkdir(parents=True, exist_ok=True)
    ok, why = collector_ok()
    log(f"start; collector {'OK' if ok else 'NOT OK'} ({why}); rates {RATE}")
    _state["last_check"] = time.monotonic()
    ev = kalshi_events()
    log(f"kalshi events with 2 markets, {LO.date()}..{HI.date()}: {len(ev)} "
        f"({(ev['league'] == 'NFL').sum()} NFL, {(ev['league'] == 'CFB').sum()} CFB)")
    cache, ko = {}, []
    for r in ev.itertuples():
        ko.append(espn_kickoff(r._asdict(), cache))
    ev["espn_kickoff"] = ko
    ev["game_id"] = [f"{r.league.lower()}_{(r.espn_kickoff if pd.notna(r.espn_kickoff) else pd.Timestamp(r.k_date, tz='UTC')):%Y%m%d}_"
                     f"{r.k_away_code.split('-')[-1].lower()}_{r.k_home_code.split('-')[-1].lower()}" for r in ev.itertuples()]
    ev.to_csv(_path(OUT / "events.csv"), index=False)
    no_espn = ev[ev["espn_kickoff"].isna()]
    log(f"ESPN kickoff found {ev['espn_kickoff'].notna().sum()}, not found {len(no_espn)}: {list(no_espn['k_event'])}")
    use = ev[ev["espn_kickoff"].notna()]
    sett, n_rows, fails = [], 0, []
    for i, r in enumerate(use.itertuples(), 1):
        f = _path(OUT / "kalshi" / f"{r.game_id}.parquet")
        if not f.exists():
            try:
                s, e = r.espn_kickoff - PRE, r.espn_kickoff + POST
                df = pd.concat([kalshi_trades(r.k_home_ticker, s, e, False), kalshi_trades(r.k_away_ticker, s, e, True)],
                               ignore_index=True).sort_values("ts", kind="stable")
                df.to_parquet(f, index=False)
                n_rows += len(df)
            except Exception as x:          # noqa: BLE001
                fails.append((r.game_id, "kalshi", type(x).__name__))
        for side, t in (("home", r.k_home_ticker), ("away", r.k_away_ticker)):
            sett.append({"game_id": r.game_id, "side": side, "ticker": t, **settlement_fields(t)})
        if i % 50 == 0:
            log(f"kalshi {i}/{len(use)} games, rows written this run {n_rows}, failures {len(fails)}")
    pd.DataFrame(sett).to_csv(_path(OUT / "settlements.csv"), index=False)
    st = pd.DataFrame(sett)
    log(f"kalshi done: {len(use)} games, rows this run {n_rows}, failures {fails}; settlement status counts "
        f"{st['status'].value_counts().to_dict()}")
    maps = []
    for lg in ("NFL", "CFB"):
        k = use[use["league"] == lg].rename(columns={"espn_kickoff": "kickoff"})
        p = pm_events(lg)
        if p.empty:
            continue
        m, u = DA.match_games(k, p, lg)
        log(f"polymarket.com {lg}: events {len(p)}, matched {len(m)}, unmatched kalshi {len(u)}")
        maps.append(m)
    pmap = pd.concat(maps, ignore_index=True) if maps else pd.DataFrame()
    pmap.to_csv(_path(OUT / "pm_map.csv"), index=False)
    n_pm, trunc = 0, []
    for r in pmap.itertuples():
        f = _path(OUT / "polymarket" / f"{r.game_id}.parquet")
        if f.exists():
            continue
        try:
            home_index = 0 if r.pm_flipped else 1
            s, e = r.kickoff - PRE, r.kickoff + POST
            df, tr = pm_trades(r.pm_condition, home_index, s, e)
            df.to_parquet(f, index=False)
            n_pm += len(df)
            if tr:
                trunc.append(r.game_id)
        except Exception as x:              # noqa: BLE001
            fails.append((r.game_id, "polymarket", type(x).__name__))
    log(f"polymarket.com done: {len(pmap)} matched games, rows this run {n_pm}, truncated {len(trunc)}, "
        f"failures {[f for f in fails if f[1] == 'polymarket']}; pauses {_state['pauses']}")
    log("finished")


if __name__ == "__main__":
    main()
