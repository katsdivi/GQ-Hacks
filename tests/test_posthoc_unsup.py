"""Synthetic tests for post-hoc unsupervised regime mining (no real data)."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "scripts")
import posthoc_unsup as U  # noqa: E402
import unsup_common as C  # noqa: E402

NS = 1_000_000_000
KO = 1_760_000_000 * NS


def _trades(extra=None):
    rows = []
    for i in range(400):                                   # trades every 30 s from ko - 2 h
        ts = KO - 7200 * NS + i * 30 * NS
        rows.append((ts, "EV-H", "trade", 0.60 + 0.0001 * (i % 7), 5.0, "buy" if i % 2 else "sell"))
        rows.append((ts + NS, "EV-A", "trade", 0.60, 3.0, "sell"))   # stored as P(home)
    if extra:
        rows += extra
    return pd.DataFrame(rows, columns=["ts", "market_id", "kind", "price", "size", "side"])


def _rows(trades, es=None, ori=None):
    return pd.DataFrame(U.game_rows("g", "NFL", "H", "A", "EV", KO, trades, None, es, ori, np.nan, False))


def test_future_trades_change_nothing():
    base = _rows(_trades())
    # plant trades strictly after every decision time's t: only those AFTER the last decision time are safe to
    # add for all rows, so compare each row against a build where trades after that row's t are wild
    for m in U.DEC_MIN:
        t = KO + m * 60 * NS
        wild = [(t + NS * (j + 1), "EV-H", "trade", 0.05, 999.0, "sell") for j in range(5)]
        tr = _trades()
        tr = pd.concat([tr[tr.ts <= t], pd.DataFrame(wild, columns=tr.columns)])
        a = base[base.dec_min == m].reset_index(drop=True)
        b = _rows(tr)
        b = b[b.dec_min == m].reset_index(drop=True)
        pd.testing.assert_frame_equal(a[U.FEATS], b[U.FEATS])


def test_espn_only_past_plays():
    es = {"ts": np.array([KO + 60 * NS, KO + 3000 * NS], dtype=np.int64), "home": np.array([0.0, 7.0]),
          "away": np.array([0.0, 0.0]), "period": np.array([1.0, 2.0]), "clock": np.array([800.0, 100.0]),
          "poss": ["1", "2"], "wp": np.array([0.5, 0.9]), "home_id": "1"}
    f = U.espn_at(es, KO + 1200 * NS, True)                # t = ko + 20 min: only the first play is known
    assert f["es_diff"] == 0.0 and f["es_wp"] == 0.5 and f["es_period"] == 1.0
    g = U.espn_at(es, KO + 3000 * NS, True)
    assert g["es_diff"] == 7.0 and g["es_wp"] == 0.9
    h = U.espn_at(es, KO + 3000 * NS, False)               # away orientation flips diff and wp
    assert h["es_diff"] == -7.0 and abs(h["es_wp"] - 0.1) < 1e-12


def test_espn_defect_rule():
    s = {"drives": {"previous": [{"plays": [
        {"wallclock": pd.Timestamp(KO + 600 * NS, unit="ns").isoformat() + "Z", "homeScore": 0, "awayScore": 0,
         "period": {"number": 1}, "clock": {"displayValue": "10:00"}, "id": "1"},
        {"wallclock": pd.Timestamp(KO - 0 * NS, unit="ns").isoformat() + "Z", "homeScore": 0, "awayScore": 0,
         "period": {"number": 1}, "clock": {"displayValue": "9:00"}, "id": "2"}]}]},
        "header": {"competitions": [{"competitors": [{"id": "1", "homeAway": "home"}, {"id": "2", "homeAway": "away"}]}]}}
    assert U.espn_state(s, KO) is None                     # 10 min backward jump


def test_clustering_fit_uses_only_train_rows():
    rng = np.random.default_rng(0)
    tr = rng.normal(size=(300, 5))
    te1 = rng.normal(size=(50, 5))
    te2 = te1.copy()
    te2[:, 0] += 100.0                                      # test rows cannot move the fitted model
    l1, a1 = U.fit_assign(tr, te1, "kmeans", 4)
    l2, a2 = U.fit_assign(tr, te2, "kmeans", 4)
    assert (l1 == l2).all()
    g1, _ = U.fit_assign(tr, te1, "gmm", 4)
    g2, _ = U.fit_assign(tr, te2, "gmm", 4)
    assert (g1 == g2).all()


def test_walk_forward_cluster_stats_past_only():
    # week w rows' outcomes must not affect week w eligibility: flip all week-w payouts and compare eligibility
    rng = np.random.default_rng(1)
    n = 700
    df = pd.DataFrame({f: rng.normal(size=n) for f in U.FEATS})
    df["p"] = rng.uniform(0.2, 0.8, n)
    df["week"] = np.repeat(np.arange(7), 100)
    df["payout"] = (rng.random(n) < df["p"]).astype(float)
    X = df[U.FEATS].to_numpy(float)
    past, cur = (df.week < 6).to_numpy(), (df.week == 6).to_numpy()
    ltr, lte = U.fit_assign(X[past], X[cur], "kmeans", 4)
    st1 = df[past].assign(cl=ltr).groupby("cl")["payout"].mean()
    df2 = df.copy()
    df2.loc[cur, "payout"] = 1 - df2.loc[cur, "payout"]
    ltr2, lte2 = U.fit_assign(df2[U.FEATS].to_numpy(float)[past], df2[U.FEATS].to_numpy(float)[cur], "kmeans", 4)
    st2 = df2[past].assign(cl=ltr2).groupby("cl")["payout"].mean()
    assert (lte == lte2).all() and np.allclose(st1.values, st2.values)


def test_fees_and_cost():
    assert C.fee_taker(0.5) == 0.18                         # 0.07*10*0.25 = 0.175 -> 0.18
    assert C.fee_maker175(0.5) == 0.05                      # 0.04375 -> 0.05
    c = U.cost(np.array([0.5]), "taker")[0]
    assert abs(c - (0.01 + 0.018)) < 1e-12
    assert abs(U.cost(np.array([0.5]), "maker")[0] - 0.005) < 1e-12


def test_taker_fill_after_t_plus_1s():
    ts = np.array([KO, KO + NS - 1, KO + NS, KO + 2 * NS], dtype=np.int64)
    px = np.array([0.4, 0.41, 0.42, 0.43])
    e = C.taker_entry(ts, px, KO, win_s=300)
    assert e[0] == KO + NS and abs(e[1] - 0.43) < 1e-9
