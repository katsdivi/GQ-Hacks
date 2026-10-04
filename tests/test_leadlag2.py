"""Synthetic tests for post-hoc leadlag2 (no real data)."""
import numpy as np

import leadlag2_common as C
import leadlag2_r1 as R

NS = C.NS


def _walk(n, seed=1):
    rng = np.random.default_rng(seed)
    return np.clip(0.5 + np.cumsum(rng.choice([-0.01, 0, 0.01], size=n, p=[0.2, 0.6, 0.2])), 0.02, 0.98)


def test_vecm_planted_leader():
    pm = _walk(3000)
    k = np.concatenate([[pm[0]] * 2, pm[:-2]])          # Kalshi = polymarket.com two steps earlier
    s = R.vecm_shares(pm, k)
    assert s["is_pm"] > 0.8 and s["gg_pm"] > 0.8
    s2 = R.vecm_shares(k, pm)                            # roles swapped: polymarket.com follows
    assert s2["is_pm"] < 0.2


def test_xcorr_sign():
    a = np.diff(_walk(2000, 2))
    b = np.concatenate([[0, 0], a[:-2]])
    lag, _ = R.xcorr_lag(a, b)
    assert lag == 2


def _game(pm_ts, pm_px, k_ts, k_px):
    return {"game_id": "x", "home": "H", "away": "A", "kickoff_ns": 0, "pay": {"H": 1.0, "A": 0.0},
            "kph": (np.array(k_ts, np.int64), np.array(k_px)), "pm": (np.array(pm_ts, np.int64), np.array(pm_px)),
            "own": {"H": (np.array(k_ts, np.int64), np.array(k_px)),
                    "A": (np.array(k_ts, np.int64), 1 - np.array(k_px))}}


def test_gap_signal_ignores_future():
    g = _game([0, 100 * NS], [0.50, 0.60], [0, 10 * NS], [0.50, 0.50])
    s1 = R.gap_signals(g, 0, 60 * NS, 0.02)
    g2 = _game([0, 100 * NS, 61 * NS], [0.50, 0.60, 0.90], [0, 10 * NS], [0.50, 0.50])
    order = np.argsort(g2["pm"][0])
    g2["pm"] = (g2["pm"][0][order], g2["pm"][1][order])
    s2 = R.gap_signals(g2, 0, 60 * NS, 0.02)
    assert s1 == s2 == []                                # no gap at or before 60 s; the 61 s print is unused


def test_gap_signal_staleness():
    g = _game([0, 50 * NS], [0.50, 0.60], [0], [0.50])   # Kalshi last trade 50+ s old at t >= 50
    assert R.gap_signals(g, 50 * NS, 60 * NS, 0.02) == []


def test_fill_strictly_after_t():
    ts = np.array([0, NS // 2, NS, 2 * NS], np.int64)
    px = np.array([0.4, 0.41, 0.42, 0.43])
    f = C.taker_entry(ts, px, 0, 60)
    assert f[0] >= NS and abs(f[1] - 0.43) < 1e-9


def test_flow_bins_past_only():
    ts = np.array([1 * NS, 6 * NS, 11 * NS], np.int64)
    fl = np.array([5.0, -2.0, 7.0])
    grid = np.array([0, 5 * NS, 10 * NS], np.int64)
    assert list(R.flow_bins(ts, fl, grid)) == [0.0, 5.0, -2.0]   # the 11 s trade never enters
