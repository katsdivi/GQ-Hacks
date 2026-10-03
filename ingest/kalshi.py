"""T3: Kalshi game markets and trades, in the shared tick format.

Market data is public (no auth). Kalshi moves old data to /historical/* endpoints;
the cutoff comes from GET /historical/cutoff (trades_created_ts). Trades before it
are only on /historical/trades, newer ones only on /markets/trades. fetch_trades
asks whichever side(s) of the cutoff the window covers and dedupes on trade_id.

Field names checked against the live API on 2026-10-02:
  trade:  trade_id, ticker, created_time, yes_price_dollars, no_price_dollars,
          count_fp, taker_side (yes/no), taker_book_side, is_block_trade
  market: ticker, event_ticker, yes_sub_title, volume_fp, open_time, close_time, result
  event:  sub_title like "BUF at DEN (Jan 17)" -> away BUF, home DEN

Usage:
  python -m ingest.kalshi find --series KXNFLGAME --date 2026-01-17
  python -m ingest.kalshi trades --ticker KXNFLGAME-26JAN17BUFDEN-DEN \\
      --start 2026-01-17T19:30 --end 2026-01-18T01:30 --game-id <id>
  python -m ingest.kalshi merge --game-id <id> [--league NFL --home DEN --away BUF --kickoff ...]
  python -m ingest.kalshi overlay --game-id <id>

Games with kickoff on or after 2026-08-01 are sealed test games: trades, merge and
overlay refuse them unless --final-test is passed.
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from functools import lru_cache
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.elections.kalshi.com/trade-api/v2"
TICKS_DIR = ROOT / "data" / "ticks"
GAMES_CSV = ROOT / "data" / "games.csv"
TEST_START = pd.Timestamp("2026-08-01", tz="UTC")
COLS = ["ts", "venue", "market_id", "kind", "price", "size", "side"]

_session = requests.Session()


def _get(path: str, params: dict | None = None) -> dict:
    """GET with retry on 429 / 5xx. Public endpoints only."""
    for attempt in range(6):
        r = _session.get(BASE + path, params=params, timeout=60)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(2 ** attempt, 30))
            continue
        r.raise_for_status()
        return r.json()
    r.raise_for_status()
    return {}


def _paged(path: str, key: str, params: dict) -> list[dict]:
    out, cursor = [], None
    while True:
        p = dict(params, limit=1000)
        if cursor:
            p["cursor"] = cursor
        d = _get(path, p)
        out += d.get(key, [])
        cursor = d.get("cursor")
        if not cursor:
            return out


def _utc(x) -> pd.Timestamp:
    t = pd.Timestamp(x)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


@lru_cache(maxsize=1)
def trades_cutoff() -> pd.Timestamp:
    return _utc(_get("/historical/cutoff")["trades_created_ts"])


@lru_cache(maxsize=None)
def event_teams(event_ticker: str) -> tuple[str, str]:
    """(away, home) team codes from the event sub_title, e.g. 'BUF at DEN (Jan 17)'."""
    ev = _get(f"/events/{event_ticker}")["event"]
    m = re.match(r"\s*(\S+)\s+at\s+(\S+)", ev.get("sub_title", ""))
    if not m:
        raise ValueError(f"cannot parse away/home from {event_ticker}: {ev.get('sub_title')!r}")
    return m.group(1), m.group(2)


def find_game_markets(series: str, date) -> pd.DataFrame:
    """Every market in `series` whose event is dated `date` (event ticker code like 26JAN17).

    One row per team market, with away/home and whether this market pays on the home team.
    """
    d = pd.Timestamp(date)
    code = f"{d:%y}{d.strftime('%b').upper()}{d:%d}"
    rows = _paged("/historical/markets", "markets", {"series_ticker": series})
    rows += _paged("/markets", "markets", {"series_ticker": series})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["event_ticker"].str.split("-").str[1].str.startswith(code)]
    df = df.drop_duplicates("ticker").copy()
    if df.empty:
        return df
    teams = df["event_ticker"].map(event_teams)
    df["away"] = teams.str[0]
    df["home"] = teams.str[1]
    df["team"] = df["ticker"].str.rsplit("-", n=1).str[1]
    df["is_home"] = df["team"] == df["home"]
    df["volume"] = pd.to_numeric(df.get("volume_fp"), errors="coerce")
    keep = ["ticker", "event_ticker", "team", "away", "home", "is_home", "yes_sub_title",
            "status", "result", "volume", "open_time", "close_time", "expected_expiration_time"]
    return df[[c for c in keep if c in df.columns]].sort_values(["event_ticker", "is_home"]).reset_index(drop=True)


def _trades_raw(path: str, ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> list[dict]:
    return _paged(path, "trades", {"ticker": ticker, "min_ts": int(start.timestamp()),
                                    "max_ts": int(end.timestamp())})


def fetch_trades(ticker: str, start_utc, end_utc, away: bool = False) -> pd.DataFrame:
    """Kalshi trades for one market as shared-format rows.

    price is P(home wins): the YES price of a home market, or 1 - YES price of an away
    market (`away=True`). side is the taker's direction on that home-win price, so a YES
    taker on an away market is a sell.
    """
    start, end = _utc(start_utc), _utc(end_utc)
    cut = trades_cutoff()
    raw: list[dict] = []
    if start < cut:
        raw += _trades_raw("/historical/trades", ticker, start, min(end, cut))
    if end > cut:
        raw += _trades_raw("/markets/trades", ticker, max(start, cut), end)
    if not raw:
        return pd.DataFrame({c: pd.Series(dtype=t) for c, t in
                             zip(COLS, ["int64", "string", "string", "string", "float64", "float64", "string"])})

    t = pd.DataFrame(raw).drop_duplicates("trade_id")
    ts = pd.to_datetime(t["created_time"], utc=True, format="ISO8601").dt.as_unit("ns")
    p = pd.to_numeric(t["yes_price_dollars"], errors="coerce")
    side = t["taker_side"].map({"yes": "buy", "no": "sell"}).fillna("unknown")
    if away:
        p = 1.0 - p
        side = side.map({"buy": "sell", "sell": "buy", "unknown": "unknown"})
    df = pd.DataFrame({
        "ts": ts.astype("int64").to_numpy(), "venue": "kalshi", "market_id": ticker, "kind": "trade",
        "price": p.round(4).to_numpy(), "size": pd.to_numeric(t["count_fp"], errors="coerce").to_numpy(),
        "side": side.to_numpy(),
    })
    df = df[(df["ts"] >= start.value) & (df["ts"] <= end.value)].dropna(subset=["price"])
    df = df.sort_values("ts", kind="stable").reset_index(drop=True)
    return df.astype({"ts": "int64", "venue": "string", "market_id": "string", "kind": "string",
                      "price": "float64", "size": "float64", "side": "string"})


def _refuse_test(when: pd.Timestamp, final_test: bool, what: str) -> None:
    if when >= TEST_START and not final_test:
        sys.exit(f"{what} is on/after {TEST_START.date()} (sealed test set). Pass --final-test only "
                 "when Divi says 'final test run'.")


def _game_kickoff(game_id: str) -> pd.Timestamp | None:
    if not GAMES_CSV.exists():
        return None
    g = pd.read_csv(GAMES_CSV, dtype=str)
    row = g[g["game_id"] == game_id]
    return _utc(row["kickoff_utc"].iloc[0]) if len(row) and pd.notna(row["kickoff_utc"].iloc[0]) else None


def cmd_find(args) -> None:
    df = find_game_markets(args.series, args.date)
    with pd.option_context("display.width", 220, "display.max_rows", 200, "display.max_columns", 20):
        print(df.to_string(index=False) if len(df) else f"no {args.series} markets dated {args.date}")


def cmd_trades(args) -> None:
    _refuse_test(_utc(args.start), args.final_test, "window start")
    df = fetch_trades(args.ticker, args.start, args.end, away=args.away)
    print(f"{args.ticker}: {len(df):,} trades {args.start} to {args.end} "
          f"(flipped to home: {args.away}; historical cutoff {trades_cutoff()})")
    if len(df):
        per_min = pd.Series(1, index=pd.to_datetime(df["ts"], utc=True)).resample("1min").size()
        print(f"  price {df['price'].min():.2f} to {df['price'].max():.2f}, "
              f"contracts {df['size'].sum():,.0f}, trades/min median {per_min.median():.0f} max {per_min.max()}")
    if args.game_id:
        path = TICKS_DIR / f"{args.game_id}_kalshi.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
        print(f"saved {path.relative_to(ROOT)} (gitignored)")


def merge(game_id: str) -> pd.DataFrame:
    parts = [pd.read_parquet(p) for p in sorted(TICKS_DIR.glob(f"{game_id}_*.parquet"))
             if not p.stem.endswith("_truth")]
    if not parts:
        sys.exit(f"no data/ticks/{game_id}_<venue>.parquet files to merge")
    df = pd.concat(parts, ignore_index=True)[COLS]
    df = df.sort_values(["ts", "venue", "kind"], kind="stable").reset_index(drop=True)
    return df.astype({"ts": "int64", "venue": "string", "market_id": "string", "kind": "string",
                      "price": "float64", "size": "float64", "side": "string"})


def upsert_game(row: dict) -> None:
    cols = ["game_id", "league", "home", "away", "kickoff_utc", "cme_symbol", "kalshi_ticker", "polymarket_token"]
    g = pd.read_csv(GAMES_CSV, dtype=str) if GAMES_CSV.exists() else pd.DataFrame(columns=cols)
    g = g[g["game_id"] != row["game_id"]]
    g = pd.concat([g, pd.DataFrame([{c: row.get(c, "") for c in cols}])], ignore_index=True)
    g.to_csv(GAMES_CSV, index=False)


def cmd_merge(args) -> None:
    kickoff = _utc(args.kickoff) if args.kickoff else _game_kickoff(args.game_id)
    if kickoff is None:
        sys.exit("need --kickoff (or a games.csv row) to check the test-set seal")
    _refuse_test(kickoff, args.final_test, "kickoff")
    df = merge(args.game_id)
    path = TICKS_DIR / f"{args.game_id}.parquet"
    df.to_parquet(path, index=False)
    print(f"saved {len(df):,} rows to {path.relative_to(ROOT)}")
    print(df.groupby(["venue", "kind"]).size().to_string())
    if args.home:
        upsert_game({"game_id": args.game_id, "league": args.league, "home": args.home, "away": args.away_team,
                     "kickoff_utc": kickoff.strftime("%Y-%m-%dT%H:%M:%SZ"), "cme_symbol": args.cme_symbol or "",
                     "kalshi_ticker": args.kalshi_ticker or "", "polymarket_token": ""})
        print(f"upserted {args.game_id} into data/games.csv")


def cmd_overlay(args) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    kickoff = _game_kickoff(args.game_id)
    if kickoff is None:
        sys.exit(f"{args.game_id} has no kickoff in data/games.csv; run merge with --home/--kickoff first")
    _refuse_test(kickoff, args.final_test, "kickoff")
    df = pd.read_parquet(TICKS_DIR / f"{args.game_id}.parquet")
    tr = df[df["kind"] == "trade"].copy()
    tr["t"] = pd.to_datetime(tr["ts"], utc=True)

    fig, ax = plt.subplots(figsize=(13, 5))
    for venue, color in [("cme", "tab:blue"), ("kalshi", "tab:orange"), ("polymarket", "tab:green")]:
        s = tr[tr["venue"] == venue]
        if len(s):
            ax.step(s["t"], s["price"], where="post", lw=0.8, color=color, label=f"{venue} ({len(s):,} trades)")
    ax.axvline(kickoff, color="grey", ls="--", lw=0.8, label="kickoff")
    ax.set_ylim(0, 1)
    ax.set_ylabel("P(home wins)")
    ax.set_title(f"{args.game_id}: trade prices by venue (UTC)")
    ax.legend(loc="best")
    fig.tight_layout()
    out = ROOT / "out" / f"{args.game_id}_overlay.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=120)
    print(f"saved {out.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--final-test", action="store_true", help="allow sealed test games (Divi only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("find")
    p.add_argument("--series", default="KXNFLGAME")
    p.add_argument("--date", required=True, help="game date as in the event ticker, e.g. 2026-01-17")
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("trades")
    p.add_argument("--ticker", required=True)
    p.add_argument("--start", required=True, help="UTC")
    p.add_argument("--end", required=True, help="UTC")
    p.add_argument("--away", action="store_true", help="market pays on the AWAY team: flip with 1 - p")
    p.add_argument("--game-id", help="if set, save data/ticks/<game_id>_kalshi.parquet")
    p.set_defaults(func=cmd_trades)

    p = sub.add_parser("merge", help="combine data/ticks/<game_id>_<venue>.parquet into <game_id>.parquet")
    p.add_argument("--game-id", required=True)
    p.add_argument("--kickoff", help="UTC; needed if the game is not in games.csv yet")
    p.add_argument("--league", default="NFL")
    p.add_argument("--home")
    p.add_argument("--away-team")
    p.add_argument("--cme-symbol")
    p.add_argument("--kalshi-ticker")
    p.set_defaults(func=cmd_merge)

    p = sub.add_parser("overlay")
    p.add_argument("--game-id", required=True)
    p.set_defaults(func=cmd_overlay)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
