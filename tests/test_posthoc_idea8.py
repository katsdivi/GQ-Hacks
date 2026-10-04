"""Synthetic tests for Post-hoc Idea 8 (no real data)."""
import numpy as np
import pandas as pd
import pytest

import posthoc_idea8 as P
import strategy_a as A

NS = P.NS
KO = pd.Timestamp("2025-10-04 20:00", tz="UTC")
T = KO.value - 300 * NS


def game(home="HOM", away="AWY", result=1.0):
    return A.Game("cfb_test", "CFB", home, away, "EV", KO, "espn", result)


def tr(rows):
    """rows: (seconds from kickoff, team code, own YES price, size, side in P(home) terms)."""
    return pd.DataFrame([{"ts": KO.value + int(s * NS), "venue": "kalshi", "market_id": f"EV-{m}", "kind": "trade",
                          "price": p, "size": float(z), "side": sd} for s, m, p, z, sd in rows])


def base(home_px=0.60):
    """Pressure on the home team inside W, plus fills after t."""
    return [(-1800, "HOM", home_px, 400, "buy"), (-1700, "AWY", home_px, 300, "buy"),
            (-1200, "HOM", home_px, 100, "sell"),
            (-299, "HOM", home_px, 10, "sell"), (-299, "AWY", home_px, 10, "sell")]


def test_stored_side_equals_raw_taker_formula():
    g = game()
    rng = np.random.default_rng(0)
    raw, stored = [], []
    for k in range(200):
        s = int(rng.integers(-2400, 0))
        m = ["HOM", "AWY"][k % 2]
        ts_side = ["yes", "no"][int(rng.integers(0, 2))]
        size = float(rng.integers(1, 50))
        raw.append({"ts": KO.value + s * NS, "market_id": f"EV-{m}", "taker_side": ts_side, "size": size})
        side = {"yes": "buy", "no": "sell"}[ts_side]
        if m == "AWY":                                   # ingest/kalshi.py:152-155
            side = {"buy": "sell", "sell": "buy"}[side]
        stored.append((s, m, 0.5, size, side))
    ph, _ = P.pressure(tr(stored), g)
    assert ph == pytest.approx(P.pressure_raw(pd.DataFrame(raw), g))


def test_trade_at_or_after_t_never_changes_I():
    g = game()
    a = P.pressure(tr(base()), g)
    b = P.pressure(tr(base() + [(-300, "HOM", 0.6, 5000, "buy"), (-200, "AWY", 0.6, 5000, "sell")]), g)
    assert a == b


def test_trade_before_W_never_changes_I():
    g = game()
    a = P.pressure(tr(base()), g)
    b = P.pressure(tr(base() + [(-2100 - 1e-6, "HOM", 0.6, 5000, "buy"), (-3000, "AWY", 0.6, 999, "buy")]), g)
    assert a == b
    c = P.pressure(tr(base() + [(-2100, "HOM", 0.6, 5, "buy")]), g)   # W is closed at kickoff - 35 min
    assert c[1] == a[1] + 5


def test_fill_never_before_t_plus_1s():
    g = game()
    rows = base()[:3] + [(-300 + 0.5, "AWY", 0.40, 10, "sell"), (-300 + 0.999, "AWY", 0.41, 10, "sell"),
                     (-300 + 1.0, "AWY", 0.42, 10, "sell")]
    out = P.evaluate_game(tr(rows), g, xs=(0.2,))
    fade = [r for r in out if r["leg"] == "fade"][0]
    assert fade["team"] == "AWY" and fade["entered"]
    assert fade["fill_ts"] >= T + NS
    # own YES of AWY at 1 - 0.42 stored P(home) = 0.58, + 1 cent
    assert fade["trade_px"] == pytest.approx(0.58) and fade["fill"] == pytest.approx(0.59)


def test_no_fill_after_window():
    g = game()
    rows = base()[:3] + [(-300 + 1 + 300 + 1e-6, "AWY", 0.42, 10, "sell")]
    out = P.evaluate_game(tr(rows), g, xs=(0.2,))
    assert [r["skip"] for r in out if r["leg"] == "fade"] == ["no post-decision trade"]


def test_swap_home_away_mirrors_trade():
    rows = base() + [(-298, "HOM", 0.60, 10, "sell"), (-298, "AWY", 0.60, 10, "sell")]
    g1 = game("HOM", "AWY", result=1.0)
    out1 = {r["leg"]: r for r in P.evaluate_game(tr(rows), g1, xs=(0.2,))}
    # Relabel: AWY is now home. Stored prices/sides are P(home) terms, so flip them all.
    flip = [(s, m, round(1 - p, 4), z, {"buy": "sell", "sell": "buy"}[sd]) for s, m, p, z, sd in rows]
    g2 = game("AWY", "HOM", result=0.0)
    out2 = {r["leg"]: r for r in P.evaluate_game(tr(flip), g2, xs=(0.2,))}
    assert out1["fade"]["I"] == pytest.approx(-out2["fade"]["I"])
    for lg in ("fade", "placebo"):
        assert out1[lg]["team"] == out2[lg]["team"]
        assert out1[lg]["fill"] == pytest.approx(out2[lg]["fill"])
        assert out1[lg]["pnl_direct"] == pytest.approx(out2[lg]["pnl_direct"])


def test_v_below_500_skips():
    g = game()
    rows = [(-1800, "HOM", 0.6, 100, "buy"), (-298, "AWY", 0.4, 10, "buy")]
    assert {r["skip"] for r in P.evaluate_game(tr(rows), g)} == {"V < 500"}


def test_holdout_refused():
    g = A.Game("cfb_h", "CFB", "HOM", "AWY", "EV", pd.Timestamp("2026-09-05 20:00", tz="UTC"), "espn", 1.0)
    with pytest.raises(ValueError):
        P.evaluate_game(tr([]), g)


@pytest.mark.parametrize("p,expect", [(0.3, 0.15), (0.5, 0.18), (0.8, 0.12)])
def test_fee_function(p, expect):
    # 0.07 x 10 x P(1-P): 0.147 -> 0.15, 0.175 -> 0.18, 0.112 -> 0.12 (rounded up to the cent)
    assert float(P.fee_direct(P.D(p))) == pytest.approx(expect)
    assert float(P.fee_webull(P.D(p))) == pytest.approx(0.20)
