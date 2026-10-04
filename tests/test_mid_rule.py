"""Amendment 2 mid rule (HYPOTHESIS_v2.md, committed 8a509ff): mid only when both sides exist, never
filled across an empty side; a mid change is a second whose defined mid differs from the previous
defined mid. Synthetic books only."""
import numpy as np
import pandas as pd

import xcorr_lead as X
from tests.test_activity_bias import quote_study

NS = 1_000_000_000


def book(rows):
    """rows: (second, bid or None, ask or None) -> collector-style rows; an empty side writes no row."""
    out = []
    for s, b, a in rows:
        ts = int(s * NS) + 123
        if b is not None:
            out.append({"ts": ts, "venue": "v", "market_id": "m", "kind": "bid", "price": b})
        if a is not None:
            out.append({"ts": ts, "venue": "v", "market_id": "m", "kind": "ask", "price": a})
    return pd.DataFrame(out)


def test_empty_side_30s_has_no_mid_and_no_changes():
    rows = [(s, 0.50 + 0.01 * (s % 2), 0.52 + 0.01 * (s % 2)) for s in range(0, 20)]   # two-sided, moving
    rows += [(s, 0.60 + 0.01 * (s % 3), None) for s in range(20, 50)]                  # ask empty 30 s, bid moving
    rows += [(s, 0.50, 0.52) for s in range(50, 60)]
    g = X.mid_grid(X.mid_snapshots(book(rows), "v"))
    span = g.loc[20:49]
    assert span.isna().all(), "no mid while the ask side is empty"
    assert X.mid_changes(g).loc[20:49].isna().all(), "no changes inside the empty span"
    assert g.loc[50] == 0.51 and not np.isnan(g.loc[19])
    # a second with no snapshot after the side empties does not revive the old mid
    g2 = X.mid_grid(X.mid_snapshots(book([(0, 0.5, 0.52), (5, 0.5, None), (40, 0.5, 0.52)]), "v"))
    assert g2.loc[5:39].isna().all() and g2.loc[0:4].notna().all()


def test_duplicate_rows_add_no_changes():
    base = [(s, 0.50 + 0.01 * (s // 10), 0.52 + 0.01 * (s // 10)) for s in range(0, 100)]
    one = book(base)
    dup = pd.concat([one, one, one], ignore_index=True)                       # every row written 3 times
    rep = book(base + [(s + 0.5, 0.50 + 0.01 * (s // 10), 0.52 + 0.01 * (s // 10)) for s in range(0, 100)])
    n = X.n_mid_changes(X.mid_grid(X.mid_snapshots(one, "v")))
    assert n == 9
    assert X.n_mid_changes(X.mid_grid(X.mid_snapshots(dup, "v"))) == n
    assert X.n_mid_changes(X.mid_grid(X.mid_snapshots(rep, "v"))) == n      # repeats at new timestamps
    one_sided = book([(s, 0.97, None) for s in range(0, 300)])                 # the Polymarket US bug case
    assert X.n_mid_changes(X.mid_grid(X.mid_snapshots(one_sided, "v"))) == 0


def test_synthetic_zero_lag_and_5s_lead_recovered():
    for other in ("polymarket.com", "Polymarket US"):
        r = quote_study(3, other, games=30, studies=1)
        assert r["zero_lag"]["median_lag"] == 0 and r["zero_lag"]["kalshi_leads_rate"] == 0, (other, r["zero_lag"])
        assert r["lead_5s"]["median_lag"] == 5 and r["lead_5s"]["share_lag5"] == 1, (other, r["lead_5s"])
    # Decision power at 30 games is ~60-70% (docs/results/activity_bias.md); this seed passes on polymarket.com
    assert quote_study(3, "polymarket.com", games=30, studies=1)["lead_5s"]["kalshi_leads_rate"] == 1


def test_two_sided_books_match_previous_function():
    """Where no side is ever empty the new rule changes nothing: same lag as the pre-amendment version."""
    import subprocess, types
    from tests.test_activity_bias import hidden_path, quotes
    src = subprocess.run(["git", "show", "8a509ff:xcorr_lead.py"], capture_output=True, text=True, check=True).stdout
    old = types.ModuleType("xcorr_lead_old")
    exec(compile(src, "xcorr_lead_old", "exec"), old.__dict__)
    rng = np.random.default_rng(11)
    for lag in (0.0, 5.0, 0.0, 5.0):
        p = hidden_path(rng)
        qk = quotes(rng, p, 0.0, 6, "kalshi")
        qo = quotes(rng, p, lag, 1, "other", poll_s=1, recv_delay_s=0.3)
        assert X.game_lag_mid(qk, "kalshi", qo, "other") == old.game_lag_mid(qk, "kalshi", qo, "other")
