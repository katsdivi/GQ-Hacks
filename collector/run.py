"""T4 live recorder: Kalshi + polymarket.com NFL / college football game markets -> local parquet (+ Tiger Data).

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
always writes a local parquet chunk every 5 s and on shutdown:
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
LIVE_DIR = Path(os.getenv("COLLECTOR_LIVE_DIR", ROOT / "data" / "live"))  # override for test runs
STATE_FILE = LIVE_DIR / "kalshi_state.json"
EVENTS_CACHE = LIVE_DIR / "kalshi_events.json"
GAPS_MD = Path(os.getenv("COLLECTOR_GAPS_MD", ROOT / "GAPS.md"))
BASE = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = ("KXNFLGAME", "KXNCAAFGAME")
ET = ZoneInfo("America/New_York")
BOOK_EVERY_S = 1.0
FLUSH_LOCAL_S = 5.0
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
        recs = df.to_dict("records")
        for r in recs:
            r.setdefault("recv_ns", recv_ns)
            k = (r["venue"], r["kind"])
            self.counts[k] = self.counts.get(k, 0) + 1
        self.buf_local += recs
        if self.conn is not None:
            self.buf_tiger += [(r["ts"], r["venue"], r["market_id"], r["kind"], r["price"], r["size"], r["side"])
                               for r in recs if r["venue"] in ("kalshi", "polymarket")]

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
        df = pd.DataFrame(rows)
        types = {"ts": "int64", "venue": "string", "market_id": "string", "kind": "string", "price": "float64",
                 "size": "float64", "side": "string", "recv_ns": "int64", "src_ts_ns": "Int64", "tx_hash": "string"}
        df = df.astype({c: t for c, t in types.items() if c in df.columns})
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


class PolymarketWS:
    """polymarket.com public market websocket (no key): NFL + CFB moneyline books and trades.

    Game markets: open moneyline markets in the current-season NFL (12185) and CFB (12756)
    series with gameStartTime yesterday, today or tomorrow (US Eastern). Outcomes are
    [away, home]; away-token rows are flipped to P(home wins).
      bid/ask rows: top of book on change, ts = receipt time.
      trade rows (last_trade_price): ts = the event's own timestamp, plus recv_ns,
        src_ts_ns and tx_hash, so block time can be looked up later.
    Calibration markets (venue "polymarket_dcal"): the 10 busiest non-sports markets, trades
    only, used to measure the match-to-block delay D (HYPOTHESIS_v2.md). Never football.
    """

    URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    GAMMA = "https://gamma-api.polymarket.com"

    def __init__(self, writer: Writer) -> None:
        self.w = writer
        self.s = requests.Session()
        self.tokens: dict[str, dict] = {}     # asset_id -> {condition, home: bool, calib: bool}
        self.books: dict[str, dict] = {}      # asset_id -> {"bids": {px: sz}, "asks": {px: sz}}
        self.top: dict[str, tuple] = {}
        self.last_msg_ns = time.time_ns()

    def refresh(self) -> bool:
        today = datetime.now(ET).date()
        keep = {today + timedelta(days=d) for d in (-1, 0, 1)}
        toks: dict[str, dict] = {}
        for sid in (12185, 12756):
            off = 0
            while True:
                b = self.s.get(f"{self.GAMMA}/events", params={"series_id": sid, "closed": "false", "limit": 100,
                                                                "offset": off}, timeout=30).json()
                if not b:
                    break
                off += len(b)
                for e in b:
                    for m in e.get("markets") or []:
                        if m.get("sportsMarketType") != "moneyline" or not m.get("gameStartTime"):
                            continue
                        gs = pd.Timestamp(m["gameStartTime"])
                        gs = gs.tz_localize("UTC") if gs.tzinfo is None else gs
                        if gs.tz_convert(ET).date() not in keep:
                            continue
                        ids = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
                        if len(ids) != 2:
                            continue
                        toks[ids[0]] = {"condition": m["conditionId"], "home": False, "calib": False}
                        toks[ids[1]] = {"condition": m["conditionId"], "home": True, "calib": False}
        busy = self.s.get(f"{self.GAMMA}/markets", params={"active": "true", "closed": "false", "order": "volume24hr",
                                                           "ascending": "false", "limit": 40}, timeout=30).json()
        n_cal = 0
        for m in busy:
            if m.get("sportsMarketType") or m.get("gameStartTime") or n_cal >= 10:
                continue  # calibration set excludes every sports market
            ids = json.loads(m["clobTokenIds"]) if isinstance(m["clobTokenIds"], str) else m["clobTokenIds"]
            for t in ids:
                toks[t] = {"condition": m["conditionId"], "home": True, "calib": True}
            n_cal += 1
        changed = set(toks) != set(self.tokens)
        self.tokens = toks
        n_game = sum(1 for v in toks.values() if not v["calib"]) // 2
        log(f"polymarket markets: {n_game} game moneylines, {n_cal} calibration markets")
        return changed

    def _emit_top(self, asset: str, recv: int) -> None:
        info = self.tokens.get(asset)
        if not info or info["calib"]:
            return
        bk = self.books.get(asset)
        if not bk:
            return
        bb = max(bk["bids"]) if bk["bids"] else None
        ba = min(bk["asks"]) if bk["asks"] else None
        snap = (bb, bk["bids"].get(bb), ba, bk["asks"].get(ba))
        if snap == self.top.get(asset):
            return
        self.top[asset] = snap
        bid, bsz, ask, asz = snap
        if info["home"]:
            hb, hbs, ha, has = bid, bsz, ask, asz
        else:  # away token: its bid is a home ask at 1 - bid
            hb, hbs = (1 - ask if ask is not None else None), asz
            ha, has = (1 - bid if bid is not None else None), bsz
        rows = [{"ts": recv, "venue": "polymarket", "market_id": asset, "kind": k, "price": round(px, 4),
                 "size": sz, "side": sd}
                for k, px, sz, sd in (("bid", hb, hbs, "buy"), ("ask", ha, has, "sell"))
                if px is not None and 0 < px < 1]
        if rows:
            self.w.add(pd.DataFrame(rows), recv)

    def handle(self, x: dict, recv: int) -> None:
        et = x.get("event_type")
        if et == "book":
            a = x["asset_id"]
            self.books[a] = {"bids": {float(l["price"]): float(l["size"]) for l in x.get("bids", [])},
                             "asks": {float(l["price"]): float(l["size"]) for l in x.get("asks", [])}}
            self._emit_top(a, recv)
        elif et == "price_change":
            touched = set()
            for c in x.get("price_changes") or []:
                a = c["asset_id"]
                bk = self.books.setdefault(a, {"bids": {}, "asks": {}})
                side = bk["bids"] if c["side"].upper() == "BUY" else bk["asks"]
                px, sz = float(c["price"]), float(c["size"])
                if sz == 0:
                    side.pop(px, None)
                else:
                    side[px] = sz
                touched.add(a)
            for a in touched:
                self._emit_top(a, recv)
        elif et == "last_trade_price":
            a = x["asset_id"]
            info = self.tokens.get(a)
            if not info:
                return
            px = float(x["price"])
            side = {"BUY": "buy", "SELL": "sell"}.get(str(x.get("side")).upper(), "unknown")
            if not info["home"] and not info["calib"]:
                px = 1 - px
                side = {"buy": "sell", "sell": "buy"}.get(side, "unknown")
            src = int(x["timestamp"]) * 1_000_000 if x.get("timestamp") else None
            self.w.add(pd.DataFrame([{
                "ts": src or recv, "venue": "polymarket_dcal" if info["calib"] else "polymarket",
                "market_id": a, "kind": "trade", "price": round(px, 4), "size": float(x.get("size") or 0),
                "side": side, "recv_ns": recv, "src_ts_ns": src, "tx_hash": x.get("transaction_hash")}]), recv)

    async def run(self, stop: asyncio.Event) -> None:
        import websockets
        backoff, last_refresh = 1, 0.0
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.refresh)
                last_refresh = time.monotonic()
                if not self.tokens:
                    await asyncio.sleep(60)
                    continue
                async with websockets.connect(self.URL, ping_interval=None, max_size=None, open_timeout=20) as ws:
                    await ws.send(json.dumps({"assets_ids": sorted(self.tokens), "type": "market"}))
                    log(f"polymarket websocket subscribed to {len(self.tokens)} tokens")
                    backoff, last_ping = 1, time.monotonic()
                    while not stop.is_set():
                        if time.monotonic() - last_ping > 10:
                            await ws.send("PING")
                            last_ping = time.monotonic()
                        if time.monotonic() - last_refresh > REFRESH_MARKETS_S:
                            last_refresh = time.monotonic()
                            if await asyncio.to_thread(self.refresh):
                                log("polymarket market set changed; resubscribing")
                                break
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=5)
                        except asyncio.TimeoutError:
                            continue
                        recv = time.time_ns()
                        if (recv - self.last_msg_ns) / 1e9 > 120:
                            log_gap(self.last_msg_ns, recv, "polymarket", "no websocket messages")
                        self.last_msg_ns = recv
                        if msg in ("PONG", ""):
                            continue
                        d = json.loads(msg)
                        for x in (d if isinstance(d, list) else [d]):
                            self.handle(x, recv)
            except Exception as e:
                if stop.is_set():
                    break
                log(f"polymarket websocket {type(e).__name__}: {e}; reconnect in {backoff}s")
                t0 = time.time_ns()
                await asyncio.sleep(backoff)
                if backoff >= 8:
                    log_gap(t0 - backoff * 1_000_000_000, time.time_ns(), "polymarket", f"websocket reconnect ({type(e).__name__})")
                backoff = min(backoff * 2, 30)


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
    pmws = PolymarketWS(w)
    log(f"collector start pid {os.getpid()} (kalshi REST polling mode + polymarket websocket)")
    await asyncio.gather(k.run(stop), pmws.run(stop), writer_loop(w, stop))
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
