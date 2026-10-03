"""Fake game checks for align/leadlag/strategy/backtest (CLAUDE.md "Ground truth for testing")."""
import pandas as pd

import align
import backtest
import leadlag
import strategy
from make_sample import LAG_S, build

P = {**leadlag.PROVISIONAL, **strategy.PROVISIONAL}


def _grids(df, a, b):
    return align.common_grid(align.to_grid(align.trade_median_events(df, a, 3.0)),
                             align.to_grid(align.trade_median_events(df, b, 3.0)))


def _run(df, a, b, latency_s):
    pa, pb = _grids(df, a, b)
    resp, summ = leadlag.leadlag(pa, pb, P["jump_cents"], P["window_s"], P["cover"], P["max_wait_s"], P["max_lag_s"])
    sig = strategy.signals(pa, pb, resp, P["entry_gap_cents"], P["exit_gap_cents"], P["timeout_s"], P["qty"])
    q, _ = backtest.follower_quotes(df, b)
    return resp, summ, backtest.simulate(sig, q, q, b, latency_s)


def test_finds_planted_jumps_and_lag():
    df, truth = build(seed=42)
    resp, summ, _ = _run(df, "cme", "kalshi", 1.0)
    t0 = df["ts"].min() // 1_000_000_000
    found = set(resp["jump_g"] - t0)
    matched = sum(any(abs(t - f) <= 1 for f in found) for t in truth["t_s"])
    assert matched == len(truth) == 15
    assert summ["median_response_s"] == LAG_S
    assert summ["xcorr_lag_s"] == LAG_S


def test_placebo_kalshi_as_leader_has_no_edge():
    df, _ = build(seed=42)
    _, summ, trades = _run(df, "kalshi", "cme", 0.0)
    assert summ["xcorr_lag_s"] == -LAG_S          # correctly sees CME moving first
    assert len(trades) == 0 or trades["pnl_cents"].sum() <= 0


def test_edge_does_not_grow_with_latency():
    df, _ = build(seed=42)
    nets = [_run(df, "cme", "kalshi", lat)[2]["pnl_cents"].sum() for lat in (0.0, 1.0, 2.0)]
    assert nets[0] >= nets[1] >= nets[2]


def test_edge_exists_when_lag_exceeds_detection_delay(monkeypatch):
    # The 3 s median detects a jump 1 s late and decisions are stamped 1 s after their label,
    # so a 2 s lag is used up before any latency. With a 5 s lag the edge must be positive at 0 s.
    import make_sample
    monkeypatch.setattr(make_sample, "LAG_S", 5)
    df, _ = make_sample.build(seed=42)
    _, summ, trades = _run(df, "cme", "kalshi", 0.0)
    assert summ["median_response_s"] == 5
    assert trades["pnl_cents"].sum() > 0


def test_decisions_are_stamped_after_their_grid_label():
    df, _ = build(seed=42)
    pa, pb = _grids(df, "cme", "kalshi")
    resp, _ = leadlag.leadlag(pa, pb)
    sig = strategy.signals(pa, pb, resp)
    assert (sig["entry_decision_ns"] == (sig["entry_g"] + 1) * 1_000_000_000).all()
    assert (sig["exit_g"] > sig["entry_g"]).all()


def test_shift_only_moves_earlier():
    df, _ = build(seed=42)
    base = align.venue_events(df, "kalshi")
    shifted = align.venue_events(df, "kalshi", shift_s=2.9)
    assert ((base["ts"] - shifted["ts"]) == 2_900_000_000).all()


def test_test_games_refused():
    import pytest
    with pytest.raises(SystemExit):
        backtest.check_allowed("nfl_x", "2026-08-02T00:00:00Z")
    backtest.check_allowed("nfl_x", "2026-07-31T00:00:00Z")


def test_trailing_median_uses_only_past_trades():
    df, _ = build(seed=42)
    ev = align.trade_median_events(df, "cme", 3.0)
    tr = df[(df["venue"] == "cme") & (df["kind"] == "trade")].sort_values("ts")
    # Trades are 1 s apart: the value at trade i is the median of trades i-2, i-1, i only.
    i = 500
    want = tr["price"].iloc[i - 2: i + 1].median()
    assert ev["price"].iloc[i] == want


def test_no_jumps_gives_empty_table_not_crash():
    import numpy as np
    flat = pd.Series(np.full(600, 0.5), index=np.arange(600, dtype="int64"))
    resp, summ = leadlag.leadlag(flat, flat)
    assert len(resp) == 0 and {"response_s", "covered"} <= set(resp.columns)
    assert summ["n_jumps"] == 0 and summ["n_covered"] == 0
