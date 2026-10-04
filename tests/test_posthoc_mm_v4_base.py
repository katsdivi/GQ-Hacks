"""Synthetic tests for scripts/posthoc_mm_signal.py (no real data)."""
import numpy as np

import posthoc_mm_v4 as M

NS = M.NS
LO, HI, KO = 0, 10_000 * NS, 5_000 * NS        # kickoff cut [4880 s, 6200 s) is far from the test times


def flat_book():
    # constant book 0.49 / 0.51 with 100 displayed on each side from t = 0
    return M.Book([0], [0.49], [0.51], [100.0], [100.0])


def test_signal_after_fill_never_changes_that_fill():
    b = flat_book()
    tts, tpx, tsz = np.array([10 * NS]), np.array([0.52]), np.array([5.0])   # through our ask at 10 s
    n = M.simulate(b, tts, tpx, tsz, LO, HI, KO, None, None, "F1")
    s = M.simulate(b, tts, tpx, tsz, LO, HI, KO, [(20 * NS, 1)], 0.25, "F1")  # Kalshi up AFTER the fill
    assert n == s and len(n) == 1 and n[0]["side"] == -1


def test_pulled_quote_never_fills_after_cancel_time():
    b = flat_book()
    sig = [(100 * NS, 1)]                                   # Kalshi up: pull our ask at 100.25 s until 110 s
    before = M.simulate(b, np.array([100 * NS + int(0.1 * NS)]), np.array([0.52]), np.array([5.0]),
                        LO, HI, KO, sig, 0.25, "F1")
    after = M.simulate(b, np.array([100 * NS + int(0.5 * NS)]), np.array([0.52]), np.array([5.0]),
                       LO, HI, KO, sig, 0.25, "F1")
    assert len(before) == 1 and len(after) == 0
    back = M.simulate(b, np.array([111 * NS]), np.array([0.52]), np.array([5.0]), LO, HI, KO, sig, 0.25, "F1")
    assert len(back) == 1                                  # re-quoted 10 s after the signal


def test_queue_fill_never_before_queue_ahead_is_traded():
    b = flat_book()                                        # 100 ahead of us at 0.49
    t = np.array([10, 20, 30]) * NS
    small = M.simulate(b, t, np.array([0.49] * 3), np.array([30.0, 30.0, 30.0]), LO, HI, KO, None, None, "F2")
    assert not [f for f in small if f["side"] == 1]        # 90 traded < 100 queue
    more = M.simulate(b, t, np.array([0.49] * 3), np.array([30.0, 30.0, 45.0]), LO, HI, KO, None, None, "F2")
    bids = [f for f in more if f["side"] == 1]
    assert len(bids) == 1 and bids[0]["qty"] == 5 and bids[0]["t"] == 30 * NS
    # strict rule never fills on at-price prints
    assert not M.simulate(b, t, np.array([0.49] * 3), np.array([300.0] * 3), LO, HI, KO, None, None, "F1")


def test_taker_delay_rule_hit_only_if_live_at_tau():
    # polymarket.com taker trade at tau = 101 s (submitted at 100 s with 1 s delay); our ask pull effective at
    # 100.25 s (signal at 100 s, L = 0.25): not hit. With L = 1.0 the pull is effective at 101 s: trade at the same
    # venue time is processed first (order not yet pulled), so it is hit; at L > delay it is hit.
    b = flat_book()
    tau = np.array([101 * NS])
    hit025 = M.simulate(b, tau, np.array([0.52]), np.array([5.0]), LO, HI, KO, [(100 * NS, 1)], 0.25, "F1")
    hit15 = M.simulate(b, tau, np.array([0.52]), np.array([5.0]), LO, HI, KO, [(100 * NS, 1)], 1.5, "F1")
    assert len(hit025) == 0 and len(hit15) == 1


def test_inventory_limit_and_kickoff_cut():
    b = flat_book()
    t = np.arange(1, 11) * NS
    f = M.simulate(b, t, np.array([0.48] * 10), np.array([10.0] * 10), LO, HI, KO, None, None, "F1")
    assert sum(x["qty"] for x in f if x["side"] == 1) == 50      # stops at +50
    cut = M.simulate(b, np.array([KO + 60 * NS]), np.array([0.52]), np.array([5.0]), LO, HI, KO, None, None, "F1")
    assert not cut
