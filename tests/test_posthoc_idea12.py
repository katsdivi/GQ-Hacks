"""Synthetic tests for scripts/posthoc_idea12.py (post-hoc Idea 12). No real data."""
import numpy as np
import pandas as pd
import pytest

import posthoc_idea12 as I

NS = I.NS
KO = pd.Timestamp("2025-10-04 20:00", tz="UTC")
KO_NS = KO.value
H, AW = "EV-HOM", "EV-AWY"


def kal(rows):   # rows: (sec after ko, market, own YES price); stored as P(home)
    out = []
    for s, m, p in rows:
        out.append({"ts": KO_NS + int(s * NS), "venue": "kalshi", "market_id": m, "kind": "trade",
                    "price": p if m == H else 1 - p, "size": 10.0, "side": "buy"})
    return pd.DataFrame(out)


def pm(rows):    # (sec after ko, P(home))
    return pd.DataFrame([{"ts": KO_NS + int(s * NS), "venue": "polymarket", "market_id": "0xabc", "kind": "trade",
                          "price": p, "size": 5.0, "side": "buy"} for s, p in rows])


T0 = 30 * 60   # inside the window (ko + 20 min .. + 4 h)


def base_game(gap=0.06):
    """Home Kalshi 0.50, polymarket.com P(home) 0.50 + gap, trades every 5 s from T0 for 60 s."""
    k = kal([(T0 + i, H, 0.50) for i in range(0, 61, 5)] + [(T0 + i, AW, 0.50) for i in range(0, 61, 5)])
    p = pm([(T0 + i, 0.50 + gap) for i in range(0, 61, 5)])
    return k, p


def test_no_trade_after_t_changes_signal():
    k, p = base_game()
    d = I.decide(k, p, H, AW, KO_NS, 0.05, +1)
    t = d["t_ns"]
    k2 = pd.concat([k, kal([((t - KO_NS) / NS + 0.5, H, 0.90)])])        # later trades on both venues
    p2 = pd.concat([p, pm([((t - KO_NS) / NS + 0.2, 0.10)])])
    d2 = I.decide(k2[k2.ts <= t + NS], p2[p2.ts <= t + NS], H, AW, KO_NS, 0.05, +1)
    d3 = I.decide(k2, p2, H, AW, KO_NS, 0.05, +1)
    assert d == d2 == d3


def test_persistence_needs_10s_before_t():
    k, p = base_game()
    d = I.decide(k, p, H, AW, KO_NS, 0.05, +1)
    assert d["team"] == "home" and d["t_ns"] >= KO_NS + (T0 + 10) * NS
    # the gap starts at T0 (first time both venues have a trade), so the first qualifying t is T0 + 10 s
    assert d["t_ns"] == KO_NS + (T0 + 10) * NS
    # a single gap tick that breaks persistence 3 s before t delays the signal
    p2 = pd.concat([p, pm([(T0 + 7, 0.50)])]).sort_values("ts")
    d2 = I.decide(k, p2, H, AW, KO_NS, 0.05, +1)
    assert d2["t_ns"] >= KO_NS + (T0 + 7 + 10) * NS


def test_stale_price_no_signal():
    # home Kalshi last traded at T0; polymarket.com trades start 31 s later: K_home is stale, no home signal
    k = kal([(T0, H, 0.50), (T0, AW, 0.50)] + [(T0 + 31 + i, AW, 0.5) for i in range(0, 40, 5)])
    p = pm([(T0 + 31 + i, 0.60) for i in range(0, 40, 5)])
    assert I.decide(k, p, H, AW, KO_NS, 0.05, +1) is None


def test_fill_never_before_t_plus_1s():
    k, p = base_game()
    d = I.decide(k, p, H, AW, KO_NS, 0.05, +1)
    t = d["t_ns"]
    k2 = pd.concat([k, kal([((t - KO_NS) / NS + 0.5, H, 0.20)])])     # trade 0.5 s after t: not fillable
    r = I.leg(k2, H, True, t, 1.0)
    assert r["entered"] and r["fill_ts"] >= t + NS and r["trade_px"] == 0.50
    assert I.leg(kal([((t - KO_NS) / NS + 61.5, H, 0.5)]), H, True, t, 1.0)["skip"] == "no post-decision trade"


def test_orientation_swap_mirrors():
    k, p = base_game()
    d = I.decide(k, p, H, AW, KO_NS, 0.05, +1)
    # swap labels: away market becomes "home"; P(home) of the new orientation = 1 - old; same team bought
    ks = k.copy()
    ks["market_id"] = ks["market_id"].map({H: AW, AW: H})
    ks["price"] = 1 - ks["price"]
    ps = p.assign(price=1 - p["price"])
    d2 = I.decide(ks, ps, AW, H, KO_NS, 0.05, +1)
    assert d2["t_ns"] == d["t_ns"] and d2["team"] == "away" and abs(d2["g"] - d["g"]) < 1e-9


def test_placebo_sign():
    k, p = base_game(gap=-0.06)
    assert I.decide(k, p, H, AW, KO_NS, 0.05, +1)["team"] == "away"     # away Kalshi cheap vs PM
    assert I.decide(k, p, H, AW, KO_NS, 0.05, -1)["team"] == "home"     # home Kalshi rich vs PM


def test_payout_from_settlement_and_cap():
    k, p = base_game()
    d = I.decide(k, p, H, AW, KO_NS, 0.05, +1)
    assert I.leg(k, H, True, d["t_ns"], None)["skip"] == "void/unsettled"
    r = I.leg(k, H, True, d["t_ns"], 0.5)
    assert r["payout"] == 0.5
    k99 = kal([((d["t_ns"] - KO_NS) / NS + 2, H, 0.98)])
    assert I.leg(k99, H, True, d["t_ns"], 1.0)["skip"] == "fill at 0.99"


@pytest.mark.parametrize("p,exp", [(0.3, 0.15), (0.5, 0.18), (0.8, 0.12)])
def test_fee(p, exp):
    # 0.07 x 10 x P(1-P): 0.147 -> 0.15, 0.175 -> 0.18, 0.112 -> 0.12 (rounded up to the cent)
    assert float(I.fee_direct(I.D(p))) == exp
    assert float(I.fee_webull(I.D(p))) == 0.20


def test_holdout_refused():
    k, p = base_game()
    with pytest.raises(ValueError):
        I.evaluate_game("x", "2026-09-01 20:00+00:00", k, p, H, AW, {})
