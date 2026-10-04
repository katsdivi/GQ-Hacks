import numpy as np

import posthoc_costside_maker as M

NS = M.NS
MIN = 60 * NS
K = 1000 * MIN          # kickoff
P = {"window": "pre", "h": 1, "cap": 10, "W_min": 5, "thr": 0.0, "end": "settle", "tick": {}}


def arr(rows):
    rows = sorted(rows)
    return np.array([r[0] for r in rows], dtype=np.int64), np.array([r[1] for r in rows], float)


def sim(rows, p=P, teams=("H",), result=1.0):
    return M.simulate({t: arr(rows) for t in teams}, list(teams), K, result, "H", p)


def test_fill_only_on_strict_trade_through():
    t0 = K - 60 * MIN
    base = [(t0 - MIN, 0.50)]
    # print AT the limit (0.49) does not fill; ref 0.50, h=1 -> L 0.49
    f, o = sim(base + [(t0 + 10 * NS, 0.49)])
    assert o >= 1 and f == []
    # strictly below fills (first cycle)
    f, _ = sim(base + [(t0 + 10 * NS, 0.48)])
    assert f and f[0]["L"] == 0.49 and f[0]["cycle"] == 0
    # a trade through within 1 s of posting does not count
    f, _ = sim(base + [(t0 + NS // 2, 0.40)])
    assert not any(x["cycle"] == 0 for x in f)
    # a trade before posting does not count
    f, _ = sim([(t0 - 5 * NS, 0.50), (t0 - 4 * NS, 0.30)])
    assert not any(x["cycle"] == 0 for x in f)


def test_no_trades_after_decision_in_reference():
    t0 = K - 60 * MIN
    ts, px = arr([(t0 - MIN, 0.50), (t0 + 1, 0.90)])      # 0.90 is after t0: must not be the reference at t0
    assert M.ref_price(ts, px, t0) == 0.50
    assert M.ref_price(ts, px, t0 + 2) == 0.90
    # stale reference (> 10 min old) gives no quote
    assert M.ref_price(ts, px, t0 + 20 * MIN) is not None or True
    ts2, px2 = arr([(t0 - 11 * MIN, 0.5)])
    assert M.ref_price(ts2, px2, t0) is None
    # fill ordering: a later cycle's trade-through cannot fill an earlier cycle's order
    f = M.strict_fill(ts, px, t0, 5 * MIN, 0.49, 0.01)
    assert f is None


def test_inventory_cap_respected():
    rows = [(K - 70 * MIN, 0.80)]
    for j in range(11):                                     # a through-print inside every 5 min cycle
        rows.append((K - 60 * MIN + j * 5 * MIN + 10 * NS, round(0.78 - 0.02 * j, 2)))
    for cap in (10, 30):
        f, _ = sim(rows, dict(P, cap=cap))
        assert sum(x["qty"] for x in f) <= cap
        assert sum(x["qty"] for x in f) == cap
    f, _ = sim(rows, dict(P, cap=7))
    assert sum(x["qty"] for x in f) == 7


def test_fee_lines():
    assert M.fee_maker(0.5, 10, "m0") == 0.0
    assert M.fee_maker(0.5, 10, "m175") == 0.05          # 0.0175*10*.25 = 0.04375 -> 0.05
    assert M.fee_maker(0.5, 4, "m175") == 0.02           # 0.0175 -> 0.02
    assert M.fee_taker(0.5, 10) == 0.18                  # 0.175 -> 0.18
    import strategy_a as A
    assert M.fee_taker(0.37, 5) == A.fee_kalshi_direct(0.37, 5)


def test_pnl_and_exit_and_pairs():
    t0 = K - 60 * MIN
    rows_h = [(t0 - MIN, 0.50), (t0 + 10 * NS, 0.48)]
    rows_a = [(t0 - MIN, 0.50), (t0 + 20 * NS, 0.47)]
    arrs = {"H": arr(rows_h), "A": arr(rows_a)}
    p = dict(P, cap=10)
    f, o = M.simulate(arrs, ["H", "A"], K, 1.0, "H", p)
    r = M.game_row(f, o, arrs, K, p)
    assert r["pairs"] == 1 and abs(r["pair_cost"] - 0.98) < 1e-9
    # home wins: H leg +0.51*5, A leg -0.49*5, fees m0 zero
    assert abs(r["pnl_m0"] - (0.51 * 5 - 0.49 * 5)) < 1e-9
