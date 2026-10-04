"""Synthetic-book tests for scripts/posthoc_idea2.py (IDEA 2, POST-HOC, EXPLORATORY)."""
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import posthoc_idea2 as P  # noqa: E402

NS = P.NS
T0 = 1_791_000_000 * NS
KO = T0 + 10_000 * NS          # kickoff far away so the cut does not interfere


def snap(rows):
    """rows: (recv_s, src_s, bid, ask, bid_size, ask_size) -> snapshot frame sorted by recv."""
    d = pd.DataFrame(rows, columns=["recv", "src", "bid", "ask", "bid_size", "ask_size"])
    d["recv"] = (T0 + d["recv"] * NS).round().astype("int64")
    d["src"] = (T0 + d["src"] * NS).round().astype("int64")
    return d.sort_values(["recv", "src"]).reset_index(drop=True)


def raw(rows):
    """Long-format book rows like the recordings: (recv_s, src_s or None, kind, price, size)."""
    out = []
    for r, s, k, p, z in rows:
        t = int(T0 + r * NS)
        out.append({"ts": t, "recv_ns": t, "src_ts_ns": (int(T0 + s * NS) if s is not None else None),
                    "kind": k, "price": p, "size": z})
    d = pd.DataFrame(out)
    d["src_ts_ns"] = d["src_ts_ns"].astype("Int64")
    return d


def test_grid_mid_undefined_when_one_side_missing():
    s, _ = P.snapshots(raw([(0.0, 0.0, "bid", 0.50, 5), (0.0, 0.0, "ask", 0.52, 5),
                            (0.35, 0.35, "bid", 0.50, 5),               # ask missing -> undefined
                            (0.75, 0.75, "bid", 0.50, 5), (0.75, 0.75, "ask", 0.54, 5)]))
    g = P.grid100(s)
    b0 = (T0) // P.BIN
    assert g.loc[b0] == pytest.approx(0.51)
    assert math.isnan(g.loc[b0 + 3]) and math.isnan(g.loc[b0 + 5])    # carried one-sided state stays undefined
    assert g.loc[b0 + 7] == pytest.approx(0.52)


def test_null_src_rows_dropped():
    s, nn = P.snapshots(raw([(0.0, None, "bid", 0.5, 1), (0.0, None, "ask", 0.6, 1),
                             (1.0, 1.0, "bid", 0.5, 1), (1.0, 1.0, "ask", 0.52, 1)]))
    assert nn == 2 and len(s) == 1


def test_signal_ignores_future_venue_time_and_later_receipt():
    k = snap([(0.0, 0.0, 0.49, 0.51, 10, 10)])
    # polymarket jumps 4c at venue time 1.2 (received 1.25). A later-venue-time snapshot (src 5.0) arriving
    # EARLIER than another must not feed the earlier decision.
    p = snap([(0.0, 0.0, 0.49, 0.51, 10, 10),
              (1.25, 1.2, 0.53, 0.55, 10, 10),
              (1.30, 5.0, 0.30, 0.32, 10, 10)])     # future venue time; must not change dP at s = 1.2
    sig = P.signals(p, k, T0 - NS, T0 + 100 * NS, KO)
    first = sig[sig.trig_src == T0 + int(1.2 * NS)]
    assert len(first) == 1 and first.iloc[0].dP == pytest.approx(0.04) and first.iloc[0].direction == 1


def test_signal_kalshi_received_later_not_used():
    # Kalshi moves up 2c at venue time 1.1 but is received at 3.0, after the polymarket trigger at 1.25.
    k = snap([(0.0, 0.0, 0.49, 0.51, 10, 10), (3.0, 1.1, 0.51, 0.53, 10, 10)])
    p = snap([(0.0, 0.0, 0.49, 0.51, 10, 10), (1.25, 1.2, 0.53, 0.55, 10, 10)])
    sig = P.signals(p, k, T0 - NS, T0 + 100 * NS, KO)
    assert len(sig) == 1 and sig.iloc[0].dK == pytest.approx(0.0)   # the late Kalshi move is invisible


def test_signal_blocked_when_kalshi_already_moved():
    k = snap([(0.0, 0.0, 0.49, 0.51, 10, 10), (1.0, 0.9, 0.51, 0.53, 10, 10)])
    p = snap([(0.0, 0.0, 0.49, 0.51, 10, 10), (1.25, 1.2, 0.53, 0.55, 10, 10)])
    assert len(P.signals(p, k, T0 - NS, T0 + 100 * NS, KO)) == 0


def test_lag_uses_no_future_beyond_window():
    # lag test reads only snapshots with venue time inside [lo, hi)
    rng = np.random.default_rng(0)
    steps = np.cumsum(rng.choice([-0.01, 0, 0.01], size=600))
    k = snap([(i * 0.1 + 0.01, i * 0.1, 0.5 + x, 0.52 + x, 1, 1) for i, x in enumerate(steps)])
    p = snap([(i * 0.1 + 0.01, i * 0.1 + 0.5, 0.5 + x, 0.52 + x, 1, 1) for i, x in enumerate(steps)])  # p 0.5 s later
    lag = P.lag_100ms(k, p, T0, T0 + 60 * NS, KO)
    assert lag == pytest.approx(0.5)
    # garbage after hi does not change it
    p2 = pd.concat([p, snap([(70 + i, 70 + i, 0.1 * (i % 5), 0.1 * (i % 5) + 0.02, 1, 1) for i in range(20)])])
    assert P.lag_100ms(k, p2.sort_values("recv").reset_index(drop=True), T0, T0 + 60 * NS, KO) == lag


def _book_for_fill():
    return snap([(0.0, 0.0, 0.49, 0.51, 50, 50),
                 (1.40, 1.40, 0.40, 0.45, 50, 50),     # received BEFORE order time 1.25 + 0.25 = 1.50
                 (1.60, 1.60, 0.50, 0.52, 50, 4),      # first at or after order time
                 (31.0, 31.0, 0.60, 0.62, 50, 50),     # before fill + 30 s
                 (31.7, 31.7, 0.58, 0.61, 50, 50)])    # first at or after 1.60 + 30 = 31.60


def test_no_quote_before_order_time_used_and_size_cap():
    sig = pd.DataFrame([{"trig_recv": T0 + int(1.25 * NS), "trig_src": T0 + int(1.2 * NS), "dP": 0.04,
                         "dK": 0.0, "direction": 1}])
    tr, sk = P.simulate(sig, _book_for_fill(), 0.25, KO, T0 + 1000 * NS)
    assert len(tr) == 1
    t = tr[0]
    assert t["fill_recv"] == T0 + int(1.60 * NS) and t["entry_px"] == 0.52 and t["qty"] == 4


def test_exit_crosses_spread_after_30s():
    sig = pd.DataFrame([{"trig_recv": T0 + int(1.25 * NS), "trig_src": T0 + int(1.2 * NS), "dP": 0.04,
                         "dK": 0.0, "direction": 1}])
    t = P.simulate(sig, _book_for_fill(), 0.25, KO, T0 + 1000 * NS)[0][0]
    assert t["exit_recv"] == T0 + int(31.7 * NS) and t["exit_px"] == 0.58      # long sells at the bid
    assert t["gross_c"] == pytest.approx(6.0)
    sig.loc[0, "direction"] = -1
    t = P.simulate(sig, _book_for_fill(), 0.25, KO, T0 + 1000 * NS)[0][0]
    assert t["entry_px"] == 0.50 and t["exit_px"] == 0.61 and t["gross_c"] == pytest.approx(-11.0)


def test_fees():
    sig = pd.DataFrame([{"trig_recv": T0 + int(1.25 * NS), "trig_src": T0 + int(1.2 * NS), "dP": 0.04,
                         "dK": 0.0, "direction": 1}])
    t = P.simulate(sig, _book_for_fill(), 0.25, KO, T0 + 1000 * NS)[0][0]
    # qty 4: entry 0.07*4*0.52*0.48 = 0.069888 -> $0.07; exit 0.07*4*0.58*0.42 = 0.068208 -> $0.07
    assert t["net_direct_c"] == pytest.approx(6.0 - (7 + 7) / 4)
    assert t["net_webull_c"] == pytest.approx(6.0 - 4.0)
    # 10 contracts at 0.50: 0.07*10*0.25 = 0.175 -> 0.18 dollars
    assert P.leg_fee_cents(0.50, 10, "direct") == pytest.approx(1.8)


def test_one_position_at_a_time():
    s1 = {"trig_recv": T0 + int(1.25 * NS), "trig_src": T0 + int(1.2 * NS), "dP": 0.04, "dK": 0.0, "direction": 1}
    s2 = {**s1, "trig_recv": T0 + int(5 * NS), "trig_src": T0 + int(5 * NS)}
    tr, sk = P.simulate(pd.DataFrame([s1, s2]), _book_for_fill(), 0.25, KO, T0 + 1000 * NS)
    assert len(tr) == 1 and sk["held"] == 1
