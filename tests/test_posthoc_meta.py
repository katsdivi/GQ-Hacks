"""Synthetic tests for scripts/posthoc_meta.py (post-hoc meta-model). No real data."""
import numpy as np
import pandas as pd
import pytest

import posthoc_meta as M

NS = 1_000_000_000


def synth(n_weeks=10, per_week=40, seed=0):
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2025-09-01 18:00", tz="UTC")       # a Monday
    rows = []
    for w in range(n_weeks):
        for i in range(per_week):
            t = start + pd.Timedelta(days=7 * w + i % 6, minutes=i)
            g = f"cfb_{t:%Y%m%d}_aa{i % 5}_bb{i % 5}"
            fill = rng.uniform(0.2, 0.8)
            pnl = (1 - fill) * 10 - 0.1 if rng.random() < fill else -fill * 10 - 0.1
            rows.append({"strategy": "I7" if i % 2 else "A", "leg": "signal", "game_id": g, "t_ns": t.value,
                         "team": f"bb{i % 5}" if i % 3 else f"aa{i % 5}", "fill": fill, "signal": rng.random(),
                         "pnl": pnl, "fee": 0.1, "league": "CFB", "kickoff_ns": (t + pd.Timedelta(minutes=5)).value})
    return M.add_features(pd.DataFrame(rows))


def test_walk_forward_never_trains_on_week_w_or_later(monkeypatch):
    c = synth()
    seen = []

    class Spy(M.Logit):
        def fit(self, X, y):
            seen.append(len(y))
            return super().fit(X, y)

    out = M.walk_forward(c, lambda: Spy())
    for w, n in zip(M.eval_weeks(c), seen):
        assert n == (c["week"] < w).sum()
    assert set(out["week"]) == set(M.eval_weeks(c))


def test_planted_future_column_is_unused():
    c = synth()
    cells = sorted(c["cell"].unique())
    X1 = M.design(c, cells)
    c2 = c.assign(future_payout=np.where(c["pnl"] > 0, 1.0, 0.0), pnl_next=c["pnl"] * 3)
    X2 = M.design(c2, cells)
    assert np.array_equal(X1, X2)
    for col in ("pnl", "y", "roc", "breakeven", "capital"):
        assert col not in M.NUM


def test_agreement_counts_only_strictly_earlier():
    base = {"strategy": "A", "leg": "x", "game_id": "cfb_20250906_aa_bb", "fill": 0.5, "signal": 0, "pnl": 1.0,
            "fee": 0.1, "league": "CFB", "kickoff_ns": 0}
    t0 = pd.Timestamp("2025-09-06 18:00", tz="UTC").value
    c = pd.DataFrame([{**base, "t_ns": t0, "team": "bb"}, {**base, "t_ns": t0, "team": "aa"},
                      {**base, "t_ns": t0 + NS, "team": "bb"}, {**base, "t_ns": t0 + 2 * NS, "team": "aa"}])
    c = M.add_features(c)
    assert list(c["agree_same"]) == [0, 0, 1, 1]
    assert list(c["agree_opp"]) == [0, 0, 1, 2]


def test_trailing_winrate_uses_only_earlier_dates():
    base = {"strategy": "A", "leg": "x", "fill": 0.5, "signal": 0, "fee": 0.1, "league": "CFB", "kickoff_ns": 0,
            "team": "bb"}
    d = [pd.Timestamp(s, tz="UTC").value for s in ("2025-09-06 18:00", "2025-09-06 20:00", "2025-09-13 18:00")]
    c = pd.DataFrame([{**base, "game_id": "cfb_20250906_aa_bb", "t_ns": d[0], "pnl": 5.0},
                      {**base, "game_id": "cfb_20250906_cc_bb", "t_ns": d[1], "pnl": -5.0},
                      {**base, "game_id": "cfb_20250913_aa_bb", "t_ns": d[2], "pnl": 5.0}])
    c = M.add_features(c)
    assert c["trail_wr"].iloc[0] == 0.5 and c["trail_wr"].iloc[1] == 0.5   # same date: nothing settled yet
    assert c["trail_wr"].iloc[2] == pytest.approx((1 + 1) / (2 + 2))


def test_decision_rule_matches_fee_breakeven():
    c = synth(n_weeks=8)
    hold = c[c["strategy"] == "A"]
    assert np.allclose(hold["breakeven"], hold["fill"] + hold["fee"] / 10)
    out = M.walk_forward(c, lambda: M.Logit())
    assert ((out["p"] > out["breakeven"]) == out["take"]).all()
    rt = M.add_features(synth(n_weeks=1).assign(strategy="B").drop(columns=[
        k for k in ("date", "week", "dow", "cell", "cfb", "preseason", "min_from_ko", "side", "agree_same",
                    "agree_opp", "trail_wr", "breakeven", "capital", "roc", "y")]))
    assert np.allclose(rt["breakeven"], 0.5 + rt["fee"] / 10)


def test_bootstrap_seed_reproducible():
    c = synth()
    assert M.game_boot_ci(c) == M.game_boot_ci(c)
