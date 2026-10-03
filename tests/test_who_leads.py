"""Decision rule of who_leads.py (docs/stats_plan.md steps 7 to 11) on synthetic per-game results."""
import pandas as pd
import pytest

import who_leads as w

D = 2.119


def _games(Ls, matched=10):
    return pd.DataFrame({"L_s": Ls, "n_matched": matched})


def test_sign_test_exact():
    assert w.sign_test(10, 0) == pytest.approx(2 / 1024)
    assert w.sign_test(5, 5) == 1.0


def test_inconclusive_under_30_games():
    assert w.summarise(_games([5.0] * 29), D, "kalshi", "polymarket")["result"].startswith("inconclusive")


def test_games_with_few_matched_jumps_do_not_qualify():
    s = w.summarise(_games([5.0] * 40, matched=4), D, "kalshi", "polymarket")
    assert s["n_qualifying"] == 0 and s["result"].startswith("inconclusive")


def test_kalshi_needs_one_second_plus_median_d():
    assert w.summarise(_games([5.0] * 40), D, "kalshi", "polymarket")["result"] == "kalshi leads"
    assert w.summarise(_games([2.5] * 40), D, "kalshi", "polymarket")["result"] == "neither venue leads consistently"


def test_polymarket_needs_one_second():
    assert w.summarise(_games([-1.5] * 40), D, "kalshi", "polymarket")["result"] == "polymarket leads"
    assert w.summarise(_games([-0.5] * 40), D, "kalshi", "polymarket")["result"] == "neither venue leads consistently"


def test_no_majority_means_neither():
    s = w.summarise(_games([5.0] * 20 + [-5.0] * 20), D, "kalshi", "polymarket")
    assert s["result"] == "neither venue leads consistently"


def test_ties_excluded_from_sign_test():
    s = w.summarise(_games([5.0] * 35 + [0.0] * 10), D, "kalshi", "polymarket")
    assert s["ties"] == 10 and s["sign_test_p"] == pytest.approx(w.sign_test(35, 0))
