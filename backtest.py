"""Fill simulation for strategy.signals on the follower venue B, with costs always charged.

Fill rule: decided at decision_ns (strategy.decision_time_ns), filled at decision_ns + latency.
Fill price comes from the follower's own observations at or before the fill time (as-of,
backward only):
  * book exists (bid and ask rows): buy at the as-of ask, sell at the as-of bid;
  * trades only: as-of last trade price + HALF_SPREAD for a buy, - HALF_SPREAD for a sell
    (fill_model = "trade+halfspread").
Fees: costs.fee on every fill (docs/research/fees.md, costs as if traded today). For Kalshi the
route is a parameter: "webull" (primary, default) or "direct" (comparison line).

Entry and exit fills can use different quote tables (HYPOTHESIS_v2.md Amendment 1). When
polymarket.com is traded, run.py passes entry quotes shifted EARLIER by D p90 and unshifted exit
quotes ("lower bound", both worse for us), and separately unshifted quotes for both ("upper
bound"). Kalshi quotes are never shifted.

Test set: games with kickoff on/after 2026-08-01 are refused unless final_test=True.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import costs

TEST_START = pd.Timestamp("2026-08-01", tz="UTC")


def check_allowed(game_id: str, kickoff_utc, final_test: bool = False) -> None:
    if game_id == "sample":
        return  # synthetic fake game, not real data
    k = pd.Timestamp(kickoff_utc)
    k = k.tz_localize("UTC") if k.tzinfo is None else k.tz_convert("UTC")
    if k >= TEST_START and not final_test:
        raise SystemExit(f"{game_id} kicks off {k} (sealed test set). Refusing without --final-test.")


def follower_quotes(ticks: pd.DataFrame, venue: str, shift_s: float = 0.0) -> tuple[pd.DataFrame, str]:
    """(ts, bid, ask) as-of table for the follower and the fill model it supports."""
    v = ticks[ticks["venue"] == venue].sort_values(["ts", "kind"], kind="stable")
    shift = int(round(shift_s * 1_000_000_000))
    book = v[v["kind"].isin(["bid", "ask"])]
    if len(book) and set(book["kind"].unique()) == {"bid", "ask"}:
        q = pd.DataFrame({"ts": book["ts"].to_numpy() - shift,
                          "bid": book["price"].where(book["kind"] == "bid").ffill().to_numpy(),
                          "ask": book["price"].where(book["kind"] == "ask").ffill().to_numpy()})
        return q.dropna().reset_index(drop=True), "book"
    tr = v[v["kind"] == "trade"]
    hs = costs.HALF_SPREAD
    q = pd.DataFrame({"ts": tr["ts"].to_numpy() - shift, "bid": tr["price"].to_numpy() - hs,
                      "ask": tr["price"].to_numpy() + hs})
    return q.reset_index(drop=True), "trade+halfspread"


def simulate(sig: pd.DataFrame, entry_quotes: pd.DataFrame, exit_quotes: pd.DataFrame, venue: str,
             latency_s: float = 1.0, kalshi_route: str | None = None) -> pd.DataFrame:
    """One row per round trip with entry/exit fill prices, fees and net P&L in cents."""
    if sig.empty:
        return pd.DataFrame(columns=["entry_fill_ns", "exit_fill_ns", "direction", "entry_px", "exit_px",
                                     "fees", "pnl_cents"])
    lat = int(round(latency_s * 1_000_000_000))
    qe = entry_quotes.sort_values("ts", kind="stable")
    qx = exit_quotes.sort_values("ts", kind="stable")

    def asof(q: pd.DataFrame, t_ns: int):
        i = np.searchsorted(q["ts"].to_numpy(), t_ns, side="right") - 1   # last quote with ts <= t_ns
        return None if i < 0 else q.iloc[i]

    rows = []
    for s in sig.itertuples():
        t_in, t_out = s.entry_decision_ns + lat, s.exit_decision_ns + lat
        a, b = asof(qe, t_in), asof(qx, t_out)
        if a is None or b is None:
            continue
        if s.direction == 1:      # long the follower: buy at ask, sell at bid
            px_in, px_out = a["ask"], b["bid"]
        else:                     # short: sell at bid, buy back at ask
            px_in, px_out = a["bid"], b["ask"]
        kw = {"route": kalshi_route} if venue == "kalshi" else {}
        fees = costs.fee(px_in, s.qty, "buy" if s.direction == 1 else "sell", venue, **kw) + \
            costs.fee(px_out, s.qty, "sell" if s.direction == 1 else "buy", venue, **kw)
        pnl = (s.direction * (px_out - px_in) * s.qty - fees) * 100
        rows.append({"entry_fill_ns": t_in, "exit_fill_ns": t_out, "direction": s.direction, "qty": s.qty,
                     "entry_px": round(float(px_in), 4), "exit_px": round(float(px_out), 4),
                     "fees": round(fees, 4), "pnl_cents": round(float(pnl), 4), "exit_reason": s.exit_reason})
    return pd.DataFrame(rows)


def to_contract(trades: pd.DataFrame, venue: str) -> pd.DataFrame:
    """out/signals/<game_id>.parquet: ts, action, venue, price, qty, fee, pnl_cum."""
    rows, cum = [], 0.0
    for t in trades.itertuples():
        rows.append({"ts": t.entry_fill_ns, "action": "enter_long" if t.direction == 1 else "enter_short",
                     "venue": venue, "price": t.entry_px, "qty": t.qty, "fee": t.fees / 2, "pnl_cum": cum})
        cum += t.pnl_cents / 100
        rows.append({"ts": t.exit_fill_ns, "action": "exit", "venue": venue, "price": t.exit_px, "qty": t.qty,
                     "fee": t.fees / 2, "pnl_cum": round(cum, 4)})
    return pd.DataFrame(rows, columns=["ts", "action", "venue", "price", "qty", "fee", "pnl_cum"])
