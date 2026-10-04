"""Synthetic tests for the Idea 11 post-run execution correction (scripts/posthoc_idea11_corrected.py).
No real data. Books are stored as P(home); team 'home' means: Kalshi YES home (k_flip False) and the polymarket.com
away token (p_flip True)."""
import numpy as np
import pandas as pd
import pytest

import posthoc_idea11_corrected as C

NS = C.NS
T0 = 1_000 * NS


def book(rows):
    """rows: (recv_s, src_s, bid, ask, bid_size, ask_size) -> venue-time-sorted snapshots."""
    d = pd.DataFrame(rows, columns=["recv", "src", "bid", "ask", "bid_size", "ask_size"])
    d["recv"] = (T0 + d["recv"] * NS).astype("int64")
    d["src"] = (T0 + d["src"] * NS).astype("float64")
    return C.by_venue_time(d)


OP = {"team": "home", "t": T0, "k_px": 0.40, "pm_px": 0.55}
# polymarket.com leg (away token) ask = 1 - stored home bid; good PM book: home bid 0.46 -> away ask 0.54
PM_GOOD = [(0.0, 0.0, 0.46, 0.48, 20.0, 20.0)]
K_GOOD = [(0.0, 0.0, 0.38, 0.40, 50.0, 50.0)]


def test_one_leg_fill_counted_naked():
    k = book(K_GOOD)
    pm = book([(0.0, 0.0, 0.40, 0.42, 20.0, 20.0)])      # away ask 0.60 > a_P 0.55: no fill
    r = C.reprice(OP, k, pm, 0.25, 1.0, 1.0, 0.0)
    assert r["status"] == "kalshi_only"
    assert r["q_hedged"] == 0 and r["q_naked"] == 10 and r["naked_venue"] == "kalshi"
    assert r["pnl_hedged"] == 0
    assert r["pnl_naked_hold"] == pytest.approx(10 * (1.0 - 0.40) - C.fee_k(0.40, 10))


def test_no_book_with_venue_time_after_fill_time():
    # snapshot RECEIVED before the fill time but with venue time AFTER it must not be used
    k = book([(0.0, 0.0, 0.50, 0.52, 50.0, 50.0),             # ask 0.52 > a_K: no fill
              (0.20, 0.30, 0.38, 0.40, 50.0, 50.0)])          # src t + 0.30 > fill time t + 0.25
    r = C.reprice(OP, k, book(PM_GOOD), 0.25, 1.0, 1.0, 0.0)
    assert r["q_k"] == 0 and r["k_state_src"] == T0
    s = C.state_at(k, T0 + int(0.25 * NS))
    assert s["src"] <= T0 + int(0.25 * NS)


def test_size_mismatch_creates_naked_excess():
    k = book(K_GOOD)                                          # Kalshi fills 10
    pm = book([(0.0, 0.0, 0.46, 0.48, 4.0, 20.0)])            # away ask size = home bid size = 4
    r = C.reprice(OP, k, pm, 0.25, 1.0, 1.0, 0.0)
    assert r["status"] == "both"
    assert r["q_k"] == 10 and r["q_pm"] == 4
    assert r["q_hedged"] == 4 and r["q_naked"] == 6 and r["naked_venue"] == "kalshi"


def test_fee_at_executed_size():
    k = book([(0.0, 0.0, 0.38, 0.40, 3.0, 3.0)])
    pm = book([(0.0, 0.0, 0.46, 0.48, 3.0, 3.0)])
    r = C.reprice(OP, k, pm, 0.25, 1.0, 1.0, 0.0)
    assert r["q_k"] == 3 and r["q_pm"] == 3
    assert r["fee_k"] == pytest.approx(0.06)                  # 0.07 x 3 x 0.4 x 0.6 = 0.0504 -> 0.06
    assert r["fee_pm"] == pytest.approx(0.03726)              # 0.05 x 3 x 0.54 x 0.46 = 0.03726
    assert C.fee_k(0.40, 10) == pytest.approx(0.17)           # 0.168 -> 0.17
    assert C.fee_pm(0.5, 1.0) == pytest.approx(0.0125)


def test_unwind_at_best_bid_failure_plus_1s_with_fee():
    # Kalshi-only fill at t + 0.25; at t + 1.25 (venue time) the YES home best bid is 0.35 (later 0.10 ignored)
    k = book([(0.0, 0.0, 0.38, 0.40, 50.0, 50.0),
              (1.10, 1.10, 0.35, 0.37, 50.0, 50.0),
              (1.40, 1.40, 0.10, 0.12, 50.0, 50.0)])
    pm = book([(0.0, 0.0, 0.40, 0.42, 20.0, 20.0)])           # no PM fill
    r = C.reprice(OP, k, pm, 0.25, 1.0, 0.0, 1.0)
    assert r["status"] == "kalshi_only"
    assert r["unwind_px"] == pytest.approx(0.35)
    uf = C.fee_k(0.35, 10)
    assert r["unwind_fee"] == pytest.approx(uf)
    assert r["pnl_naked_unwind"] == pytest.approx(10 * (0.35 - 0.40) - C.fee_k(0.40, 10) - uf)
    assert r["pnl_naked_hold"] == pytest.approx(10 * (0.0 - 0.40) - C.fee_k(0.40, 10))


def test_pm_leg_never_fills_before_t_plus_L_plus_delay():
    # PM book good at t + 0.5 (between t + L and t + L + delay), bad from t + 1.0: no fill at t + 1.25
    pm = book([(0.0, 0.0, 0.40, 0.42, 20.0, 20.0),
               (0.5, 0.5, 0.46, 0.48, 20.0, 20.0),
               (1.0, 1.0, 0.40, 0.42, 20.0, 20.0)])
    r = C.reprice(OP, book(K_GOOD), pm, 0.25, 1.0, 1.0, 0.0)
    assert r["pm_fill_time"] == T0 + int(1.25 * NS)
    assert r["q_pm"] == 0 and r["status"] == "kalshi_only"
    # and a good book appearing only after the fill time is not used either
    pm2 = book([(0.0, 0.0, 0.40, 0.42, 20.0, 20.0), (1.3, 1.3, 0.46, 0.48, 20.0, 20.0)])
    assert C.reprice(OP, book(K_GOOD), pm2, 0.25, 1.0, 1.0, 0.0)["q_pm"] == 0
