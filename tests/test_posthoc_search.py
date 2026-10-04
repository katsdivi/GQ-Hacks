"""Synthetic tests for scripts/posthoc_search.py (no real data)."""
import numpy as np
import pandas as pd
import pytest

import posthoc_search as S


def pool(n_weeks=10, per_week=40, seed=0, edge_cell=None):
    rng = np.random.default_rng(seed)
    rows = []
    t0 = pd.Timestamp("2025-09-01", tz="UTC")
    cells = [("I7", "signal"), ("I8", "fade"), ("I12", "signal"), ("A", "favorite")]
    for w in range(n_weeks):
        wk = (t0 + pd.Timedelta(weeks=w)).tz_convert(None).date().isoformat()
        for i in range(per_week):
            s, l = cells[i % len(cells)]
            t = t0 + pd.Timedelta(weeks=w, hours=i)
            fill = float(rng.uniform(0.1, 0.9))
            pnl = float(rng.normal(-0.1, 1.0)) + (1.0 if edge_cell == s else 0.0)
            rows.append(dict(strategy=s, leg=l, game_id=f"g{w}_{i // 4}", t_ns=t.value, team="X" if i % 2 else "Y",
                             fill=fill, signal=float(rng.uniform(0.02, 0.5)), pnl=pnl, fee=0.1, league="CFB",
                             kickoff_ns=t.value, date=t.tz_convert(None).date().isoformat(), week=wk, dow=0,
                             min_from_ko=float(rng.uniform(-10, 200)), side="home", agree_same=0, agree_opp=0,
                             trail_wr=0.5, breakeven=fill + 0.01, capital=fill * 10 + 0.1,
                             roc=pnl / (fill * 10 + 0.1), y=int(pnl > 0)))
    return S.prep(pd.DataFrame(rows))


def test_no_future_data_planted_column_ignored():
    c = pool()
    c2 = c.assign(future_pnl=c["pnl"] * 100)               # planted future column, must not matter
    for f in (lambda d: S.price_filter(d, "040to060"), lambda d: S.fine_threshold(d, "I7:signal"),
              lambda d: S.hedge(d, 0.5), S.thompson):
        a, b = f(c), f(c2)
        assert list(a["uid"]) == list(b["uid"])


def test_walk_forward_boundaries():
    c = pool()
    w = S.eval_weeks(c)[0]
    base = S.fine_threshold(c, "I7:signal")
    c2 = c.copy()
    later = c2["week"] > w
    c2.loc[later, "pnl"] = -c2.loc[later, "pnl"] * 50   # changing later weeks must not change week w picks
    b2 = S.fine_threshold(c2, "I7:signal")
    assert list(base.loc[base["week"] == w, "uid"]) == list(b2.loc[b2["week"] == w, "uid"])
    same = S.price_filter(c, "ge080"), S.price_filter(c2, "ge080")
    assert list(same[0].loc[same[0]["week"] == w, "uid"]) == list(same[1].loc[same[1]["week"] == w, "uid"])


def test_consensus_uses_only_earlier_or_same_time():
    t = pd.Timestamp("2025-09-10", tz="UTC").value
    base = dict(game_id="g", team="X", fill=0.5, signal=0.1, pnl=1.0, fee=0.1, league="NFL", kickoff_ns=t,
                date="2025-09-10", week="2025-09-08", dow=2, min_from_ko=-5.0, side="home", agree_same=0,
                agree_opp=0, trail_wr=0.5, breakeven=0.51, capital=5.1, roc=0.2, y=1)
    rows = [dict(base, strategy="I7", leg="signal", t_ns=t), dict(base, strategy="I8", leg="fade", t_ns=t + 10),
            dict(base, strategy="I13", leg="signal", t_ns=t + 20)]
    c = S.prep(pd.DataFrame(rows))
    b2 = S.consensus(c, 2, False, "hyp")
    assert len(b2) == 1 and b2.iloc[0]["strategy"] == "I8"   # second distinct idea, never the first
    b3 = S.consensus(c, 3, False, "hyp")
    assert len(b3) == 1 and b3.iloc[0]["strategy"] == "I13"
    agree = S.with_agreement(c)
    assert list(agree) == [0, 1, 2]


def test_hedge_updates_only_on_past_dates():
    c = pool(n_weeks=8)
    d0 = sorted(c["date"].unique())[0]
    first = S.hedge(c, 0.5)
    # on the first date all weights are uniform -> nothing exceeds 1/K strictly
    assert not (first["date"] == d0).any()
    c2 = c.copy()
    last = sorted(c["date"].unique())[-1]
    c2.loc[c2["date"] == last, "roc"] = 0.99               # change the last date's outcomes
    a, b = S.hedge(c, 0.5), S.hedge(c2, 0.5)
    assert list(a["uid"]) == list(b["uid"])                 # decisions on every date unchanged


def test_reality_check_noise_vs_planted():
    rng = np.random.default_rng(1)
    noise = rng.normal(0, 1, size=(120, 20))
    r = S.reality_check(noise, reps=500)
    assert r["rc_p"] > 0.2
    planted = noise.copy()
    planted[:, 3] += 1.0
    r2 = S.reality_check(planted, reps=500)
    assert r2["rc_p"] < 0.01 and r2["best"] == 3 and r2["rw_p"][3] < 0.01


def test_seed_reproducible():
    c = pool()
    e = c[c["week"].isin(S.eval_weeks(c))]
    assert S.boot_roc(e) == S.boot_roc(e)
    assert list(S.thompson(c)["uid"]) == list(S.thompson(c)["uid"])
    D = np.random.default_rng(2).normal(size=(50, 5))
    assert S.reality_check(D, reps=200)["rc_p"] == S.reality_check(D, reps=200)["rc_p"]


def test_sized_fee_and_holm():
    assert S.fee_direct(0.5, 20) == 0.35 and S.fee_direct(0.5, 5) == 0.09
    p = np.array([0.001, 0.02, 0.5])
    assert list(S.holm(p)) == [True, True, False] or list(S.holm(p)) == [True, False, False]
