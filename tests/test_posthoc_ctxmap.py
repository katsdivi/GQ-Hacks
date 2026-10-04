"""Synthetic tests for scripts/posthoc_ctxmap.py (post-hoc context map). No real data."""
import numpy as np
import pandas as pd

import posthoc_ctxmap as M


def _pool(n_weeks=10, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    t = 0
    for w in range(n_weeks):
        week = f"2025-09-{w + 1:02d}"
        for i in range(30):
            t += 1
            cell = ["X:a", "Y:b"][i % 2]
            pnl = float(rng.normal(0.5 if cell == "X:a" else -0.5, 1))
            rows.append({"cell": cell, "game_id": f"g{w}_{i}", "t_ns": t, "week": week, "date": week,
                         "league": "CFB", "min_from_ko": -5.0, "fill": 0.5, "pnl": pnl, "roc": pnl / 5,
                         "y": int(pnl > 0), "breakeven": 0.51})
    return M.add_context(pd.DataFrame(rows))


def test_week_w_never_used_for_week_w():
    c = _pool()
    seen = {}
    orig = M.choose

    def spy(past, n):
        seen.setdefault("weeks", []).append(set(past["week"]))
        return orig(past, n)
    M.choose = spy
    try:
        _, picks = M.walk_forward(c, 20)
    finally:
        M.choose = orig
    for w, ws in zip(sorted(picks), seen["weeks"]):
        assert all(x < w for x in ws)


def test_future_column_unused():
    c = _pool()
    a, _ = M.walk_forward(c, 20)
    c2 = c.copy()
    c2["future_payout"] = np.random.default_rng(1).normal(size=len(c2))   # planted, must be ignored
    c2["min_from_ko_after"] = 999
    b, _ = M.walk_forward(c2, 20)
    assert a[["cell", "game_id"]].reset_index(drop=True).equals(b[["cell", "game_id"]].reset_index(drop=True))
    # load() keeps only spec columns
    assert "future_payout" not in M.USED


def test_contexts_from_decision_time_fields():
    df = pd.DataFrame({"league": ["CFB", "NFL", "CFB"], "min_from_ko": [-1.0, 90.0, 90.5], "fill": [0.34, 0.65, 0.66]})
    ctx = df["league"] + "|" + M.phase(df["min_from_ko"]) + "|" + M.band(df["fill"])
    assert list(ctx) == ["CFB|pre|lo", "NFL|early|mid", "CFB|late|hi"]


def test_eligibility_exact():
    past = pd.DataFrame({"ctx": ["x"] * 39, "cell": ["A:a"] * 20 + ["B:b"] * 19, "cpc": [1.0] * 20 + [5.0] * 19})
    assert M.choose(past, 20) == {"x": "A:a"}          # B has 19 < 20
    assert M.choose(past, 19) == {"x": "B:b"}
    neg = past.assign(cpc=0.0)
    assert M.choose(neg, 1) == {}                       # score must be > 0


def test_tie_break_deterministic():
    past = pd.DataFrame({"ctx": ["x"] * 50, "cell": ["B:b"] * 25 + ["A:a"] * 25, "cpc": [1.0] * 50})
    assert M.choose(past, 20) == {"x": "A:a"}           # equal score and n: alphabetical
    past2 = pd.concat([past, pd.DataFrame({"ctx": ["x"], "cell": ["B:b"], "cpc": [1.0]})])
    assert M.choose(past2, 20) == {"x": "B:b"}          # equal score, more trades wins


def test_bootstrap_reproducible():
    c = _pool()
    assert M.game_boot_ci(c) == M.game_boot_ci(c)
