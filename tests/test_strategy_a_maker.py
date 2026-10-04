"""Strategy A-maker on fake games only (v3 Amendment 5 draft). Same fake-game helpers as tests/test_strategy_a.py:
trades at seconds relative to t = kickoff - 5 min, own-market YES prices, stored as P(home)."""
import pandas as pd
import pytest

import strategy_a_maker as M
from tests.test_strategy_a import BASE, T, game, trades

NS = 1_000_000_000
# BASE: HHH own price 0.80 at t (fresh), AAA 0.21 -> favorite HHH, as-of 0.80 >= theta 0.80, L = 0.79


def fav(rows):
    return next(r for r in rows if not r["placebo"])


def test_fill_only_on_trade_through():
    at_limit = trades(BASE + [(30, "HHH", 0.79), (60, "HHH", 0.80)])          # prints AT L only: not filled
    r = fav(M.evaluate_game(at_limit, game()))
    assert r["attempted"] and r["limit_price"] == pytest.approx(0.79) and not r["entered"] and r["skip"] == "unfilled"
    through = trades(BASE + [(30, "HHH", 0.79), (45, "HHH", 0.78)])           # 0.78 <= L - 1 tick: filled at L
    r = fav(M.evaluate_game(through, game()))
    assert r["entered"] and r["fill_price"] == pytest.approx(0.79) and r["fill_ts"] == T + 45 * NS
    assert r["pnl_webull"] == pytest.approx((1.0 - 0.79) * 10 - 0.20)        # home won (result 1.0)


def test_no_fill_from_trade_before_t_plus_1s_or_after_kickoff():
    early = trades(BASE + [(0.5, "HHH", 0.70)])                               # inside the 1 s latency: ignored
    assert fav(M.evaluate_game(early, game()))["skip"] == "unfilled"
    exactly = trades(BASE + [(1.0, "HHH", 0.70)])                              # at t + 1 s: interval is open there
    assert fav(M.evaluate_game(exactly, game()))["skip"] == "unfilled"
    late = trades(BASE + [(301, "HHH", 0.70)])                                 # after kickoff (t + 300 s)
    assert fav(M.evaluate_game(late, game()))["skip"] == "unfilled"
    at_ko = trades(BASE + [(300, "HHH", 0.70)])                                # at kickoff: included
    assert fav(M.evaluate_game(at_ko, game()))["entered"]


def test_unfilled_counted_and_placebo_same_rule():
    tr = trades(BASE + [(30, "HHH", 0.80), (40, "AAA", 0.19)])               # fav never trades through; dog does
    rows = M.evaluate_game(tr, game())
    s = M.summarize(pd.DataFrame(rows)).set_index("leg")
    assert s.loc["favorite", "attempts"] == 1 and s.loc["favorite", "fills"] == 0 and s.loc["favorite", "unfilled"] == 1
    d = next(r for r in rows if r["placebo"])
    assert d["limit_price"] == pytest.approx(0.20) and d["entered"] and d["fill_price"] == pytest.approx(0.20)


def test_decision_unchanged_from_a_and_theta_fixed():
    below = trades([(-120, "HHH", 0.75), (-60, "AAA", 0.26), (-2, "HHH", 0.75), (30, "HHH", 0.70)])
    assert all(r["skip"] == "below theta" for r in M.evaluate_game(below, game()))   # 0.75 < 0.80
    stale = trades([(-700, "HHH", 0.85), (-60, "AAA", 0.15), (30, "HHH", 0.70)])
    assert all(r["skip"].startswith("stale") for r in M.evaluate_game(stale, game()))
    with pytest.raises(ValueError):
        M.evaluate_game(trades(BASE), game(kickoff=pd.Timestamp("2026-09-05 20:00", tz="UTC")))


def test_limit_rounding_and_costs_x2():
    assert M.limit_price(0.805, 0.01) == pytest.approx(0.80)                  # 0.795 rounds to the cent grid
    assert M.limit_price(0.8, 0.001) == pytest.approx(0.79)
    e = pd.DataFrame({"fill_price": [0.79], "payout": [1.0]})
    x = M.costs_x2(e).iloc[0]
    assert x.fill_price == pytest.approx(0.80) and x.pnl_webull == pytest.approx((1 - 0.80) * 10 - 0.40)
