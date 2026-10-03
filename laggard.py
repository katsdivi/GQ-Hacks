"""Trade-the-laggard evaluator on recorded books (HYPOTHESIS_v2.md Amendment 2, one pre-registered setting).

Rule-7 file (same review rule as strategy.py / backtest.py): written on branch t14-laggard, reviewed line by
line by Divi before main. Synthetic tests only (tests/test_laggard.py); not run on any recorded game.

Setting (Amendment 2, fixed): Kalshi is the leader. A Kalshi mid jump of >= 4 cents within a trailing 10 s
window (leadlag.detect_jumps) opens a position on the follower venue if the gap Kalshi mid - follower mid, in
the jump direction, is >= 3 cents at that second; exit when the gap is < 1 cent or after 60 s; 10 contracts;
one position at a time (strategy.signals).
Mids: Amendment 2 mid rule (xcorr_lead.mid_snapshots / mid_grid): 1 s grid, defined only when both sides
exist. Seconds inside an excluded interval (book-wipe rule) have no mid on either venue, so no entry happens
there and a gap is never measured across one.
Timing: a decision from grid label g is knowable at (g + 1) s (strategy.decision_time_ns). The order is sent
then and fills at decision + venue delay + latency:
  polymarket.com: 3 s taker delay on sports markets (v2 Amendment 3 draft item 16; the frozen maps do not
  record market.trading.secondsDelay, so 3 s for every market). The polymarket.com latency curve therefore
  starts at 3 s: latency_s in the output is the total time from decision to fill (3, 3.25, ..., 13 s).
  Polymarket US: no documented delay, 0 s.
Fills (Amendment 2): the follower's recorded best ask (buy) / best bid (sell) in the last snapshot at or
before the fill time (backward as-of, ts <= fill time). If that snapshot has the needed side empty, the trade
is skipped ("no quote"): a side is never carried across an empty snapshot. Exits use the same rule; a round
trip whose exit has no quote is skipped as a whole and counted.
Costs: costs.fee on every fill: polymarket.com 0.05 x C x P x (1 - P) to 5 decimals; Polymarket US 0.0695 x C x
P x (1 - P), banker's rounding to the cent, by fill timestamp.
Sealed games (kickoff >= 2026-08-01) are refused unless holdout_run=True (the recorded books exist only from
2026-10-03, so the one pre-registered run is a holdout run, made once with the lead test).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import costs
import leadlag
import strategy
import xcorr_lead as X

NS = 1_000_000_000
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
SETTING = dict(jump_cents=4.0, window_s=10, entry_gap_cents=3.0, exit_gap_cents=1.0, timeout_s=60, qty=10)
VENUE_DELAY_S = {"polymarket": 3.0, "polymarket_us": 0.0}
LATENCIES_S = (0.0, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)     # added to the venue delay
LABELS = {"polymarket": "paper only; polymarket.com not available to US residents",
          "polymarket_us": "US-executable version (Polymarket US); state eligibility as in HYPOTHESIS_v2.md"}


def _grid(ticks: pd.DataFrame, venue: str, lo_g: int, hi_g: int, exclude) -> pd.Series:
    """Mid grid over [lo_g, hi_g]. mid_grid stops at the last snapshot; a quiet book keeps its state, so
    seconds after the last snapshot take that snapshot's mid (NaN if it was one-sided). None before the first."""
    m = X.mid_grid(X.mid_snapshots(ticks, venue))
    g = m.reindex(range(lo_g, hi_g + 1))
    if len(m):
        g.loc[int(m.index[-1]) + 1:] = m.iloc[-1]
    for a, b in exclude:
        g.loc[max(a, lo_g):min(b, hi_g)] = np.nan
    return g


def book(ticks: pd.DataFrame, venue: str) -> pd.DataFrame:
    """Follower snapshots: ts (ns, sorted), bid, ask; NaN = that side empty in that snapshot."""
    w = X._book_wide(ticks, venue)
    return pd.DataFrame({"ts": w.index.to_numpy(dtype="int64"), "bid": w["bid"].to_numpy(float),
                         "ask": w["ask"].to_numpy(float)})


def quote_at(q: pd.DataFrame, t_ns: int, side: str) -> float:
    """Best ask (side "ask") or bid of the last snapshot with ts <= t_ns; NaN if none or that side empty."""
    i = int(np.searchsorted(q["ts"].to_numpy(), t_ns, side="right")) - 1
    return float("nan") if i < 0 else float(q[side].iloc[i])


def signals(k_ticks: pd.DataFrame, o_ticks: pd.DataFrame, venue: str, lo_ns: int, hi_ns: int,
            exclude=(), setting: dict = SETTING) -> pd.DataFrame:
    """Entry/exit decisions from the two mid grids over [lo_ns, hi_ns). Uses grid labels <= g for label g."""
    lo_g, hi_g = lo_ns // NS, hi_ns // NS - 1
    gk = _grid(k_ticks, "kalshi", lo_g, hi_g, exclude)
    go = _grid(o_ticks, venue, lo_g, hi_g, exclude)
    jumps = leadlag.detect_jumps(gk, setting["jump_cents"], setting["window_s"])
    return strategy.signals(gk, go, jumps, setting["entry_gap_cents"], setting["exit_gap_cents"],
                            setting["timeout_s"], qty=setting["qty"])


def fill_trades(sig: pd.DataFrame, q: pd.DataFrame, venue: str, latency_s: float) -> pd.DataFrame:
    """Round trips at one latency. latency_s = total decision-to-fill time (venue delay included)."""
    lat = int(round(latency_s * NS))
    rows = []
    for s in sig.itertuples():
        t_in, t_out = s.entry_decision_ns + lat, s.exit_decision_ns + lat
        side_in, side_out = ("ask", "bid") if s.direction == 1 else ("bid", "ask")
        px_in, px_out = quote_at(q, t_in, side_in), quote_at(q, t_out, side_out)
        row = {"latency_s": latency_s, "entry_g": s.entry_g, "direction": s.direction, "qty": s.qty,
               "exit_reason": s.exit_reason, "entry_fill_ns": t_in, "exit_fill_ns": t_out}
        if np.isnan(px_in) or np.isnan(px_out):
            rows.append({**row, "filled": False, "skip": "no quote at entry" if np.isnan(px_in) else
                         "no quote at exit"})
            continue
        b_in, b_out = ("buy", "sell") if s.direction == 1 else ("sell", "buy")
        f_in = costs.fee(px_in, s.qty, b_in, venue, ts=t_in)
        f_out = costs.fee(px_out, s.qty, b_out, venue, ts=t_out)
        pnl = s.direction * (px_out - px_in) * s.qty - f_in - f_out
        rows.append({**row, "filled": True, "skip": "", "entry_px": px_in, "exit_px": px_out,
                     "fee_entry": f_in, "fee_exit": f_out, "pnl_cents": round(pnl * 100, 6),
                     "edge_cents_per_contract": round(pnl * 100 / s.qty, 6)})
    return pd.DataFrame(rows)


def evaluate_game(game_id: str, kickoff_utc, k_ticks: pd.DataFrame, o_ticks: pd.DataFrame, venue: str,
                  lo_ns: int, hi_ns: int, exclude=(), latencies=LATENCIES_S, holdout_run: bool = False,
                  setting: dict = SETTING) -> pd.DataFrame:
    """All latencies for one game on one follower venue. One row per (latency, signal)."""
    if venue not in VENUE_DELAY_S:
        raise ValueError(f"no follower venue {venue!r}")
    k = pd.Timestamp(kickoff_utc)
    k = k.tz_localize("UTC") if k.tzinfo is None else k.tz_convert("UTC")
    if k >= SEAL and not holdout_run:
        raise ValueError(f"{game_id}: kickoff {k} is a holdout game; needs holdout_run=True (run once)")
    sig = signals(k_ticks, o_ticks, venue, lo_ns, hi_ns, exclude, setting)
    q = book(o_ticks, venue)
    out = [fill_trades(sig, q, venue, VENUE_DELAY_S[venue] + L) for L in latencies]
    out = [o for o in out if len(o)]
    if not out:
        return pd.DataFrame(columns=["game_id", "venue", "latency_s", "filled"])
    return pd.concat(out, ignore_index=True).assign(game_id=game_id, venue=venue)


def latency_curve(trades: pd.DataFrame) -> pd.DataFrame:
    """out/latency_curve.csv contract: latency_s, n_trades, edge_cents_mean (net, per contract), 95% normal CI,
    pnl_total (dollars). Also n_skipped_no_quote. Filled round trips only."""
    rows = []
    for lat, d in trades.groupby("latency_s"):
        f = d[d["filled"].astype(bool)]
        e = f["edge_cents_per_contract"].to_numpy(float) if len(f) else np.array([])
        m = float(e.mean()) if len(e) else float("nan")
        se = float(e.std(ddof=1) / np.sqrt(len(e))) if len(e) > 1 else float("nan")
        rows.append({"latency_s": lat, "n_trades": len(e), "edge_cents_mean": m,
                     "edge_ci_low": m - 1.96 * se, "edge_ci_high": m + 1.96 * se,
                     "pnl_total": float(f["pnl_cents"].sum()) / 100 if len(f) else 0.0,
                     "n_skipped_no_quote": int((~d["filled"].astype(bool)).sum())})
    return pd.DataFrame(rows)
