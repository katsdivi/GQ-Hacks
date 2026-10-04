"""Synthetic tests for scripts/posthoc_regress.py (post-hoc residual regression)."""
import numpy as np
import pandas as pd
import pytest

import posthoc_regress as R
import regress_common as C

NS = C.NS


def _series(ts, px, sz=None, yes=None):
    ts = np.array(ts, dtype=np.int64)
    n = len(ts)
    return (ts, np.array(px, float), np.ones(n) if sz is None else np.array(sz, float),
            np.ones(n, bool) if yes is None else np.array(yes, bool))


def test_team_feats_ignore_future_trades():
    t = 1_000 * NS
    s1 = _series([100 * NS, 500 * NS, 900 * NS], [0.40, 0.42, 0.45])
    s2 = _series([100 * NS, 500 * NS, 900 * NS, 1_001 * NS, 1_500 * NS], [0.40, 0.42, 0.45, 0.90, 0.10])
    assert R.team_feats(s1, t) == R.team_feats(s2, t)


def test_trade_at_t_is_used_and_stale_skipped():
    t = 10_000 * NS
    assert R.team_feats(_series([t], [0.5]), t)["p"] == 0.5
    assert R.team_feats(_series([t - (R.STALE_S + 1) * NS], [0.5]), t) is None


def _toy(weeks=10, n=60, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for w in range(weeks):
        for i in range(n):
            p = rng.uniform(0.1, 0.9)
            rec = {f: rng.normal() for f in R.FEATS}
            rec.update(p=p, game_id=f"g{w}_{i}", team="H", t_ns=w * 10 ** 12 + i, week=w,
                       pay=float(rng.random() < p), mins=-5)
            rows.append(rec)
    df = pd.DataFrame(rows)
    df["r"] = df["pay"] - df["p"]
    df["c"] = 0.02
    df["y"] = (df["r"] > df["c"]).astype(float)
    return df


def test_walk_forward_boundary(monkeypatch):
    df = _toy()
    seen = []

    def spy(model, tr, te, feats=R.FEATS):
        seen.append((tr["week"].max(), te["week"].unique().tolist()))
        return np.zeros(len(te))

    monkeypatch.setattr(R, "predict", spy)
    R.walk_forward(df, first_test=6)
    assert seen and all(mx < te[0] and len(te) == 1 for mx, te in seen)


def test_planted_future_column_unused():
    df = _toy()
    tr, te = df[df.week < 8], df[df.week == 8].copy()
    a = R.predict("RIDGE10", tr, te)
    tr2, te2 = tr.assign(future=tr["pay"]), te.assign(future=te["pay"])
    b = R.predict("RIDGE10", tr2, te2)
    assert np.allclose(a, b)


def test_iso_uses_past_only():
    df = _toy()
    tr, te = df[df.week < 8], df[df.week == 8].copy()
    a = R.predict("ISO", tr, te)
    te2 = te.assign(pay=1 - te["pay"], r=lambda d: d["pay"] - d["p"])
    b = R.predict("ISO", tr, te2)
    assert np.allclose(a, b)
    hi, v = R.pav(np.array([0.1, 0.2, 0.3, 0.4]), np.array([1.0, 0.0, 1.0, 1.0]))
    assert np.all(np.diff(v) >= 0)


def _summary(plays, home_id="1"):
    return {"header": {"competitions": [{"competitors": [{"id": home_id, "homeAway": "home"},
                                                          {"id": "2", "homeAway": "away"}]}]},
            "drives": {"previous": [{"team": {"id": "1"}, "plays": plays}]},
            "winprobability": [{"playId": p["id"], "homeWinPercentage": p["_wp"]} for p in plays]}


def test_espn_only_plays_up_to_t():
    ko = pd.Timestamp("2025-10-01T00:00Z").value
    mk = lambda i, m, hs, wp: {"id": str(i), "wallclock": (pd.Timestamp(ko) + pd.Timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                               "homeScore": hs, "awayScore": 0, "period": {"number": 1},
                               "clock": {"displayValue": "10:00"}, "_wp": wp}
    p1 = [mk(1, 10, 0, 0.5), mk(2, 20, 7, 0.7)]
    p2 = p1 + [mk(3, 40, 14, 0.95)]
    t = ko + 30 * 60 * NS
    a = R.espn_at(R.espn_state(_summary(p1), ko, "same"), t, True)
    b = R.espn_at(R.espn_state(_summary(p2), ko, "same"), t, True)
    assert a == b and a["score_diff"] == 7 and abs(a["wp"] - 0.7) < 1e-12
    c = R.espn_at(R.espn_state(_summary(p2), ko, "swapped"), t, True)   # Kalshi home = ESPN away
    assert c["score_diff"] == -7 and abs(c["wp"] - 0.3) < 1e-12


def test_thresholds_and_fees():
    assert C.fee_taker(0.5) == 0.18          # 0.07 x 10 x 0.25 = 0.175 -> 0.18
    assert C.fee_maker175(0.5) == 0.05       # 0.0175 x 10 x 0.25 = 0.04375 -> 0.05
    assert R.threshold("TAKER", 0.49, 0.0) == pytest.approx(0.01 + 0.018)
    assert R.threshold("MAKER", 0.51, 0.01) == pytest.approx(-0.01 + 0.005 + 0.01)
