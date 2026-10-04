"""Webull paper orders for Strategy A (Andrew's spec). Sandbox only; never real money (CLAUDE.md rule 6).

One order per signal: buy the favorite's OWN Kalshi market, routed through Webull's event-contract API.
Payload fields follow the official SDK sample samples/trade/trade_client_v3_event.py
(webull-openapi-python-sdk 3.0.2, order_v3.place_order):
  combo_type NORMAL, client_order_id (unique), instrument_type EVENT, market US, symbol = Kalshi market
  ticker, order_type LIMIT, entrust_type QTY, time_in_force IOC, side BUY, quantity, limit_price,
  event_outcome yes/no.
[To confirm with Andrew / the sandbox: the SDK sample uses time_in_force DAY; IOC for EVENT is not shown.]

Modes:
  dry_run=True (default): no network. Logs the exact payload and returns an internal id with status
    "dry_run_not_sent". Never reports a fill.
  dry_run=False: sends to the sandbox host only (api.sandbox.webull.com); any other host is refused.
Rate limit: at most 30 requests per sliding 60 s (sandbox), enforced here by blocking before a request.
Keys: read from environment variables only (WEBULL_APP_KEY, WEBULL_APP_SECRET, WEBULL_ACCOUNT_ID), never
printed, logged or written. The SDK is imported lazily, so dry runs and tests need neither keys nor the SDK.
"""
from __future__ import annotations

import collections
import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

SANDBOX_HOST = "api.sandbox.webull.com"
REGION = "us"
RATE_N, RATE_WINDOW_S = 30, 60.0
ENV_KEYS = ("WEBULL_APP_KEY", "WEBULL_APP_SECRET", "WEBULL_ACCOUNT_ID")
LOG = Path("out/webull_orders.jsonl")


class RateLimiter:
    """Sliding window: at most n calls in any window_s seconds. acquire() blocks until a slot is free."""

    def __init__(self, n: int = RATE_N, window_s: float = RATE_WINDOW_S, clock=time.monotonic, sleep=time.sleep):
        self.n, self.window_s, self.clock, self.sleep = n, window_s, clock, sleep
        self.calls: collections.deque = collections.deque()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        with self.lock:
            while True:
                now = self.clock()
                while self.calls and now - self.calls[0] >= self.window_s:
                    self.calls.popleft()
                if len(self.calls) < self.n:
                    self.calls.append(now)
                    return
                self.sleep(self.window_s - (now - self.calls[0]))


def event_outcome(market_team: str, favorite: str) -> str:
    """Buying the favorite: "yes" on the favorite's own market, "no" on the opponent's market."""
    return "yes" if market_team == favorite else "no"


def build_payload(market_ticker: str, favorite: str, qty: int, limit_price: float,
                  client_order_id: str) -> dict:
    """Order on the favorite's own market (ticker f"{event}-{TEAM}"), so the outcome is "yes"."""
    team = market_ticker.rsplit("-", 1)[-1]
    if not (isinstance(qty, int) and qty > 0):
        raise ValueError(f"quantity must be a positive whole number of contracts, got {qty!r}")
    px = Decimal(str(round(float(limit_price), 2)))
    if not Decimal("0.01") <= px <= Decimal("0.99"):
        raise ValueError(f"limit price must be 0.01 to 0.99, got {limit_price!r}")
    return {"combo_type": "NORMAL", "client_order_id": client_order_id, "instrument_type": "EVENT",
            "market": "US", "symbol": market_ticker, "order_type": "LIMIT", "entrust_type": "QTY",
            "time_in_force": "IOC", "side": "BUY", "quantity": str(qty), "limit_price": str(px),
            "event_outcome": event_outcome(team, favorite)}


def _sdk_trade_client(host: str):
    """Real SDK client from env vars. Imported lazily; keys never leave this function."""
    missing = [k for k in ENV_KEYS if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"missing env vars: {', '.join(missing)}")
    from webull.core.client import ApiClient
    from webull.trade.trade_client import TradeClient
    api = ApiClient(os.environ["WEBULL_APP_KEY"], os.environ["WEBULL_APP_SECRET"], REGION)
    api.add_endpoint(REGION, host)
    return TradeClient(api)


@dataclass
class WebullPaper:
    dry_run: bool = True
    host: str = SANDBOX_HOST
    trade_client: object | None = None          # injected in tests; built from env vars otherwise
    limiter: RateLimiter = field(default_factory=RateLimiter)
    log_path: Path = LOG

    def __post_init__(self):
        if self.host != SANDBOX_HOST:
            raise ValueError(f"paper trading only: host must be {SANDBOX_HOST}")

    def _log(self, rec: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")

    def _client(self):
        if self.trade_client is None:
            self.trade_client = _sdk_trade_client(self.host)
        return self.trade_client

    def place_paper_order(self, market_ticker: str, favorite: str, qty: int, limit_price: float) -> dict:
        """Returns {internal_id, client_order_id, status, payload, response}. A fill is never inferred here:
        fills come only from the venue's order detail (order_status)."""
        coid = uuid.uuid4().hex
        payload = build_payload(market_ticker, favorite, qty, limit_price, coid)
        rec = {"internal_id": f"sl-{coid[:12]}", "client_order_id": coid, "ts_utc": time.time(),
               "dry_run": self.dry_run, "host": self.host, "payload": payload}
        if self.dry_run:
            rec.update(status="dry_run_not_sent", response=None)
            self._log(rec)
            return rec
        account = os.environ.get("WEBULL_ACCOUNT_ID")
        if not account:
            raise RuntimeError("missing env var WEBULL_ACCOUNT_ID")
        self.limiter.acquire()
        res = self._client().order_v3.place_order(account, [payload])
        body = _json(res)
        rec.update(status="sent" if res.status_code == 200 else f"http_{res.status_code}", response=body)
        self._log(rec)
        return rec

    def order_status(self, client_order_id: str) -> dict:
        """Venue order detail (the only source of fill information)."""
        if self.dry_run:
            return {"client_order_id": client_order_id, "status": "dry_run_not_sent"}
        self.limiter.acquire()
        res = self._client().order_v3.get_order_detail(os.environ["WEBULL_ACCOUNT_ID"], client_order_id)
        return {"client_order_id": client_order_id, "http": res.status_code, "response": _json(res)}


def _json(res):
    try:
        return res.json()
    except ValueError:
        return None
