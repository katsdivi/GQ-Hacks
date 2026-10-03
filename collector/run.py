"""T4 live recorder: Kalshi NFL + college football game markets -> local parquet (+ Tiger Data).

One asyncio process, one listener per venue, one writer.

Kalshi listener (REST polling mode, Decision D fallback; public endpoints, no key):
  * Every ~1 s: GET /markets?tickers=... in batches of 100 for every open KXNFLGAME /
    KXNCAAFGAME market whose game date is yesterday, today or tomorrow (US Eastern).
    Emits bid and ask rows (top of book) when they change. ts = receipt time.
  * When a market's volume changes, GET /markets/trades for it from the last trade seen.
    Trade rows carry Kalshi's created_time, so trades are lossless across restarts (the
    last trade time per market is saved in the state file and backfilled on start).
  * Market list refreshes every 10 min. Home/away from the event sub_title, cached.
  Websocket mode needs KALSHI_API_KEY_ID + KALSHI_PRIVATE_KEY_PATH; not built until a key
  exists to test against.

All prices are P(home wins): away markets are flipped (1 - p, bid <-> ask, buy <-> sell).

Writer: buffers rows, writes Tiger Data once per second if TIGER_DATABASE_URL is set, and
always writes a local parquet chunk every 30 s and on shutdown:
  data/live/<venue>/<YYYYMMDD>/<unix_s>_<pid>.parquet   (gitignored)
Local chunks add recv_ns (receipt time, ns) to the shared columns.

Holdout rule: this process only writes. It prints row counts, nothing else.

Usage:
  python -m collector.run                  # until killed (SIGINT / SIGTERM flush first)
  python -m collector.run --minutes 2      # short test run
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import signal
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from ingest.kalshi import trades_to_rows
from store import timescale

ROOT = Path(__file__).resolve().parents[1]
LIVE_DIR = ROOT / "data" / "live"
STATE_FILE = LIVE_DIR / "kalshi_state.json"
EVENTS_CACHE = LIVE_DIR / "kalshi_events.json"
GAPS_MD = ROOT / "GAPS.md"
BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ("KXNFLGAME", "KXNCAAFGAME")
ET = ZoneInfo("America/New_York")
BOOK_EVERY_S = 1.0
FLUSH_LOCAL_S = 30.0
FLUSH_TIGER_S = 1.0
REFRESH_MARKETS_S = 600
MAX_REQ_PER_S = 8.0          # Kalshi basic tier allows more; stay well under it
MAX_TRADE_POLLS_PER_LOOP = 6  # keep the book loop near 1 Hz; the rest wait for the next loop
GAP_LOG_S = 15.0
SHARED = ["ts", "venue", "market_id", "kind", "price", "size", "side"]
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                                       "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}


def log(msg: str) -> None:
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z {msg}", flush=True)


def log_gap(start_ns: int, end_ns: int, venue: str, cause: str) -> None:
    fmt = lambda ns: datetime.fromtimestamp(ns / 1e9, tz=ET).strftime("%a %b %d %H:%M:%S")
    with GAPS_MD.open("a") as f:
        f.write(f"| {fmt(start_ns)} | {fmt(end_ns)} | {venue} | {cause} | auto-logged by collector |\n")
    log(f"GAP {venue} {(end_ns - start_ns) / 1e9:.0f}s: {cause}")


class Writer:
    def __init__(self) -> None:
        self.buf_local: list[dict] = []
        self.buf_tiger: list[tuple] = []
        self.counts: dict[tuple, int] = {}
        self.conn = None
        if timescale.configured():
            try:
                self.conn = timescale.connect()
                timescale.ensure_schema(self.conn)
                log("Tiger Data connected")
            except Exception as e:  # keep recording locally
                log(f"Tiger Data unavailable, local parquet only: {type(e).__name__}: {e}")
        else:
            log("TIGER_DATABASE_URL not set: local parquet only")

    def add(self, df: pd.DataFrame, recv_ns: int) -> None:
        if df.empty:
            return
        recs = df[SHARED].to_dict("records")
        for r in recs:
            r["recv_ns"] = recv_ns
            k = (r["venue"], r["kind"])
            self.counts[k] = self.counts.get(k, 0) + 1
        self.buf_local += recs
        if self.conn is not None:
            self.buf_tiger += [(r["ts"], r["venue"], r["market_id"], r["kind"], r["price"], r["size"], r["side"])
                               for r in recs]

    def flush_tiger(self) -> None:
        if self.conn is None or not self.buf_tiger:
            return
        rows, self.buf_tiger = self.buf_tiger, []
        try:
            timescale.write_rows(self.conn, rows)
        except Exception as e:
            log(f"Tiger write failed ({type(e).__name__}: {e}); rows kept in local parquet; reconnecting")
            try:
                self.conn = timescale.connect()
            except Exception:
                self.conn = None

    def flush_local(self) -> None:
        if not self.buf_local:
            return
        rows, self.buf_local = self.buf_local, []
        df = pd.DataFrame(rows).astype({"ts": "int64", "venue": "string", "market_id": "string", "kind": "string",
                                        "price": "float64", "size": "float64", "side": "string", "recv_ns": "int64"})
        now = datetime.now(timezone.utc)
        for venue, part in df.groupby("venue"):
            d = LIVE_DIR / str(venue) / f"{now:%Y%m%d}"
            d.mkdir(parents=True, exist_ok=True)
            part.to_parquet(d / f"{int(now.timestamp())}_{os.getpid()}.parquet", index=False)


class KalshiPoller:
    def __init__(self, writer: Writer) -> None:
        self.w = writer
        self.s = requests.Session()
        self.markets: dict[str, dict] = {}       # ticker -> {away: bool}
        self.book: dict[str, tuple] = {}         # ticker -> (bid, ask, bid_sz, ask_sz) as last emitted
        self.volume: dict[str, float] = {}
        self.events = json.loads(EVENTS_CACHE.read_text()) if EVENTS_CACHE.exists() else {}
        st = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
        self.last_trade_s: dict[str, int] = st.get("last_trade_s", {})
        self.seen_ids: dict[str, set] = {}
        self.pending_trades: list[str] = []
        self.next_req = 0.0
        self.had_ok_poll = False
        self.last_ok_ns = time.time_ns()
        prev = st.get("last_ok_ns")
        if prev and (self.last_ok_ns - prev) / 1e9 > GAP_LOG_S:
            log_gap(prev, self.last_ok_ns, "kalshi", "collector not running (restart or crash); books lost, trades backfilled")

    def get(self, path: str, params: dict) -> dict:
        for attempt in range(6):
            wait = self.next_req - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.next_req = max(self.next_req, time.monotonic()) + 1.0 / MAX_REQ_PER_S
            try:
                r = self.s.get(BASE + path, params=params, timeout=15)
            except requests.RequestException as e:
                log(f"kalshi {path} {type(e).__name__}; retry {attempt + 1}")
                time.sleep(min(2 ** attempt, 30))
                continue
            if r.status_code == 429 or r.status_code >= 500:
                log(f"kalshi {path} HTTP {r.status_code}; backing off {min(2 ** attempt, 30)}s")
                time.sleep(min(2 ** attempt, 30))
                continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError(f"kalshi {path} failed after retries")

    def event_away_home(self, event: str) -> tuple[str, str] | None:
        if event not in self.events:
            ev = self.get(f"/events/{event}", {}).get("event", {})
            m = re.match(r"\s*(\S+)\s+(at|vs\.?)\s+(\S+)", ev.get("sub_title", ""))
            self.events[event] = [m.group(1), m.group(3), m.group(2)] if m else None
            EVENTS_CACHE.write_text(json.dumps(self.events))
        return self.events[event]

    def refresh_markets(self) -> None:
        today = datetime.now(ET).date()
        keep_dates = {today + timedelta(days=d) for d in (-1, 0, 1)}
        found: dict[str, dict] = {}
        for series in SERIES:
            cursor = None
            while True:
                p = {"series_ticker": series, "status": "open", "limit": 1000}
                if cursor:
                    p["cursor"] = cursor
                d = self.get("/markets", p)
                for m in d.get("markets", []):
                    code = m["event_ticker"].split("-")[1]
                    try:
                        gd = datetime(2000 + int(code[:2]), MONTHS[code[2:5]], int(code[5:7])).date()
                    except (KeyError, ValueError):
                        continue
                    if gd not in keep_dates:
                        continue
                    teams = self.event_away_home(m["event_ticker"])
                    if not teams:
                        log(f"skip {m['ticker']}: cannot parse away/home")
                        continue
                    team = m["ticker"].rsplit("-", 1)[1]
                    if team not in (teams[0], teams[1]):
                        log(f"skip {m['ticker']}: team {team} not in {teams}")
                        continue
                    found[m["ticker"]] = {"away": team == teams[0]}
                cursor = d.get("cursor")
                if not cursor:
                    break
        added = set(found) - set(self.markets)
        self.markets = found
        log(f"kalshi markets: {len(found)} open game markets in date window (+{len(added)} new)")

    def poll_books(self) -> None:
        tickers = sorted(self.markets)
        recv = time.time_ns()
        rows, changed = [], []
        for i in range(0, len(tickers), 100):
            d = self.get("/markets", {"tickers": ",".join(tickers[i:i + 100]), "limit": 1000})
            recv = time.time_ns()
            for m in d.get("markets", []):
                t = m["ticker"]
                if t not in self.markets:
                    continue
                f = lambda k: float(m[k]) if m.get(k) not in (None, "") else float("nan")
                bid, ask, bsz, asz = f("yes_bid_dollars"), f("yes_ask_dollars"), f("yes_bid_size_fp"), f("yes_ask_size_fp")
                vol = f("volume_fp")
                if t in self.volume and vol != self.volume[t]:
                    changed.append(t)
                elif t not in self.volume and t in self.last_trade_s:
                    changed.append(t)  # restart: backfill trades since the last one saved
                elif t not in self.volume:
                    self.last_trade_s[t] = int(time.time()) - 60
                self.volume[t] = vol
                snap = (bid, ask, bsz, asz)
                if snap == self.book.get(t):
                    continue
                self.book[t] = snap
                away = self.markets[t]["away"]
                # Home terms: away market's bid becomes home ask at 1 - bid, and vice versa.
                hb, ha, hbs, has = (1 - ask, 1 - bid, asz, bsz) if away else (bid, ask, bsz, asz)
                for kind, px, sz, side in (("bid", hb, hbs, "buy"), ("ask", ha, has, "sell")):
                    if px == px and 0 < px < 1:  # skip empty side (0 or 1 after flip, or NaN)
                        rows.append({"ts": recv, "venue": "kalshi", "market_id": t, "kind": kind,
                                     "price": round(px, 4), "size": sz, "side": side})
        if rows:
            self.w.add(pd.DataFrame(rows), recv)
        for t in changed:
            if t not in self.pending_trades:
                self.pending_trades.append(t)
        batch, self.pending_trades = self.pending_trades[:MAX_TRADE_POLLS_PER_LOOP], self.pending_trades[MAX_TRADE_POLLS_PER_LOOP:]
        for t in batch:
            self.poll_trades(t)

    def poll_trades(self, ticker: str) -> None:
        now_s = int(time.time())
        since = self.last_trade_s.get(ticker, now_s - 120)
        since = max(since - 2, now_s - 6 * 3600)
        raw, cursor = [], None
        while True:
            p = {"ticker": ticker, "min_ts": since, "limit": 1000}
            if cursor:
                p["cursor"] = cursor
            d = self.get("/markets/trades", p)
            raw += d.get("trades", [])
            cursor = d.get("cursor")
            if not cursor:
                break
        seen = self.seen_ids.setdefault(ticker, set())
        new = [r for r in raw if r["trade_id"] not in seen]
        if not new:
            return
        seen.update(r["trade_id"] for r in new)
        if len(seen) > 50_000:
            self.seen_ids[ticker] = set(r["trade_id"] for r in new)
        df = trades_to_rows(new, ticker, away=self.markets[ticker]["away"])
        self.w.add(df, time.time_ns())
        self.last_trade_s[ticker] = int(df["ts"].max() // 1_000_000_000)

    def save_state(self) -> None:
        STATE_FILE.write_text(json.dumps({"last_ok_ns": self.last_ok_ns, "last_trade_s": self.last_trade_s}))

    async def run(self, stop: asyncio.Event) -> None:
        last_refresh = 0.0
        while not stop.is_set():
            t0 = time.monotonic()
            try:
                if time.monotonic() - last_refresh > REFRESH_MARKETS_S:
                    await asyncio.to_thread(self.refresh_markets)
                    last_refresh = time.monotonic()
                await asyncio.to_thread(self.poll_books)
                now = time.time_ns()
                if self.had_ok_poll and (now - self.last_ok_ns) / 1e9 > GAP_LOG_S:
                    log_gap(self.last_ok_ns, now, "kalshi", "polling stalled (errors, rate limit or host asleep)")
                self.last_ok_ns, self.had_ok_poll = now, True
                self.save_state()
            except Exception as e:
                log(f"kalshi poll error {type(e).__name__}: {e}")
                await asyncio.sleep(2)
            await asyncio.sleep(max(0.0, BOOK_EVERY_S - (time.monotonic() - t0)))


async def writer_loop(w: Writer, stop: asyncio.Event) -> None:
    last_local, last_report = time.monotonic(), time.monotonic()
    while not stop.is_set():
        await asyncio.sleep(FLUSH_TIGER_S)
        await asyncio.to_thread(w.flush_tiger)
        if time.monotonic() - last_local >= FLUSH_LOCAL_S:
            await asyncio.to_thread(w.flush_local)
            last_local = time.monotonic()
        if time.monotonic() - last_report >= 300:
            log("rows since start: " + ", ".join(f"{v}/{k}={n:,}" for (v, k), n in sorted(w.counts.items())))
            last_report = time.monotonic()


async def main_async(minutes: float | None) -> None:
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    if minutes:
        loop.call_later(minutes * 60, stop.set)
    w = Writer()
    k = KalshiPoller(w)
    log(f"collector start pid {os.getpid()} (kalshi REST polling mode)")
    await asyncio.gather(k.run(stop), writer_loop(w, stop))
    w.flush_tiger()
    w.flush_local()
    k.save_state()
    log("collector stopped cleanly; rows: " + ", ".join(f"{v}/{kk}={n:,}" for (v, kk), n in sorted(w.counts.items())))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--minutes", type=float, help="stop after this many minutes (testing)")
    args = ap.parse_args()
    asyncio.run(main_async(args.minutes))


if __name__ == "__main__":
    main()
