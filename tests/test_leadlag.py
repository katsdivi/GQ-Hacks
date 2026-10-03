"""Fake game checks for align/leadlag/strategy/backtest (CLAUDE.md "Ground truth for testing")."""
import pandas as pd

import align
import backtest
import leadlag
import strategy
from make_sample import LAG_S, build

P = {**leadlag.PROVISIONAL, **strategy.PROVISIONAL}


def _grids(df, a, b):
    return align.common_grid(align.to_grid(align.venue_events(df, a)), align.to_grid(align.venue_events(df, b)))


def _run(df, a, b, latency_s):
    pa, pb = _grids(df, a, b)
    resp, summ = leadlag.leadlag(pa, pb, P["jump_cents"], P["window_s"], P["cover"], P["max_wait_s"], P["max_lag_s"])
    sig = strategy.signals(pa, pb, resp, P["entry_gap_cents"], P["exit_gap_cents"], P["timeout_s"], P["qty"])
    q, _ = backtest.follower_quotes(df, b)
    return resp, summ, backtest.simulate(sig, q, b, latency_s)


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


def test_edge_shrinks_with_latency():
    df, _ = build(seed=42)
    nets = [_run(df, "cme", "kalshi", lat)[2]["pnl_cents"].sum() for lat in (0.0, 1.0, 2.0)]
    assert nets[0] > nets[1] >= nets[2]


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
