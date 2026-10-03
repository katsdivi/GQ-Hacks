"""Strategy B (HYPOTHESIS_v3.md "Strategy B" with Amendment 1 sections 3 and 5): Kalshi vs polymarket.com
disagreement, trading Kalshi only.

Rule-7 file: written on branch t13-strategy-a, reviewed line by line by Divi (docs/review/strategy_b_walkthrough.md).

Per game, window [ESPN kickoff - 30 min, ESPN kickoff + 4.5 h] (Amendment 1 section 3), 1 s grid (align.py):
  Price per venue: trailing 3 s median of that venue's trade prices (align.trade_median_events, window (t-3 s, t]),
    P(home), raw timestamps (polymarket.com block time, never shifted). Grid label g = last value at or before
    the end of second g. Kalshi = all trades of both team markets (tick contract: both already P(home)).
  Valid: d(g) = Kalshi(g) - polymarket.com(g) is valid only if BOTH venues have a trade in the 60 s ending at the
    end of second g, i.e. ts in ((g + 1) s - 60 s, (g + 1) s).
  Entry: d valid and |d| >= k with the same sign for m consecutive seconds (counted only after the previous exit);
    decision stamped at the end of the m-th second, (g + 1) s. Trade Kalshi toward polymarket.com: buy P(home) if
    d < 0, sell if d > 0. 10 contracts, one position at a time.
  Exit: first later second with d valid and |d| < 1 cent ("converged"), else at entry label + T ("timeout"),
    else at the last window second ("window end"). Decision at (exit label + 1) s.
  Fill (Amendment 1 section 5): the first Kalshi trade with ts in [decision + 1 s, decision + 60 s]; buy at
    trade + 0.5 cent, sell at trade - 0.5 cent
    (v3 training fill model, half-spread 0.5 cent). No such trade at entry or at exit -> the trade is skipped and
    counted (a round trip is never half filled).
  Costs: Webull $0.02 per contract per fill (entry and exit, primary); Kalshi direct 0.07 x C x P x (1 - P)
    rounded up to the cent per order (comparison), P = fill price (P(1 - P) is the same for either side).
  Net edge per trade = net P&L per contract, in cents.
Grid: k in {3, 5} cents x m in {10, 30} s x T in {60, 300} s.
Placebo (v3): Kalshi from game A against polymarket.com from game B, the next game in kickoff order with kickoff
  within 30 min after A (cyclic within the 30 min slot); A's window and A's Kalshi fills.
No prices are printed. Sealed games (kickoff >= 2026-08-01) are refused unless final_test=True.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

import align
from strategy_a import fee_kalshi_direct

NS = 1_000_000_000
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
K_GRID, M_GRID, T_GRID = (0.03, 0.05), (10, 30), (60, 300)
SETTINGS = [(k, m, t) for k in K_GRID for m in M_GRID for t in T_GRID]
PRE_S, POST_S = 30 * 60, int(4.5 * 3600)
MEDIAN_WINDOW_S = 3.0
STALE_S = 60
EXIT_GAP = 0.01
LATENCY_S = 1.0
FILL_WINDOW_S = 60
HALF_SPREAD = 0.005
QTY = 10
WEBULL_PER_CONTRACT = 0.02
MIN_TRADES_SELECT = 30
EPS = 1e-9


@dataclass
class Grid:
    lo_g: int
    d: np.ndarray          # Kalshi - polymarket.com per second (NaN if either price undefined)
    valid: np.ndarray      # bool: both venues traded in the 60 s ending at the end of the second


def venue_grid(trades: pd.DataFrame, venue: str, lo_g: int, hi_g: int) -> tuple[np.ndarray, np.ndarray]:
    """(price, has_recent_trade) per grid second lo_g..hi_g. Backward only: label g uses trades with
    ts < (g + 1) s."""
    n = hi_g - lo_g + 1
    tr = trades[(trades["venue"] == venue) & (trades["kind"] == "trade")]
    if tr.empty:
        return np.full(n, np.nan), np.zeros(n, bool)
    ev = align.trade_median_events(tr, venue, MEDIAN_WINDOW_S)
    # to_grid spans from the first trade (pre-window trades included), so reindexing carries the last value in
    px = align.to_grid(ev).reindex(np.arange(lo_g, hi_g + 1)).ffill()
    ts = np.sort(tr["ts"].to_numpy(dtype="int64"))
    ends = (np.arange(lo_g, hi_g + 1, dtype="int64") + 1) * NS        # end of each second
    last = np.searchsorted(ts, ends, side="left") - 1                 # last trade with ts < end
    last_ts = np.where(last >= 0, ts[np.clip(last, 0, None)], np.iinfo(np.int64).min)
    recent = (last >= 0) & (last_ts > ends - STALE_S * NS)
    return px.to_numpy(float), recent


def build_grid(k_trades: pd.DataFrame, p_trades: pd.DataFrame, lo_ns: int, hi_ns: int) -> Grid:
    lo_g, hi_g = lo_ns // NS, hi_ns // NS - 1
    kp, kr = venue_grid(k_trades, "kalshi", lo_g, hi_g)
    pp, pr = venue_grid(p_trades, "polymarket", lo_g, hi_g)
    d = kp - pp
    return Grid(lo_g, d, kr & pr & ~np.isnan(d))


def _runlen(c: np.ndarray) -> np.ndarray:
    """Length of the run of True ending at each index."""
    r = np.zeros(len(c), dtype=np.int64)
    run = 0
    for i, x in enumerate(c):
        run = run + 1 if x else 0
        r[i] = run
    return r


def signals(grid: Grid, k: float, m: int, t_s: int) -> pd.DataFrame:
    """Round-trip decisions on the grid. A label-g decision is stamped (g + 1) s."""
    d, v = grid.d, grid.valid
    n = len(d)
    up = v & (d >= k - EPS)
    dn = v & (d <= -k + EPS)
    r_up, r_dn = _runlen(up), _runlen(dn)
    conv = v & (np.abs(d) < EXIT_GAP - EPS)
    rows, s = [], 0
    while s < n:
        # first i >= s + m - 1 whose same-sign run reaches m counting only seconds >= s
        idx = np.arange(s + m - 1, n)
        ok = ((r_up[s + m - 1:] >= m) | (r_dn[s + m - 1:] >= m)) if len(idx) else np.array([], bool)
        hits = idx[ok]
        if not len(hits):
            break
        e = int(hits[0])
        direction = 1 if d[e] < 0 else -1               # buy Kalshi P(home) when Kalshi is below polymarket.com
        later = np.flatnonzero(conv[e + 1:min(e + t_s, n - 1) + 1])
        if len(later):
            x, reason = e + 1 + int(later[0]), "converged"
        elif e + t_s <= n - 1:
            x, reason = e + t_s, "timeout"
        else:
            x, reason = n - 1, "window end"
        rows.append({"entry_g": grid.lo_g + e, "exit_g": grid.lo_g + x, "direction": direction, "exit_reason": reason,
                     "entry_dec_ns": (grid.lo_g + e + 1) * NS, "exit_dec_ns": (grid.lo_g + x + 1) * NS,
                     "d_at_entry_cents": round(float(d[e]) * 100, 2)})
        s = x + 1
    return pd.DataFrame(rows, columns=["entry_g", "exit_g", "direction", "exit_reason", "entry_dec_ns",
                                       "exit_dec_ns", "d_at_entry_cents"])


def first_fill(k_ts: np.ndarray, k_px: np.ndarray, dec_ns: int) -> tuple[int, float] | None:
    """First Kalshi trade with ts in [dec + 1 s, dec + 60 s] (k_ts sorted)."""
    lo, hi = dec_ns + int(LATENCY_S * NS), dec_ns + FILL_WINDOW_S * NS
    i = int(np.searchsorted(k_ts, lo, side="left"))
    if i >= len(k_ts) or k_ts[i] > hi:
        return None
    return int(k_ts[i]), float(k_px[i])


def fill_trades(sig: pd.DataFrame, k_trades: pd.DataFrame, half_spread: float = HALF_SPREAD,
                fee_mult: float = 1.0) -> pd.DataFrame:
    tr = k_trades[(k_trades["venue"] == "kalshi") & (k_trades["kind"] == "trade")].sort_values("ts", kind="stable")
    k_ts, k_px = tr["ts"].to_numpy(dtype="int64"), tr["price"].to_numpy(float)
    out = []
    for s in sig.itertuples():
        a, b = first_fill(k_ts, k_px, s.entry_dec_ns), first_fill(k_ts, k_px, s.exit_dec_ns)
        row = s._asdict()
        row.pop("Index", None)
        if a is None or b is None:
            out.append({**row, "filled": False, "skip": "no entry fill" if a is None else "no exit fill"})
            continue
        p_in = round(a[1] + s.direction * half_spread, 4)        # buy pays up, sell receives less
        p_out = round(b[1] - s.direction * half_spread, 4)
        fw = 2 * WEBULL_PER_CONTRACT * QTY * fee_mult
        fd = (fee_kalshi_direct(p_in, QTY) + fee_kalshi_direct(p_out, QTY)) * fee_mult
        gross = s.direction * (p_out - p_in) * QTY
        out.append({**row, "filled": True, "skip": "", "entry_fill_ts": a[0], "exit_fill_ts": b[0],
                    "entry_px": p_in, "exit_px": p_out, "fee_webull": fw, "fee_direct": fd,
                    "pnl_webull": gross - fw, "pnl_direct": gross - fd,
                    "edge_webull_cents": (gross - fw) / QTY * 100, "edge_direct_cents": (gross - fd) / QTY * 100})
    return pd.DataFrame(out)


def window(espn_kickoff) -> tuple[int, int]:
    k = pd.Timestamp(espn_kickoff)
    k = k.tz_localize("UTC") if k.tzinfo is None else k.tz_convert("UTC")
    return k.value - PRE_S * NS, k.value + POST_S * NS


def evaluate_game(game_id: str, espn_kickoff, k_trades: pd.DataFrame, p_trades: pd.DataFrame,
                  settings=SETTINGS, final_test: bool = False, half_spread: float = HALF_SPREAD,
                  fee_mult: float = 1.0) -> tuple[pd.DataFrame, dict]:
    """All settings for one (Kalshi, polymarket.com) pair. Returns (trades, info with valid share)."""
    if pd.Timestamp(espn_kickoff) >= SEAL and not final_test:
        raise ValueError(f"{game_id}: kickoff on/after 2026-08-01 is sealed (needs final_test)")
    lo, hi = window(espn_kickoff)
    g = build_grid(k_trades, p_trades, lo, hi)
    out = []
    for k, m, t_s in settings:
        f = fill_trades(signals(g, k, m, t_s), k_trades, half_spread, fee_mult)
        if len(f):
            out.append(f.assign(k=k, m=m, T=t_s))
    info = {"game_id": game_id, "valid_share": float(g.valid.mean()) if len(g.valid) else 0.0}
    cols = ["k", "m", "T", "filled", "skip"]
    return (pd.concat(out, ignore_index=True).assign(game_id=game_id) if out
            else pd.DataFrame(columns=cols + ["game_id"])), info


def placebo_pairs(games: pd.DataFrame) -> list[tuple[str, str]]:
    """(A, B): B = the next game in kickoff order with kickoff within 30 min after A's slot start, cyclic
    within the slot (games whose kickoffs are within 30 min of the slot's first game). A game alone in its slot
    has no partner."""
    g = games.sort_values(["espn_kickoff", "game_id"]).reset_index(drop=True)
    ko = pd.to_datetime(g["espn_kickoff"], utc=True)
    pairs, i = [], 0
    while i < len(g):
        j = i
        while j + 1 < len(g) and (ko[j + 1] - ko[i]) <= pd.Timedelta(minutes=30):
            j += 1
        slot = list(g["game_id"][i:j + 1])
        if len(slot) > 1:
            pairs += [(slot[x], slot[(x + 1) % len(slot)]) for x in range(len(slot))]
        i = j + 1
    return pairs


def select_setting(summary: pd.DataFrame):
    """v3: best mean net edge per trade (Webull line) among settings with at least 30 trades."""
    s = summary[summary["n_trades"] >= MIN_TRADES_SELECT]
    if s.empty:
        return None
    b = s.sort_values(["edge_webull_cents", "n_trades"], ascending=[False, False]).iloc[0]
    return (float(b["k"]), int(b["m"]), int(b["T"]))
