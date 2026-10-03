"""Strategy A on fake games only (HYPOTHESIS_v3.md + Amendment 1). Prices are P(home) per the tick contract."""
import math

import pandas as pd
import pytest

import strategy_a as A

NS = 1_000_000_000
KO = pd.Timestamp("2025-10-04 20:00", tz="UTC")
T = (KO - pd.Timedelta(minutes=5)).value          # decision instant t


def game(result=1.0, kickoff=KO, source="espn"):
    return A.Game("cfb_20251004_aaa_hhh", "CFB", "HHH", "AAA", "KXNCAAFGAME-25OCT04AAAHHH",
                  kickoff, source, result)


def trades(rows):
    """rows: (seconds relative to t, team, own-market YES price). Stored as P(home) like the real files."""
    out = []
    for s, team, own in rows:
        out.append({"ts": T + int(s * NS), "venue": "kalshi", "market_id": f"KXNCAAFGAME-25OCT04AAAHHH-{team}",
                    "kind": "trade", "price": own if team == "HHH" else 1 - own, "size": 1.0, "side": "buy"})
    return pd.DataFrame(out)


def fav_row(rows, theta):
    return next(r for r in rows if r["theta"] == theta and not r["placebo"])


BASE = [(-120, "HHH", 0.80), (-60, "AAA", 0.21), (-2, "HHH", 0.80)]


def test_fill_is_first_trade_after_latency_plus_cent():
    tr = trades(BASE + [(0.5, "HHH", 0.99), (3, "HHH", 0.83), (10, "HHH", 0.86)])   # 0.5 s is inside the latency
    r = fav_row(A.evaluate_game(tr, game()), 0.70)
    assert r["entered"] and r["team"] == "HHH"
    assert r["fill_price"] == pytest.approx(0.84)            # 0.83 + 1 cent, not the 0.80 before t
    assert r["fill_ts"] == T + 3 * NS
    assert r["pnl_webull"] == pytest.approx((1 - 0.84) * 10 - 0.20)
    assert r["fee_direct"] == pytest.approx(math.ceil(0.07 * 10 * 0.84 * 0.16 * 100) / 100)


def test_fill_exactly_at_t_plus_latency_counts():
    tr = trades(BASE + [(1.0, "HHH", 0.83)])
    assert fav_row(A.evaluate_game(tr, game()), 0.70)["fill_price"] == pytest.approx(0.84)


def test_no_trade_within_5_min_after_t_skips():
    tr = trades(BASE + [(301, "HHH", 0.83)])
    rows = A.evaluate_game(tr, game())
    r = fav_row(rows, 0.70)
    assert not r["entered"] and r["skip"] == "no post-decision trade"
    s = A.summarize(pd.DataFrame(rows))
    assert s[(s.theta == 0.70) & (~s.placebo)]["skipped_no_post_decision_trade"].item() == 1


def test_decision_ignores_trades_after_t():
    # after t the away team trades far above: must not flip the favorite or change the theta check
    tr = trades(BASE + [(2, "AAA", 0.95), (3, "HHH", 0.83)])
    rows = A.evaluate_game(tr, game())
    assert fav_row(rows, 0.70)["team"] == "HHH"
    assert not fav_row(rows, 0.90)["entered"] and fav_row(rows, 0.90)["skip"] == "below theta"


def test_staleness_and_away_favorite_and_tie():
    stale = trades([(-700, "HHH", 0.80), (-60, "AAA", 0.21), (3, "HHH", 0.83)])
    assert fav_row(A.evaluate_game(stale, game()), 0.70)["skip"].startswith("stale")
    away = trades([(-60, "HHH", 0.20), (-30, "AAA", 0.82), (5, "AAA", 0.85)])
    r = fav_row(A.evaluate_game(away, game(result=0.0)), 0.80)
    assert r["team"] == "AAA" and r["fill_price"] == pytest.approx(0.86) and r["payout"] == 1.0
    tie = fav_row(A.evaluate_game(trades(BASE + [(3, "HHH", 0.83)]), game(result=0.5)), 0.70)
    assert tie["entered"] and tie["payout"] == 0.5


def test_placebo_uses_same_fill_rule_and_seal():
    tr = trades(BASE + [(3, "HHH", 0.83), (4, "AAA", 0.18)])
    p = next(r for r in A.evaluate_game(tr, game()) if r["theta"] == 0.70 and r["placebo"])
    assert p["team"] == "AAA" and p["fill_price"] == pytest.approx(0.19) and p["payout"] == 0.0
    with pytest.raises(ValueError):
        A.evaluate_game(tr, game(kickoff=pd.Timestamp("2026-09-05 20:00", tz="UTC")))
    assert fav_row(A.evaluate_game(tr, game(source="kalshi_date")), 0.70)["skip"].startswith("kickoff not from ESPN")


def test_select_theta_needs_50_trades():
    s = pd.DataFrame({"theta": [0.7, 0.8, 0.9, 0.7], "placebo": [False, False, False, True],
                      "n_trades": [120, 60, 49, 120], "roc_webull_mean": [0.01, 0.03, 0.10, 0.5]})
    assert A.select_theta(s) == 0.8


def test_fill_capped_at_99_cents():
    tr = trades([(-120, "HHH", 0.97), (-60, "AAA", 0.03), (-2, "HHH", 0.98), (3, "HHH", 0.99)])
    r = fav_row(A.evaluate_game(tr, game()), 0.90)
    assert r["entered"] and r["fill_price"] == 0.99 and r["fill_capped"]          # 0.99 trade -> 0.99, not 1.00
    assert r["pnl_webull"] == pytest.approx((1 - 0.99) * 10 - 0.20)
    s = A.summarize(pd.DataFrame(A.evaluate_game(tr, game())))
    assert s.loc[(s.theta == 0.90) & ~s.placebo, "n_capped_fills"].item() == 1
    tr2 = trades(BASE + [(3, "HHH", 0.98)])
    r2 = fav_row(A.evaluate_game(tr2, game()), 0.70)
    assert r2["fill_price"] == 0.99 and not r2["fill_capped"]                     # 0.98 + 1 cent is not capped


def test_preseason_flag_and_side_by_side():
    pre = A.Game("nfl_20250810_aaa_hhh", "NFL", "HHH", "AAA", "KXNCAAFGAME-25OCT04AAAHHH", KO, "espn", 1.0)
    hof = A.Game("nfl_20250801_aaa_hhh", "NFL", "HHH", "AAA", "X", pd.Timestamp("2025-08-01 00:00", tz="UTC"),
                 "espn", 1.0)
    reg = A.Game("nfl_20250905_aaa_hhh", "NFL", "HHH", "AAA", "X", pd.Timestamp("2025-09-05 00:20", tz="UTC"),
                 "espn", 1.0)
    aug = A.Game("nfl_20250810_aaa_hhh", "NFL", "HHH", "AAA", "X", pd.Timestamp("2025-08-10 17:00", tz="UTC"),
                 "espn", 1.0)
    cfb_aug = A.Game("cfb_20250830_aaa_hhh", "CFB", "HHH", "AAA", "X", pd.Timestamp("2025-08-30 16:00", tz="UTC"),
                     "espn", 1.0)
    assert [A.is_preseason(g) for g in (hof, aug, reg, cfb_aug)] == [True, True, False, False]
    assert not A.is_preseason(pre)                                                # October kickoff
    tr = trades(BASE + [(3, "HHH", 0.83)])
    rows = pd.DataFrame(A.evaluate_game(tr, game()) + [dict(r, game_id="nfl_x", preseason=True)
                                                       for r in A.evaluate_game(tr, game())])
    t = A.summarize_side_by_side(rows)
    n = t[(t.theta == 0.70) & ~t.placebo].set_index("sample")["n_trades"]
    assert n["primary"] == 2 and n["no NFL preseason"] == 1
