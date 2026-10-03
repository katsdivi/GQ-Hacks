"""Mann-Whitney (scipy) vs the earlier custom version, fixed-verdict decisions, and Holm across venues.
Synthetic data only."""
import numpy as np
import pytest
from scipy.stats import mannwhitneyu

import xcorr_lead as X
from tests.test_activity_bias import hidden_path, quotes

HAND = [([1, 2, 3, 4, 5], [6, 7, 8, 9, 10]),               # no ties, full separation
        ([1, 2, 2, 3, 5, 5], [2, 4, 5, 5, 6, 7, 7]),       # ties across groups
        ([5] * 12, list(range(-15, 16)))]                    # constant group vs spread (the fixture shape)


@pytest.mark.parametrize("a,b", HAND)
def test_custom_matches_scipy_asymptotic(a, b):
    ref = mannwhitneyu(a, b, alternative="two-sided", method="asymptotic", use_continuity=True).pvalue
    assert X.mann_whitney_p_custom(a, b) == pytest.approx(ref, rel=1e-9)
    assert X.mann_whitney_p(a, b) == pytest.approx(mannwhitneyu(a, b, alternative="two-sided").pvalue, rel=1e-12)


def _pair(rng, lag, linked=True, poll=False):
    pk = hidden_path(rng)
    po = pk if linked else hidden_path(rng)
    qk = quotes(rng, pk, 0.0, 6, "kalshi")
    qo = (quotes(rng, po, lag, 1, "other", poll_s=1, recv_delay_s=0.3) if poll else quotes(rng, po, lag, 2, "other"))
    return X.game_lag_mid(qk, "kalshi", qo, "other")


@pytest.fixture(scope="module")
def lags():
    rng = np.random.default_rng(101)
    return {"lead": [_pair(rng, 5.0) for _ in range(80)],
            "zero": [_pair(rng, 0.0) for _ in range(80)],
            "placebo": [_pair(rng, 0.0, linked=False) for _ in range(150)]}


def test_fixed_verdict_80_games_5s_lead(lags):
    d = X.decide(lags["lead"], lags["placebo"], 0.0, "kalshi", "other", min_lead_s=1.0)
    assert d["result"] == "kalshi leads", d
    assert d["mann_whitney_p"] < 0.01


def test_fixed_verdict_zero_lag_linked(lags):
    d = X.decide(lags["zero"], lags["placebo"], 0.0, "kalshi", "other", min_lead_s=1.0)
    assert d["result"].startswith("inconclusive") or d["result"] == "neither venue leads consistently", d


def test_holm_levels_and_stop(lags):
    lead, zero, pl = lags["lead"], lags["zero"], lags["placebo"]
    out = X.decide_holm({"polymarket.com": (lead, pl, "polymarket", 1.0), "Polymarket US": (zero, pl, "polymarket_us", 1.5)})
    assert out["polymarket.com"]["holm_level"] == 0.025 and out["polymarket.com"]["result"] == "kalshi leads"
    assert out["Polymarket US"]["holm_level"] == 0.05
    # p between 0.025 and 0.05 on the smaller test: Holm rejects nothing, so neither test can lead
    rng = np.random.default_rng(7)
    weak = list(rng.choice(np.arange(-15, 16), 30)) + [5] * 30
    p = X.mann_whitney_p(weak, pl)
    if 0.025 <= p < 0.05:
        o = X.decide_holm({"a": (weak, pl, "x", 1.0), "b": (weak, pl, "y", 1.0)})
        assert all(v["result"] != "kalshi leads" for v in o.values())
    # levels: smaller p judged at 0.025; larger at 0.05 only if the smaller passed, else 0.0 (Holm stopped)
    spread = list(range(-15, 16)) * 3
    o = X.decide_holm({"a": ([5] * 40, spread, "x", 1.0), "b": ([0] * 40, spread, "y", 1.0)})
    pa, pb = X.mann_whitney_p([5] * 40, spread), X.mann_whitney_p([0] * 40, spread)
    assert pa < 0.025 and o["a"]["holm_level"] == 0.025 and o["b"]["holm_level"] == 0.05 and pb > 0.05
    o = X.decide_holm({"a": ([0] * 40, spread, "x", 1.0), "b": ([0] * 41, spread, "y", 1.0)})
    assert sorted(v["holm_level"] for v in o.values()) == [0.0, 0.025]
