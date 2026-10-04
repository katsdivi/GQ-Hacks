"""Synthetic tests for the HYPOTHESIS_v4 Arm B parameter in scripts/posthoc_mm_v4.py (no real data)."""
import numpy as np

import posthoc_mm_v4 as M

NS = M.NS
LO, HI, KO = 0, 10_000 * NS, 5_000 * NS


def test_arm_a_default_matches_always_quote():
    b = M.Book([0], [0.49], [0.51], [100.0], [100.0])      # 2 c spread
    tts, tpx, tsz = np.array([10 * NS]), np.array([0.52]), np.array([5.0])
    assert len(M.simulate(b, tts, tpx, tsz, LO, HI, KO, None, None, "F1")) == 1
    assert len(M.simulate(b, tts, tpx, tsz, LO, HI, KO, None, None, "F1", min_spread=0.0)) == 1


def test_arm_b_does_not_quote_below_3c_spread():
    b = M.Book([0], [0.49], [0.51], [100.0], [100.0])      # 2 c spread < 3 c
    tts, tpx, tsz = np.array([10 * NS]), np.array([0.52]), np.array([5.0])
    assert M.simulate(b, tts, tpx, tsz, LO, HI, KO, None, None, "F1", min_spread=0.03) == []


def test_arm_b_quotes_at_3c_and_stops_when_spread_narrows():
    # 3 c spread from t=0, narrows to 1 c at t=20 s
    b = M.Book([0, 20 * NS], [0.48, 0.50], [0.51, 0.51], [100.0, 100.0], [100.0, 100.0])
    early = M.simulate(b, np.array([10 * NS]), np.array([0.52]), np.array([5.0]), LO, HI, KO, None, None, "F1",
                       min_spread=0.03)
    late = M.simulate(b, np.array([30 * NS]), np.array([0.52]), np.array([5.0]), LO, HI, KO, None, None, "F1",
                      min_spread=0.03)
    assert len(early) == 1 and early[0]["side"] == -1
    assert late == []
