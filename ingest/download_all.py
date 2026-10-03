"""T8: download Kalshi + polymarket.com trades for every NFL and CFB training game on both venues.

Training only: kickoff before 2026-08-01 (sealed test set is never touched here).

Steps:
  1. Game lists. Kalshi: KXNFLGAME / KXNCAAFGAME markets from /historical/markets plus settled
     /markets. polymarket.com: game events from the Gamma API (NFL series 10187, CFB series
     10210), moneyline market only. Kickoff = Polymarket gameStartTime.
  2. Match each Kalshi event to one polymarket.com event: game date within 1 day and team
     names (Kalshi title "Away at Home Winner?", Polymarket outcomes [away, home]). NFL codes
     are matched through an alias table first. Unmatched or ambiguous games are logged.
  3. For each matched game, kickoff - 2 h to kickoff + 5 h:
       Kalshi: trades for both team markets (/historical/trades), flipped to P(home wins).
       polymarket.com: taker trades for the moneyline condition (data API), flipped to
       P(home wins). Timestamps are block time, whole seconds (see HYPOTHESIS_v2.md).
     Saves data/ticks/<game_id>_kalshi.parquet, _polymarket.parquet, merged <game_id>.parquet.
  4. Upserts data/games.csv. Writes out/download_manifest.csv (counts only) and appends
     failures to out/download_errors.csv. Games already on disk are skipped.

Kalshi's home team is canonical. If polymarket.com lists the teams the other way round
(neutral sites), its prices are flipped to Kalshi's home team and the manifest says so.

Usage:
  python -m ingest.download_all --plan            # build and save the matched game list only
  python -m ingest.download_all                   # download everything not on disk
  python -m ingest.download_all --limit 3         # first 3 games (testing)
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import time
import traceback
from pathlib import Path

import pandas as pd
import requests

from ingest.kalshi import COLS, merge, trades_to_rows

ROOT = Path(__file__).resolve().parents[1]
TICKS = ROOT / "data" / "ticks"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "out"
GAMES_CSV = ROOT / "data" / "games.csv"
PLAN_CSV = RAW / "t8_game_plan.csv"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
PMDATA = "https://data-api.polymarket.com"
TEST_START = pd.Timestamp("2026-08-01", tz="UTC")
PRE, POST = pd.Timedelta(hours=2), pd.Timedelta(hours=5)
PM_SERIES = {"NFL": "10187", "CFB": "10210"}
K_SERIES = {"NFL": "KXNFLGAME", "CFB": "KXNCAAFGAME"}
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
# Kalshi NFL code -> polymarket.com slug code, where they differ.
NFL_ALIAS = {"JAC": "jax", "LA": "la", "LV": "lv", "WAS": "was", "NE": "ne", "NO": "no",
             "GB": "gb", "KC": "kc", "SF": "sf", "TB": "tb"}
MAX_REQ_PER_S = 2.0     # Kalshi budget; the live recorder gets priority (override with --rate)

_s = requests.Session()
_next = [0.0]
RATE = [MAX_REQ_PER_S]


def get(url: str, params: dict | None = None, throttle: bool = True):
    for attempt in range(7):
        if throttle:
            w = _next[0] - time.monotonic()
            if w > 0:
                time.sleep(w)
            _next[0] = max(_next[0], time.monotonic()) + 1.0 / RATE[0]
        try:
            r = _s.get(url, params=params, timeout=60)
        except requests.RequestException:
            time.sleep(min(2 ** attempt, 60))
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(2 ** attempt, 60))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"GET {url} failed after retries")


def utc(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


# ---------- game lists ----------

def kalshi_events(league: str) -> pd.DataFrame:
    rows = []
    for path, extra in (("/historical/markets", {}), ("/markets", {"status": "settled"})):
        cur = None
        while True:
            p = {"series_ticker": K_SERIES[league], "limit": 1000, **extra}
            if cur:
                p["cursor"] = cur
            d = get(KALSHI + path, p)
            rows += d.get("markets", [])
            cur = d.get("cursor")
            if not cur:
                break
    m = pd.DataFrame(rows).drop_duplicates("ticker")
    m["vol"] = pd.to_numeric(m["volume_fp"], errors="coerce").fillna(0)
    out = []
    for ev, g in m.groupby("event_ticker"):
        title = g["title"].iloc[0]
        t = re.match(r"^(.*?)\s+(at|vs\.?)\s+(.*?)(\s+Winner\?)?$", title or "")
        code = ev.split("-")[1]
        try:
            gdate = pd.Timestamp(2000 + int(code[:2]), MONTHS[code[2:5]], int(code[5:7]))
        except (KeyError, ValueError):
            continue
        if not t or len(g) != 2:
            continue
        away_name, sep, home_name = t.group(1), t.group(2), t.group(3)
        by_name = {r.yes_sub_title: r for r in g.itertuples()}
        # Kalshi yes_sub_title can be shortened ("Los Angeles R"); match each team to its market.
        def pick(name):
            best = max(by_name, key=lambda s: difflib.SequenceMatcher(None, s.lower(), name.lower()).ratio())
            return by_name[best]
        a, h = pick(away_name), pick(home_name)
        if a.ticker == h.ticker:
            continue
        out.append({"league": league, "k_event": ev, "k_date": gdate, "k_sep": sep, "k_away": away_name,
                    "k_home": home_name, "k_away_ticker": a.ticker, "k_home_ticker": h.ticker,
                    "k_away_code": a.ticker.rsplit("-", 1)[1], "k_home_code": h.ticker.rsplit("-", 1)[1],
                    "k_volume": float(g["vol"].sum())})
    return pd.DataFrame(out)


def pm_events(league: str) -> pd.DataFrame:
    evs, off = [], 0
    while True:
        b = get(f"{GAMMA}/events", {"series_id": PM_SERIES[league], "limit": 100, "offset": off}, throttle=False)
        if not b:
            break
        evs += b
        off += len(b)
    rows = []
    for e in evs:
        ml = [m for m in (e.get("markets") or []) if m.get("sportsMarketType") == "moneyline"]
        if not ml:
            continue
        m = ml[0]
        dm = re.search(r"(\d{4}-\d{2}-\d{2})$", e["slug"])
        if not dm or not m.get("gameStartTime"):
            continue
        outcomes = json.loads(m["outcomes"]) if isinstance(m["outcomes"], str) else m["outcomes"]
        parts = e["slug"].split("-")
        rows.append({"pm_slug": e["slug"], "pm_date": pd.Timestamp(dm.group(1)), "kickoff_utc": utc(m["gameStartTime"]),
                     "pm_condition": m["conditionId"], "pm_away": outcomes[0], "pm_home": outcomes[1],
                     "pm_away_code": parts[1], "pm_home_code": parts[2]})
    return pd.DataFrame(rows)


def _norm(s: str) -> str:
    s = s.lower().replace("&", "and").replace(".", "").replace("'", "")
    s = re.sub(r"\bstate\b", "st", s)
    s = re.sub(r"\buniversity\b|\bof\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:  # "charlotte" vs "charlotte 49ers"
        return 0.92
    return difflib.SequenceMatcher(None, a, b).ratio()


def match_games(k: pd.DataFrame, p: pd.DataFrame, league: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    matched, unmatched = [], []
    used = set()
    for r in k.itertuples():
        cands = p[(p["pm_date"] - r.k_date).abs() <= pd.Timedelta(days=1)]
        best, best_score, best_flip = None, 0.0, False
        for c in cands.itertuples():
            if c.pm_slug in used:
                continue
            if league == "NFL":
                ka = NFL_ALIAS.get(r.k_away_code, r.k_away_code.lower())
                kh = NFL_ALIAS.get(r.k_home_code, r.k_home_code.lower())
                same = (ka, kh) == (c.pm_away_code, c.pm_home_code)
                swap = (ka, kh) == (c.pm_home_code, c.pm_away_code)
                score, flip = (1.0, False) if same else ((1.0, True) if swap else (0.0, False))
            else:
                s_same = (_sim(r.k_away, c.pm_away) + _sim(r.k_home, c.pm_home)) / 2
                s_swap = (_sim(r.k_away, c.pm_home) + _sim(r.k_home, c.pm_away)) / 2
                score, flip = (s_same, False) if s_same >= s_swap else (s_swap, True)
            if score > best_score:
                best, best_score, best_flip = c, score, flip
        if best is not None and best_score >= 0.8:
            used.add(best.pm_slug)
            matched.append({**r._asdict(), **best._asdict(), "match_score": round(best_score, 3), "pm_flipped": best_flip})
        else:
            unmatched.append({**r._asdict(), "best_score": round(best_score, 3),
                              "best_pm": best.pm_slug if best is not None else ""})
    drop = ["Index"]
    return (pd.DataFrame(matched).drop(columns=drop, errors="ignore"),
            pd.DataFrame(unmatched).drop(columns=drop, errors="ignore"))


def build_plan() -> pd.DataFrame:
    plans, misses = [], []
    for league in ("NFL", "CFB"):
        k, p = kalshi_events(league), pm_events(league)
        m, u = match_games(k, p, league)
        print(f"{league}: Kalshi events {len(k)}, polymarket.com game events {len(p)}, matched {len(m)}, unmatched {len(u)}")
        plans.append(m)
        misses.append(u.assign(league=league))
    plan = pd.concat(plans, ignore_index=True)
    plan = plan[plan["kickoff_utc"] < TEST_START].copy()
    plan["game_id"] = (plan["league"].str.lower() + "_" + plan["kickoff_utc"].dt.strftime("%Y%m%d") + "_"
                       + plan["k_away_code"].str.lower() + "_" + plan["k_home_code"].str.lower())
    plan = plan.sort_values("kickoff_utc").reset_index(drop=True)
    RAW.mkdir(parents=True, exist_ok=True)
    plan.to_csv(PLAN_CSV, index=False)
    OUT.mkdir(exist_ok=True)
    pd.concat(misses, ignore_index=True).to_csv(OUT / "download_unmatched.csv", index=False)
    print(f"plan: {len(plan)} training games on both venues -> {PLAN_CSV.relative_to(ROOT)}; "
          f"unmatched list -> out/download_unmatched.csv")
    return plan


# ---------- downloads ----------

def kalshi_trades(ticker: str, start: pd.Timestamp, end: pd.Timestamp, away: bool) -> pd.DataFrame:
    raw, cur = [], None
    while True:
        p = {"ticker": ticker, "min_ts": int(start.timestamp()), "max_ts": int(end.timestamp()), "limit": 1000}
        if cur:
            p["cursor"] = cur
        d = get(KALSHI + "/historical/trades", p)
        raw += d.get("trades", [])
        cur = d.get("cursor")
        if not cur:
            break
    return trades_to_rows(raw, ticker, away=away)


def pm_trades(condition: str, home_index: int, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.DataFrame, bool]:
    """polymarket.com taker trades for one moneyline condition, as P(home wins) rows.

    Returns (rows, truncated). The data API stops at offset 10,000 with limit 10,000, so a
    market with more taker trades than that cannot be fully paged; truncated=True then.
    """
    raw = []
    for off in (0, 10_000):
        b = get(f"{PMDATA}/trades", {"market": condition, "limit": 10_000, "offset": off, "takerOnly": "true"},
                throttle=False)
        if not isinstance(b, list) or not b:
            break
        raw += b
        if len(b) < 10_000:
            break
    truncated = len(raw) >= 20_000
    if not raw:
        return pd.DataFrame(columns=COLS), truncated
    t = pd.DataFrame(raw).drop_duplicates(["transactionHash", "asset", "size", "price", "side", "outcomeIndex"])
    ts = t["timestamp"].astype("int64") * 1_000_000_000
    is_home = t["outcomeIndex"].astype(int) == home_index
    price = t["price"].astype(float).where(is_home, 1.0 - t["price"].astype(float))
    side = t["side"].str.lower().map({"buy": "buy", "sell": "sell"}).fillna("unknown")
    side = side.where(is_home, side.map({"buy": "sell", "sell": "buy", "unknown": "unknown"}))
    df = pd.DataFrame({"ts": ts.to_numpy(), "venue": "polymarket", "market_id": condition, "kind": "trade",
                       "price": price.round(4).to_numpy(), "size": t["size"].astype(float).to_numpy(),
                       "side": side.to_numpy()})
    if truncated and len(df) and df["ts"].min() > start.value:
        truncated = True
    elif truncated:
        truncated = False  # the cap was hit, but what we have reaches back past the window start
    df = df[(df["ts"] >= start.value) & (df["ts"] <= end.value)].sort_values("ts", kind="stable")
    return df.astype({"ts": "int64", "venue": "string", "market_id": "string", "kind": "string",
                      "price": "float64", "size": "float64", "side": "string"}).reset_index(drop=True), truncated


def upsert_games(rows: list[dict]) -> None:
    cols = ["game_id", "league", "home", "away", "kickoff_utc", "cme_symbol", "kalshi_ticker", "polymarket_token"]
    g = pd.read_csv(GAMES_CSV, dtype=str) if GAMES_CSV.exists() else pd.DataFrame(columns=cols)
    new = pd.DataFrame(rows)[cols]
    g = pd.concat([g[~g["game_id"].isin(new["game_id"])], new], ignore_index=True)
    g.to_csv(GAMES_CSV, index=False)


def log_error(game_id: str, step: str, err: str) -> None:
    path = OUT / "download_errors.csv"
    first = not path.exists()
    pd.DataFrame([{"ts_utc": pd.Timestamp.now(tz="UTC").isoformat(), "game_id": game_id, "step": step,
                   "error": err[:500]}]).to_csv(path, mode="a", header=first, index=False)


def download(plan: pd.DataFrame, limit: int | None) -> None:
    manifest_path = OUT / "download_manifest.csv"
    done = set(pd.read_csv(manifest_path)["game_id"]) if manifest_path.exists() else set()
    todo = [r for r in plan.itertuples() if r.game_id not in done and not (TICKS / f"{r.game_id}.parquet").exists()]
    if limit:
        todo = todo[:limit]
    print(f"{len(plan)} planned, {len(plan) - len(todo)} already on disk or in manifest, {len(todo)} to download")
    games_rows = []
    for i, r in enumerate(todo, 1):
        kick = utc(r.kickoff_utc)
        if kick >= TEST_START:
            continue  # belt and braces: never fetch a test game
        start, end = kick - PRE, kick + POST
        try:
            k = pd.concat([kalshi_trades(r.k_home_ticker, start, end, away=False),
                           kalshi_trades(r.k_away_ticker, start, end, away=True)], ignore_index=True)
            k.to_parquet(TICKS / f"{r.game_id}_kalshi.parquet", index=False)
        except Exception as e:
            log_error(r.game_id, "kalshi", f"{type(e).__name__}: {e}")
            continue
        try:
            # outcomes are [away, home] on polymarket.com; if it lists the teams the other way
            # round from Kalshi, Kalshi's home team is outcome 0.
            home_index = 0 if r.pm_flipped else 1
            p, trunc = pm_trades(r.pm_condition, home_index, start, end)
            p.to_parquet(TICKS / f"{r.game_id}_polymarket.parquet", index=False)
        except Exception as e:
            log_error(r.game_id, "polymarket", f"{type(e).__name__}: {e}\n{traceback.format_exc()[-300:]}")
            continue
        merged = merge(r.game_id)
        merged.to_parquet(TICKS / f"{r.game_id}.parquet", index=False)
        row = {"game_id": r.game_id, "league": r.league, "kickoff_utc": kick.strftime("%Y-%m-%dT%H:%M:%SZ"),
               "n_kalshi_trades": len(k), "n_polymarket_trades": len(p), "polymarket_truncated": trunc,
               "pm_flipped": r.pm_flipped, "match_score": r.match_score}
        pd.DataFrame([row]).to_csv(manifest_path, mode="a", header=not manifest_path.exists(), index=False)
        games_rows.append({"game_id": r.game_id, "league": r.league, "home": r.k_home_code, "away": r.k_away_code,
                           "kickoff_utc": row["kickoff_utc"], "cme_symbol": "", "kalshi_ticker": r.k_home_ticker,
                           "polymarket_token": r.pm_condition})
        if len(games_rows) >= 20:
            upsert_games(games_rows)
            games_rows = []
        if i % 10 == 0 or i == len(todo):
            print(f"{pd.Timestamp.now(tz='UTC'):%H:%M:%S}Z {i}/{len(todo)} games done", flush=True)
    if games_rows:
        upsert_games(games_rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", action="store_true", help="only build the matched game list")
    ap.add_argument("--replan", action="store_true", help="rebuild the game list even if it exists")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--rate", type=float, default=MAX_REQ_PER_S, help="max Kalshi requests per second")
    a = ap.parse_args()
    RATE[0] = a.rate
    TICKS.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)
    plan = build_plan() if (a.plan or a.replan or not PLAN_CSV.exists()) else pd.read_csv(
        PLAN_CSV, parse_dates=["kickoff_utc", "k_date", "pm_date"])
    if a.plan:
        return
    download(plan, a.limit)


if __name__ == "__main__":
    main()
