import numpy as np
import pytest

import posthoc_costside_patterns as P
import strategy_a as sa

NS = 1_000_000_000


def tr(pairs):
    return (np.array([p[0] for p in pairs], dtype="int64"), np.array([p[1] for p in pairs], dtype=float))


def test_no_data_after_t():
    a = tr([(10 * NS, 0.50), (20 * NS, 0.60)])
    b = tr([(10 * NS, 0.50), (20 * NS, 0.60), (21 * NS, 0.99), (500 * NS, 0.01)])
    t = 20 * NS
    assert P.price_asof(a, t, 100 * NS) == P.price_asof(b, t, 100 * NS) == 0.60
    # a trade at t + 1 ns is invisible
    c = tr([(10 * NS, 0.50), (20 * NS + 1, 0.99)])
    assert P.price_asof(c, 20 * NS, 100 * NS) == 0.50
    # stale beyond max age -> nan
    assert np.isnan(P.price_asof(a, 200 * NS, 10 * NS))
    # P1 pick unchanged by appended future rows
    ref = {"H": 0.40, "A": 0.60}
    now_a = {"H": P.price_asof(a, t, 100 * NS), "A": 0.40}
    now_b = {"H": P.price_asof(b, t, 100 * NS), "A": 0.40}
    assert P.p1_pick(ref, now_a, 3, "mom") == P.p1_pick(ref, now_b, 3, "mom") == "H"


def test_fill_at_or_after_one_second():
    t = 100 * NS
    x = tr([(t, 0.50), (t + NS - 1, 0.55), (t + NS, 0.60), (t + 2 * NS, 0.70)])
    assert P.fill_price(x, t) == pytest.approx(0.61)           # the trade at t+1.0 s exactly, +1 cent
    y = tr([(t + NS - 1, 0.55)])
    assert P.fill_price(y, t) is None
    z = tr([(t + 301 * NS, 0.55)])                             # beyond 5 min
    assert P.fill_price(z, t) is None
    w = tr([(t + 2 * NS, 0.985)])
    assert P.fill_price(w, t) == 0.99                          # cap


def test_p4_uses_only_known_settlements():
    t = 10 * 3600 * NS
    mk = lambda ko_h, pay: dict(ko_ns=int(ko_h * 3600 * NS), fav_px=0.8, fav_payout=pay)
    games = [mk(1, 0.0),      # kickoff + 5h = 6h <= t: known upset
             mk(5.01, 0.0),   # settles at 10.01h > t: unknown
             mk(5, 0.0),      # exactly t: known
             mk(0, 1.0),      # known, not an upset
             dict(ko_ns=0, fav_px=0.6, fav_payout=0.0)]  # fav below 0.70: not an upset
    assert P.upsets_known(games, t) == 2
    assert P.upsets_known(games, t - 1) == 1


def test_fee_correct():
    p, pay = 0.71, 1.0
    pnl, fee, cost = P.trade_pnl(p, pay)
    assert fee == sa.fee_kalshi_direct(0.71, 10) == 0.15   # ceil(0.07*10*0.71*0.29 = 0.1441) = 0.15
    assert pnl == pytest.approx((1 - 0.71) * 10 - 0.15)
    assert cost == pytest.approx(7.10 + 0.15)
    assert P.trade_pnl(0.50, 0.0)[1] == 0.18                 # ceil(0.175)
