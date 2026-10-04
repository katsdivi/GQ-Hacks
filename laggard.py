"""Trade-the-laggard evaluator on recorded books (HYPOTHESIS_v2.md Amendment 2, one pre-registered setting).

Rule-7 file (same review rule as strategy.py / backtest.py): written on branch t14-laggard, reviewed line by
line by Divi before main. Synthetic tests only (tests/test_laggard.py); not run on any recorded game.

Setting (Amendment 2, fixed): Kalshi is the leader. A Kalshi mid jump of >= 4 cents within a trailing 10 s
window (leadlag.detect_jumps) opens a position on the follower venue if the gap Kalshi mid - follower mid, in
the jump direction, is >= 3 cents at that second; exit when the gap is < 1 cent or after 60 s; 10 contracts;
one position at a time (strategy.signals).
Mids: Amendment 2 mid rule (xcorr_lead.mid_snapshots / mid_grid): 1 s grid, defined only when both sides
exist. Breaks: every excluded interval (book-wipe rule, kickoff cut) and every heartbeat outage of either venue
(GAPS rows, passed in as `outages`). Inside a break neither venue has a mid, and after it a venue's mid stays
undefined until that venue's first snapshot received after the break ends: a mid is never carried across a
break, and none is carried past the window end. So no entry happens in or right after a break and a gap is
never measured across one.
Timing: a decision from grid label g is knowable at (g + 1) s (strategy.decision_time_ns). The order is sent
then and fills at decision + venue delay + latency:
  polymarket.com: the market's own sports taker delay (v2 Amendment 3): seconds_delay from
  data/live/holdout_seconds_delay.csv (CLOB field seconds_delay, read 2026-10-03 16:22 ET, frozen; all 112
  holdout markets at 1 s), joined by condition id. A market missing from the file gets 3 s (the help-center
  figure) and is counted (delay_source "missing->3"). latency_s in the output is the total time from decision
  to fill, so each market's latency curve starts at its own delay (1, 1.25, ..., 11 s for a 1 s market).
  Polymarket US: no documented delay, 0 s.
Fills (Amendment 2): the follower's recorded best ask (buy) / best bid (sell) in the last snapshot at or
before the fill time (backward as-of, ts <= fill time). Skipped and counted, never filled from an older quote:
the needed side empty in that snapshot ("no quote"); the fill time inside a break, or a break between that
snapshot and the fill time ("break"); the fill time at or after the window end ("after window end"). Exits
use the same rule; a round trip whose exit is skipped is skipped as a whole.
Capacity (polymarket.com): the collector records the size at the best level. A taker fill at the best quote
can take at most that level (deeper levels are worse prices), so capacity per trade = best-level size at the
fill time, in contracts, and in dollars at the fill cost (P for a buy, 1 - P for a sell, in home terms).
Polymarket US sizes are not recorded (the batch poll carries no sizes), so its capacity is NaN (not measurable).
Costs: costs.fee on every fill: polymarket.com 0.05 x C x P x (1 - P) to 5 decimals; Polymarket US 0.0695 x C x
P x (1 - P), banker's rounding to the cent, by fill timestamp.
Sealed games (kickoff >= 2026-08-01) are refused unless holdout_run=True (the recorded books exist only from
2026-10-03, so the one pre-registered run is a holdout run, made once with the lead test).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import costs
import leadlag
import strategy
import xcorr_lead as X

NS = 1_000_000_000
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
SETTING = dict(jump_cents=4.0, window_s=10, entry_gap_cents=3.0, exit_gap_cents=1.0, timeout_s=60, qty=10)
VENUE_DELAY_S = {"polymarket": 3.0, "polymarket_us": 0.0}  # polymarket.com 3.0: ONLY for a market missing from
#   holdout_seconds_delay.csv (0 of 112); every holdout market uses its own value (all 1 s, read 16:22 ET)
SECONDS_DELAY_CSV = Path("data/live/holdout_seconds_delay.csv")
LATENCIES_S = (0.0, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)     # added to the venue delay
TRADE_POST_S = int(4.5 * 3600)   # laggard trading ends at the latest at kickoff + 4.5 h (the lead-test window end)
PIN_S = 60                       # a pinned run is 60 s long (holdout_mid.PIN_S)
LABELS = {"polymarket": "paper only; polymarket.com not available to US residents",
          "polymarket_us": "US-executable version (Polymarket US); state eligibility as in HYPOTHESIS_v2.md"}


def trading_end_ns(kickoff_ns: int, pin_start_g: int | None) -> int:
    """Causal end of laggard trading (v2 Amendment 5 draft): the earlier of kickoff + 4.5 h and the first moment
    the 60 s pinned run is observable, (pin_start + PIN_S) s, since label g is known at (g + 1) s. Uses no data
    after that moment (the lead-test window ends at the pin START, which needs the next 60 s)."""
    end = int(kickoff_ns) + TRADE_POST_S * NS
    if pin_start_g is not None and pin_start_g == pin_start_g:
        end = min(end, (int(pin_start_g) + PIN_S) * NS)
    return end


def load_seconds_delay(path: Path = SECONDS_DELAY_CSV) -> dict:
    """condition id -> seconds_delay (int) from the frozen file; blank values are left out (missing)."""
    d = pd.read_csv(path, dtype={"market_id": str})
    d = d[pd.to_numeric(d["seconds_delay"], errors="coerce").notna()]
    return dict(zip(d["market_id"], d["seconds_delay"].astype(int)))


def venue_delay(venue: str, condition: str | None = None, delays: dict | None = None) -> tuple[float, str]:
    """(delay seconds, source). polymarket.com: the market's seconds_delay, else 3 s counted as missing."""
    if venue != "polymarket":
        return VENUE_DELAY_S[venue], "none documented"
    if delays is not None and condition in delays:
        return float(delays[condition]), "seconds_delay file"
    return VENUE_DELAY_S["polymarket"], "missing->3"


def _breaks_g(exclude, outages) -> list[tuple[int, int]]:
    """Grid-second intervals (inclusive): exclusions as given, outages (ns, [a, b)) widened to whole seconds."""
    out = [(int(a), int(b)) for a, b in exclude]
    out += [(int(a) // NS, (int(b) - 1) // NS) for a, b in outages]
    return sorted(out)


def _grid(ticks: pd.DataFrame, venue: str, lo_g: int, hi_g: int, breaks) -> pd.Series:
    """Mid grid over [lo_g, hi_g]. mid_grid stops at the last snapshot; a quiet book keeps its state, so
    seconds after the last snapshot take that snapshot's mid (NaN if it was one-sided), up to the window end
    only. Inside a break the mid is NaN, and after it the mid stays NaN until this venue's first snapshot
    received after the break (no carry across a break). None before the first snapshot."""
    snap = X.mid_snapshots(ticks, venue)
    m = X.mid_grid(snap)
    g = m.reindex(range(lo_g, hi_g + 1))
    if len(m):
        g.loc[int(m.index[-1]) + 1:] = m.iloc[-1]
    labels = np.unique(snap.index.to_numpy() // NS) if len(snap) else np.array([], dtype="int64")
    for a, b in breaks:
        i = np.searchsorted(labels, b, side="right")      # first snapshot second after the break
        resume = int(labels[i]) if i < len(labels) else hi_g + 1
        g.loc[max(a, lo_g):min(resume - 1, hi_g)] = np.nan
    return g


def book(ticks: pd.DataFrame, venue: str) -> pd.DataFrame:
    """Follower snapshots: ts (ns, sorted), bid, ask, bid_size, ask_size; NaN = that side empty (or no size)."""
    w = X._book_wide(ticks, venue)
    out = pd.DataFrame({"ts": w.index.to_numpy(dtype="int64"), "bid": w["bid"].to_numpy(float),
                        "ask": w["ask"].to_numpy(float)})
    b = ticks[(ticks["venue"] == venue) & ticks["kind"].isin(["bid", "ask"])]
    if "size" in b and len(b):
        sz = b.pivot_table(index="ts", columns="kind", values="size", aggfunc="last").reindex(w.index)
        for k in ("bid", "ask"):
            out[f"{k}_size"] = sz[k].to_numpy(float) if k in sz else np.nan
    else:
        out["bid_size"] = out["ask_size"] = np.nan
    return out


def quote_at(q: pd.DataFrame, t_ns: int, side: str, breaks_ns=(), end_ns: int | None = None) -> tuple:
    """(price, size, skip) for best ask (side "ask") or bid of the last snapshot with ts <= t_ns.
    skip is "" when usable. Never uses a snapshot from before a break that starts at or before t_ns, and never
    fills at or after the window end."""
    if end_ns is not None and t_ns >= end_ns:
        return float("nan"), float("nan"), "after window end"
    i = int(np.searchsorted(q["ts"].to_numpy(), t_ns, side="right")) - 1
    if i < 0:
        return float("nan"), float("nan"), "no quote"
    snap_ts = int(q["ts"].iloc[i])
    for a, b in breaks_ns:
        if a <= t_ns and snap_ts < b:          # fill in the break, or the snapshot predates the break's end
            return float("nan"), float("nan"), "break"
    px = float(q[side].iloc[i])
    if np.isnan(px):
        return px, float("nan"), "no quote"
    return px, float(q[f"{side}_size"].iloc[i]) if f"{side}_size" in q else float("nan"), ""


def signals(k_ticks: pd.DataFrame, o_ticks: pd.DataFrame, venue: str, lo_ns: int, hi_ns: int,
            exclude=(), setting: dict = SETTING, outages=()) -> pd.DataFrame:
    """Entry/exit decisions from the two mid grids over [lo_ns, hi_ns). Uses grid labels <= g for label g."""
    lo_g, hi_g = lo_ns // NS, hi_ns // NS - 1
    br = _breaks_g(exclude, outages)
    gk = _grid(k_ticks, "kalshi", lo_g, hi_g, br)
    go = _grid(o_ticks, venue, lo_g, hi_g, br)
    jumps = leadlag.detect_jumps(gk, setting["jump_cents"], setting["window_s"])
    return strategy.signals(gk, go, jumps, setting["entry_gap_cents"], setting["exit_gap_cents"],
                            setting["timeout_s"], qty=setting["qty"])


def fill_trades(sig: pd.DataFrame, q: pd.DataFrame, venue: str, latency_s: float, breaks_ns=(),
                end_ns: int | None = None) -> pd.DataFrame:
    """Round trips at one latency. latency_s = total decision-to-fill time (venue delay included)."""
    lat = int(round(latency_s * NS))
    rows = []
    for s in sig.itertuples():
        t_in, t_out = s.entry_decision_ns + lat, s.exit_decision_ns + lat
        side_in, side_out = ("ask", "bid") if s.direction == 1 else ("bid", "ask")
        px_in, sz_in, sk_in = quote_at(q, t_in, side_in, breaks_ns, end_ns)
        px_out, _, sk_out = quote_at(q, t_out, side_out, breaks_ns, end_ns)
        row = {"latency_s": latency_s, "entry_g": s.entry_g, "direction": s.direction, "qty": s.qty,
               "exit_reason": s.exit_reason, "entry_fill_ns": t_in, "exit_fill_ns": t_out}
        if sk_in or sk_out:
            rows.append({**row, "filled": False, "skip": f"{sk_in} at entry" if sk_in else f"{sk_out} at exit"})
            continue
        b_in, b_out = ("buy", "sell") if s.direction == 1 else ("sell", "buy")
        f_in = costs.fee(px_in, s.qty, b_in, venue, ts=t_in)
        f_out = costs.fee(px_out, s.qty, b_out, venue, ts=t_out)
        pnl = s.direction * (px_out - px_in) * s.qty - f_in - f_out
        cost_in = px_in if s.direction == 1 else 1 - px_in
        rows.append({**row, "filled": True, "skip": "", "entry_px": px_in, "exit_px": px_out,
                     "fee_entry": f_in, "fee_exit": f_out, "pnl_cents": round(pnl * 100, 6),
                     "edge_cents_per_contract": round(pnl * 100 / s.qty, 6),
                     "cap_contracts": sz_in, "cap_dollars": sz_in * cost_in})
    return pd.DataFrame(rows)


def evaluate_game(game_id: str, kickoff_utc, k_ticks: pd.DataFrame, o_ticks: pd.DataFrame, venue: str,
                  lo_ns: int, hi_ns: int, exclude=(), latencies=LATENCIES_S, holdout_run: bool = False,
                  setting: dict = SETTING, outages=(), condition: str | None = None,
                  delays: dict | None = None) -> pd.DataFrame:
    """All latencies for one game on one follower venue. One row per (latency, signal).
    exclude: grid-second intervals (inclusive); outages: ns intervals [a, b) of either venue (GAPS rows).
    condition / delays: polymarket.com condition id and load_seconds_delay() (missing -> 3 s, counted)."""
    if venue not in VENUE_DELAY_S:
        raise ValueError(f"no follower venue {venue!r}")
    k = pd.Timestamp(kickoff_utc)
    k = k.tz_localize("UTC") if k.tzinfo is None else k.tz_convert("UTC")
    if k >= SEAL and not holdout_run:
        raise ValueError(f"{game_id}: kickoff {k} is a holdout game; needs holdout_run=True (run once)")
    delay, source = venue_delay(venue, condition, delays)
    sig = signals(k_ticks, o_ticks, venue, lo_ns, hi_ns, exclude, setting, outages)
    q = book(o_ticks, venue)
    breaks_ns = [(a * NS, (b + 1) * NS) for a, b in _breaks_g(exclude, outages)]
    out = [fill_trades(sig, q, venue, delay + L, breaks_ns, hi_ns).assign(added_latency_s=L) for L in latencies]
    out = [o for o in out if len(o)]
    if not out:
        return pd.DataFrame(columns=["game_id", "venue", "latency_s", "filled", "venue_delay_s", "delay_source"])
    return pd.concat(out, ignore_index=True).assign(game_id=game_id, venue=venue, venue_delay_s=delay,
                                                    delay_source=source)


def capacity(trades: pd.DataFrame) -> pd.DataFrame:
    """Per game and latency: median capacity per filled trade and the total, contracts and dollars.
    NaN where sizes are not recorded (Polymarket US)."""
    f = trades[trades["filled"].astype(bool)] if len(trades) else trades
    if not len(f):
        return pd.DataFrame(columns=["game_id", "venue", "latency_s", "n_trades", "cap_contracts_median",
                                     "cap_dollars_median", "cap_contracts_total", "cap_dollars_total"])
    return (f.groupby(["game_id", "venue", "latency_s"])
             .agg(n_trades=("cap_contracts", "size"), cap_contracts_median=("cap_contracts", "median"),
                  cap_dollars_median=("cap_dollars", "median"),
                  cap_contracts_total=("cap_contracts", lambda x: x.sum(min_count=1)),
                  cap_dollars_total=("cap_dollars", lambda x: x.sum(min_count=1)))
             .reset_index())


BOOT_N, BOOT_SEED = 2000, 20261003      # docs/stats_plan.md: block bootstrap by game, 2,000 draws, seed 20261003


def game_bootstrap_ci(per_game_sum: np.ndarray, per_game_n: np.ndarray) -> tuple[float, float]:
    """Block bootstrap by game (as run_strategy_b.boot_ci): resample whole games with replacement; each draw's
    statistic is total edge / total trades. NaN with fewer than 2 games or fewer than 2 trades."""
    p, n = np.asarray(per_game_sum, float), np.asarray(per_game_n, float)
    if len(p) < 2 or n.sum() < 2:
        return float("nan"), float("nan")
    idx = np.random.default_rng(BOOT_SEED).integers(0, len(p), size=(BOOT_N, len(p)))
    m = p[idx].sum(axis=1) / np.maximum(n[idx].sum(axis=1), 1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def latency_curve(trades: pd.DataFrame) -> pd.DataFrame:
    """out/latency_curve.csv contract: latency_s, n_trades, edge_cents_mean (net, per contract), edge_ci_low /
    edge_ci_high = 95% block bootstrap by game (docs/stats_plan.md, v2 Amendment 5 draft), pnl_total (dollars).
    Also n_games, the per-trade normal CI as extra columns labelled "per-trade normal (not the plan's CI)", and skip
    counts (no quote, break, after window end). Filled round trips only. Group by latency_s = total
    decision-to-fill time, so mix markets only when they share a delay."""
    rows = []
    for lat, d in trades.groupby("latency_s"):
        f = d[d["filled"].astype(bool)]
        e = f["edge_cents_per_contract"].to_numpy(float) if len(f) else np.array([])
        m = float(e.mean()) if len(e) else float("nan")
        se = float(e.std(ddof=1) / np.sqrt(len(e))) if len(e) > 1 else float("nan")
        if len(f) and "game_id" in f:
            pg = f.groupby("game_id")["edge_cents_per_contract"]
            lo, hi = game_bootstrap_ci(pg.sum().to_numpy(), pg.size().to_numpy())
            n_games = int(pg.ngroups)
        else:
            lo, hi, n_games = float("nan"), float("nan"), 0
        rows.append({"latency_s": lat, "n_trades": len(e), "n_games": n_games, "edge_cents_mean": m,
                     "edge_ci_low": lo, "edge_ci_high": hi, "ci_method": "block bootstrap by game, 2000, seed 20261003",
                     "pnl_total": float(f["pnl_cents"].sum()) / 100 if len(f) else 0.0,
                     "per_trade_normal_ci_low (not the plan's CI)": m - 1.96 * se,
                     "per_trade_normal_ci_high (not the plan's CI)": m + 1.96 * se,
                     "n_skipped_no_quote": int((d["skip"].astype(str).str.startswith("no quote")).sum()),
                     "n_skipped_break": int((d["skip"].astype(str).str.startswith("break")).sum()),
                     "n_skipped_after_end": int((d["skip"].astype(str).str.startswith("after window end")).sum())})
    return pd.DataFrame(rows)
