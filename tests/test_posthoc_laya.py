import numpy as np
import pandas as pd

import posthoc_laya as L


def _cands(n_weeks=9, per=20, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for w in range(n_weeks):
        for i in range(per):
            rows.append({"strategy": "I9", "leg": "signal", "side": "home", "league": "CFB", "preseason": 0,
                         "min_from_ko": 70.0, "dow": 5, "signal": float(rng.normal()), "agree_same": 1,
                         "agree_opp": 0, "trail_wr": 0.5, "fill": 0.5, "pnl": float(rng.normal()), "y": 1,
                         "week": f"2025-09-{w + 1:02d}", "game_id": f"g{w}_{i}", "roc": 0.0, "date": "d"})
    return pd.DataFrame(rows)


def test_text_ignores_excluded_columns():
    c = _cands()
    t1 = L.texts(c)
    c2 = c.assign(fill=0.99, pnl=123.0, y=0, roc=9.9)
    assert L.texts(c2) == t1


def test_walk_forward_never_uses_week_w_or_later():
    c = _cands()
    X = np.random.default_rng(1).normal(size=(len(c), 5))
    p1 = L.walk_forward(c, X, 10.0)
    c2 = c.copy()
    last = sorted(c["week"].unique())[-1]
    c2.loc[c2["week"] == last, "pnl"] += 1000.0   # change only the last week's outcomes
    p2 = L.walk_forward(c2, X, 10.0)
    early = c["week"] != last
    assert np.allclose(np.nan_to_num(p1[early.to_numpy()]), np.nan_to_num(p2[early.to_numpy()]))


def test_first_eval_week_has_six_weeks_history():
    c = _cands()
    assert L.eval_weeks(c)[0] == sorted(c["week"].unique())[6]


def test_decision_rule_does_not_use_fill():
    c = _cands()
    X = np.random.default_rng(2).normal(size=(len(c), 5))
    p1 = L.walk_forward(c, X, 10.0)
    p2 = L.walk_forward(c.assign(fill=0.01), X, 10.0)
    assert np.array_equal(np.isnan(p1), np.isnan(p2)) and np.allclose(np.nan_to_num(p1), np.nan_to_num(p2))
