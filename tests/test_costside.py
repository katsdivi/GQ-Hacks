"""Synthetic tests for the post-hoc cost-side search (post-hoc, exploratory)."""
import numpy as np
import pandas as pd

import costside_common as C
import costside_round1 as R

NS = C.NS


def test_maker_fill_needs_strict_trade_through_after_post():
    ts = np.array([0, 2, 3, 4], dtype=np.int64) * NS
    px = np.array([0.50, 0.50, 0.49, 0.48])
    assert C.maker_entry(ts, px, 0, 0.50, 60) == (3 * NS, 0.50)       # 0.49 <= 0.50 - 0.01
    assert C.maker_entry(ts, px, 0, 0.49, 60) == (4 * NS, 0.49)       # print AT 0.49 does not count
    assert C.maker_entry(ts, px, 0, 0.47, 60) is None


def test_no_maker_fill_at_or_before_post_plus_latency():
    ts = np.array([0, 1, 5], dtype=np.int64) * NS
    px = np.array([0.40, 0.40, 0.60])
    assert C.maker_entry(ts, px, 0, 0.45, 60) is None                  # trade-through at t and t+1 s ignored


def test_leader_signal_uses_only_data_at_or_before_t():
    g = {"kickoff_ns": 0, "pm": (np.array([1300, 1330, 1400]) * NS, np.array([0.50, 0.50, 0.56])),
         "kph": (np.array([1000, 1395]) * NS, np.array([0.50, 0.50]))}
    s1 = R.c1_signals(g, 0.05, 5)
    g2 = {**g, "kph": (np.array([1000, 1395, 1401]) * NS, np.array([0.50, 0.50, 0.90]))}   # future Kalshi trade
    g3 = {**g, "pm": (np.array([1300, 1330, 1400, 1450]) * NS, np.array([0.50, 0.50, 0.56, 0.10]))}
    assert s1 == R.c1_signals(g2, 0.05, 5)
    assert s1 == R.c1_signals(g3, 0.05, 5)[:len(s1)]
    assert s1 == [(1400 * NS, 1)]


def test_exit_never_before_fill_plus_h():
    ts = np.array([0, 10, 59, 60, 70], dtype=np.int64) * NS
    px = np.array([0.5, 0.6, 0.7, 0.8, 0.9])
    assert C.exit_at(ts, px, 0, 60) == (60 * NS, 0.79)
    assert C.exit_at(np.array([0, 300], dtype=np.int64) * NS, np.array([0.5, 0.5]), 0, 60) is None


def test_fee_lines():
    assert C.fee_taker(0.5) == 0.18          # 0.07*10*0.25 = 0.175 -> 0.18
    assert C.fee_maker175(0.5) == 0.05       # 0.04375 -> 0.05
    assert C.fee_maker0(0.5) == 0.0
    assert C.fee_taker(0.95) == 0.04         # 0.03325 -> 0.04


def test_reality_check_noise_vs_planted_edge():
    rng = np.random.default_rng(1)
    days = [f"d{i:03d}" for i in range(150)]
    noise = {f"n{k}": pd.Series(rng.normal(0, 1, 150), index=days) for k in range(20)}
    r0 = C.multiple_testing(noise, nboot=300)
    assert r0["rc_p"] > 0.05
    planted = {**noise, "edge": pd.Series(rng.normal(0.8, 1, 150), index=days)}
    r1 = C.multiple_testing(planted, nboot=300)
    assert r1["best_by_t"] == "edge" and r1["rc_p"] < 0.05
