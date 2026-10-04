"""Synthetic tests for Post-hoc Idea 11 (no real data)."""
import numpy as np
import pandas as pd

import posthoc_idea11 as I

NS = I.NS
KO = 10_000 * NS           # kickoff far from the test windows below
LO, HI = 0, 3_000 * NS     # window [0, 3000 s), kickoff cut [KO - 120 s, KO + 1200 s] is outside it


def rows(recv, kind_px_sz, src_off=-40_000_000):
    """recv: ns; kind_px_sz: list of (kind, price, size)."""
    return [{"ts": recv, "kind": k, "price": p, "size": s, "recv_ns": recv, "src_ts_ns": recv + src_off}
            for k, p, s in kind_px_sz]


def snap(recs):
    return I.snapshots(pd.DataFrame(recs))[0]


def test_residue_removed_and_side_empty():
    df = pd.DataFrame(rows(1 * NS, [("bid", 0.50, 0.004), ("ask", 0.52, 100)]) +
                      rows(2 * NS, [("bid", 0.50, 5.0), ("ask", 0.52, 0.009)]) +
                      rows(3 * NS, [("bid", 0.50, 0.01), ("ask", 0.52, 3.0)]))
    s, n = I.snapshots(df)
    assert n == 2
    assert len(s) == 3                                  # snapshots kept even when a side is residue
    assert np.isnan(s.loc[0, "bid"]) and s.loc[0, "ask"] == 0.52
    assert np.isnan(s.loc[1, "ask"])
    assert s.loc[2, "bid_size"] == 0.01                 # exactly 0.01 is not residue
    m = I.mid_of(s)
    assert np.isnan(m[0]) and np.isnan(m[1]) and abs(m[2] - 0.51) < 1e-12


def base_snaps():
    """Kalshi home ask 0.40, Kalshi away market P(home) bid 0.30 (away YES ask 0.70), polymarket.com home token
    bid 0.60 (away token ask 0.40) / ask 0.62. X = home: 0.40 + 0.40 + fees < 1 -> opportunity."""
    kh = snap(rows(10 * NS, [("bid", 0.39, 50), ("ask", 0.40, 50)]) + rows(20 * NS, [("bid", 0.59, 50), ("ask", 0.60, 50)]))
    ka = snap(rows(10 * NS, [("bid", 0.30, 50), ("ask", 0.31, 50)]))
    pm = snap(rows(10 * NS, [("bid", 0.60, 7), ("ask", 0.62, 9)]) + rows(30 * NS, [("bid", 0.60, 7), ("ask", 0.62, 9)]))
    return {"k_home": kh, "k_away": ka, "pm": pm}


def test_no_book_after_t_used_for_signal():
    s = base_snaps()
    ops = I.opportunities(s, LO, HI, KO)
    o = ops[ops.team == "home"].iloc[0]
    assert o["t"] == 10 * NS and o["k_px"] == 0.40
    # changing a book received AFTER t must not change the signal at t
    s2 = base_snaps()
    s2["k_home"].loc[1, "ask"] = 0.99
    o2 = I.opportunities(s2, LO, HI, KO)
    o2 = o2[o2.team == "home"].iloc[0]
    assert o2["t"] == o["t"] and o2["k_px"] == o["k_px"] and o2["pm_px"] == o["pm_px"]
    # the opportunity ends at the first event where it no longer clears (Kalshi ask 0.60 at 20 s)
    assert abs(o["duration_s"] - 10.0) < 1e-9


def test_pm_leg_never_before_t_plus_L_plus_delay_and_same_size():
    s = base_snaps()
    # extra polymarket.com snapshot at t + L + delay - 1 ns must be skipped
    o = {"team": "home", "t": 10 * NS}
    L, d = 0.5, 1.0
    early = rows(10 * NS + int((L + d) * NS) - 1, [("bid", 0.90, 1), ("ask", 0.91, 1)])
    s["pm"] = snap(rows(10 * NS, [("bid", 0.60, 7), ("ask", 0.62, 9)]) + early +
                   rows(12 * NS, [("bid", 0.60, 7), ("ask", 0.62, 9)]))
    s["k_home"] = snap(rows(10 * NS, [("bid", 0.39, 50), ("ask", 0.40, 50)]) +
                       rows(10 * NS + int(L * NS) - 1, [("bid", 0.10, 1), ("ask", 0.11, 1)]) +
                       rows(11 * NS, [("bid", 0.39, 50), ("ask", 0.40, 50)]))
    e = I.execute(o, s, L, d)
    assert e["pm_fill_recv"] >= o["t"] + int((L + d) * NS)
    assert e["k_fill_recv"] >= o["t"] + int(L * NS)
    assert e["pm_px"] == 0.40 and e["k_px"] == 0.40
    assert e["q"] == 7.0                                 # min(10, 50, 7), same q on both legs
    assert e["executed"]
    pnl = I.settle_pnl(e, "home", {"home": 1.0, "away": 0.0}, {"home": 1.0, "away": 0.0})
    assert abs(pnl["pnl"] - (7 * 1.0 - 7 * 0.80 - e["fee_k"] - e["fee_pm"])) < 1e-9


def test_disagreeing_settlement_flagged():
    assert I.settlement_agrees({"home": 1.0, "away": 0.0}, {"home": 1.0, "away": 0.0})
    assert not I.settlement_agrees({"home": 1.0, "away": 0.0}, {"home": 0.0, "away": 1.0})
    assert not I.settlement_agrees({"home": 0.5, "away": 0.5}, {"home": 1.0, "away": 0.0})


def test_fees():
    assert I.fee_k(0.40, 10) == 0.17                   # 0.07*10*0.24 = 0.168 -> 0.17
    assert I.fee_k(0.40, 7) == 0.12                    # 0.1176 -> 0.12
    assert abs(I.fee_k_pc10(0.40) - 0.017) < 1e-12
    assert abs(I.fee_pm(0.40, 7) - 0.05 * 7 * 0.24) < 1e-12


def test_lag_sign_and_10ms():
    rng = np.random.default_rng(1)
    n = 5000
    x = np.where(rng.random(n) < 0.05, rng.normal(size=n), 0.0)
    y = np.roll(x, 3)                                   # y moves 3 bins (30 ms) after x
    assert abs(I.xcorr_lag(x, y) - 0.03) < 1e-12        # + = x (Kalshi) first
    assert abs(I.xcorr_lag(y, x) + 0.03) < 1e-12
