"""Book-wipe exclusion (HYPOTHESIS_v2.md Amendment 3 draft) on synthetic books only.

Each game: Kalshi and the other venue quote the same hidden path with no lag, except around kickoff, where
the other venue's book is wiped (a "book_empty" marker row), stays empty 60 s, then re-quotes for 4 min by
copying Kalshi 5 s late while the price moves fast (kickoff). Without the exclusion the copy period makes
Kalshi look like the leader; after the exclusion it must not.
"""
import numpy as np
import pandas as pd

import holdout_mid as H
import xcorr_lead as X

NS = 1_000_000_000
W = 3600                      # window seconds, kickoff at W // 2
KO = W // 2
EMPTY_S, COPY_S, COPY_LAG = 60, 240, 5


def path(rng):
    vol = np.where((np.arange(W) >= KO) & (np.arange(W) < KO + EMPTY_S + COPY_S), 0.02, 0.003)
    jump = rng.random(W) < np.where(vol > 0.01, 0.5, 0.05)
    return np.clip(0.5 + np.cumsum(jump * rng.normal(0, vol)), 0.1, 0.9).round(2)


def book(ts_s, mids, venue, market, t0):
    rows = []
    prev = None
    for t, m in zip(ts_s, mids):
        if m == prev:
            continue
        prev = m
        for k, px in (("bid", m - 0.01), ("ask", m + 0.01)):
            rows.append({"ts": t0 + int(t) * NS + 200_000_000, "venue": venue, "market_id": market,
                         "kind": k, "price": round(px, 4)})
    return rows


def game(rng, wiped=True):
    t0 = 1_760_000_000 * NS
    p = path(rng)
    s = np.arange(W)
    k = book(s, p, "kalshi", "K", t0)
    other = p.copy()
    copy = (s >= KO + EMPTY_S) & (s < KO + EMPTY_S + COPY_S)
    other[copy] = p[np.flatnonzero(copy) - COPY_LAG]
    keep = (s < KO) | (s >= KO + EMPTY_S)
    o = book(s[keep], other[keep], "polymarket", "P", t0)
    if wiped:
        o.append({"ts": t0 + KO * NS + 100_000_000, "venue": "polymarket", "market_id": "P",
                  "kind": "book_empty", "price": np.nan})
    return pd.DataFrame(k), pd.DataFrame(o).sort_values("ts", kind="stable"), t0 + KO * NS


def test_wipe_found_and_mid_undefined_while_empty():
    tk, to, ko = game(np.random.default_rng(1))
    sides = X.sides_snapshots(to, "polymarket")
    assert (sides == 0).sum() == 1
    g = X.mid_grid(X.mid_snapshots(to, "polymarket"))
    assert g.loc[ko // NS + 1: ko // NS + EMPTY_S - 1].isna().all()     # never carried across the wipe
    (lo, hi), src = H.wipe_exclusion(to, "polymarket", ko, ko // NS + W)
    assert src == "clear"
    assert lo == ko // NS - 120
    assert hi == ko // NS + EMPTY_S + 300                              # 5 min after two-sided again


def test_fallback_when_no_clear_recorded():
    tk, to, ko = game(np.random.default_rng(2), wiped=False)
    (lo, hi), src = H.wipe_exclusion(to, "polymarket", ko, ko // NS + W)
    assert (src, lo, hi) == ("fallback", ko // NS - 120, ko // NS + 600)


def test_change_never_spans_exclusion():
    g = pd.Series([0.5, 0.5, 0.6, np.nan, np.nan, 0.9, 0.9], index=np.arange(10, 17))
    c = X.mid_changes(g, exclude=[(12, 14)])
    assert np.isnan(c.loc[15])                       # 0.9 has no previous mid: no 0.4 jump across the gap
    assert c.loc[16] == 0


def test_requote_copying_kalshi_is_not_a_lead_after_exclusion():
    rng = np.random.default_rng(7)
    raw, excl = [], []
    for _ in range(40):
        tk, to, ko = game(rng)
        raw.append(X.game_lag_mid(tk, "kalshi", to, "polymarket"))
        ex, _ = H.wipe_exclusion(to, "polymarket", ko, ko // NS + W)
        excl.append(X.game_lag_mid(tk, "kalshi", to, "polymarket", exclude=[ex]))
    raw, excl = np.array(raw), np.array(excl)
    # placebo: unrelated games (Kalshi of one game vs the other venue of another), with the exclusion
    pl = []
    for _ in range(40):
        tk, _to, _ = game(rng)
        _tk, to, ko = game(rng)
        ex, _ = H.wipe_exclusion(to, "polymarket", ko, ko // NS + W)
        pl.append(X.game_lag_mid(tk, "kalshi", to, "polymarket", exclude=[ex]))
    pl = np.array(pl)
    assert (raw == COPY_LAG).mean() >= 0.9                              # the trap is real without the rule
    assert (excl == 0).mean() >= 0.9
    assert X.decide(excl, pl, 0.0, "kalshi", "polymarket")["result"] != "kalshi leads"
