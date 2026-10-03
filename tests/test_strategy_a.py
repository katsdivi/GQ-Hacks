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


def test_fill_capped_at_one_minus_tick():
    tr = trades([(-120, "HHH", 0.97), (-60, "AAA", 0.03), (-2, "HHH", 0.98), (3, "HHH", 0.99)])
    r = fav_row(A.evaluate_game(tr, game()), 0.90)
    assert r["entered"] and r["fill_price"] == 0.99 and r["fill_capped"]          # 0.99 trade -> 0.99, not 1.00
    assert r["pnl_webull"] == pytest.approx((1 - 0.99) * 10 - 0.20)
    s = A.summarize(pd.DataFrame(A.evaluate_game(tr, game())))
    assert s.loc[(s.theta == 0.90) & ~s.placebo, "n_capped_fills"].item() == 1
    tr2 = trades(BASE + [(3, "HHH", 0.98)])
    r2 = fav_row(A.evaluate_game(tr2, game()), 0.70)
    assert r2["fill_price"] == 0.99 and not r2["fill_capped"]                     # 0.98 + 1 cent is not capped
    # a market with a 0.001 step: cap 0.999, so the 0.99 trade fills at 1.00 -> capped at 0.999
    g = game()
    g.tick = {"HHH": 0.001, "AAA": 0.001}
    r3 = fav_row(A.evaluate_game(tr, g), 0.90)
    assert r3["fill_price"] == 0.999 and r3["fill_capped"]
    g.tick = {"HHH": 0.01}                                                        # explicit cent tick: as default
    assert fav_row(A.evaluate_game(tr, g), 0.90)["fill_price"] == 0.99


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
    # boundary: the opener is Thu Sep 4, 2025 (ET date); Sep 3 ET is preseason, Sep 4 ET is not
    sep3 = A.Game("nfl_x", "NFL", "H", "A", "X", pd.Timestamp("2025-09-04 03:00", tz="UTC"), "espn", 1.0)
    sep4 = A.Game("nfl_x", "NFL", "H", "A", "X", pd.Timestamp("2025-09-04 16:00", tz="UTC"), "espn", 1.0)
    assert A.is_preseason(sep3) and not A.is_preseason(sep4)
    with pytest.raises(ValueError):                                               # 2026 opener not set
        A.is_preseason(A.Game("nfl_x", "NFL", "H", "A", "X", pd.Timestamp("2026-08-10", tz="UTC"), "espn", 1.0))
    tr = trades(BASE + [(3, "HHH", 0.83)])
    rows = pd.DataFrame(A.evaluate_game(tr, game()) + [dict(r, game_id="nfl_x", preseason=True)
                                                       for r in A.evaluate_game(tr, game())])
    t = A.summarize_side_by_side(rows)
    n = t[(t.theta == 0.70) & ~t.placebo].set_index("sample")["n_trades"]
    assert n["primary"] == 2 and n["no NFL preseason"] == 1


# The four training games with a blank settlement in the games file, and what Kalshi's metadata records for
# them (status/result/settlement_value_dollars only; v3 Amendment 3 section 1). MIA (away of MIA at CHI) 404s.
BLANKS = [("nfl_20250929_gb_dal", "DAL", "GB", "KXNFLGAME-25SEP28GBDAL"),
          ("nfl_20250808_lv_sea", "SEA", "LV", "KXNFLGAME-25AUG07LVSEA"),
          ("nfl_20250810_mia_chi", "CHI", "MIA", "KXNFLGAME-25AUG10MIACHI"),
          ("nfl_20250817_jac_no", "NO", "JAC", "KXNFLGAME-25AUG17JACNO")]
CENT = '[{"end": "1.0000", "start": "0.0000", "step": "0.0100"}]'


def four_games(tmp_path):
    games = [{"game_id": g, "league": "NFL", "home": h, "away": a, "kalshi_event": e, "kalshi_ticker": f"{e}-{h}",
              "kickoff_utc_espn": "2025-09-28T20:25:00Z", "kickoff_source": "espn", "settlement_result": None,
              "n_trades": 100} for g, h, a, e in BLANKS]
    games.append({**games[0], "game_id": "nfl_20251005_x_y", "settlement_result": 1.0})   # a normal game
    meta = []
    for g, h, a, e in BLANKS:
        meta.append({"game_id": g, "side": "home", "ticker": f"{e}-{h}", "status": "finalized", "result": "scalar",
                     "settlement_value_dollars": "0.5000", "price_level_structure": "linear_cent",
                     "price_ranges": CENT})
        meta.append({"game_id": g, "side": "away", "ticker": f"{e}-{a}",
                     **({"status": "not found"} if a == "MIA" else
                        {"status": "finalized", "result": "scalar", "settlement_value_dollars": "0.5000",
                         "price_level_structure": "linear_cent", "price_ranges": CENT})})
    gp, mp = tmp_path / "games.csv", tmp_path / "meta.csv"
    pd.DataFrame(games).to_csv(gp, index=False)
    pd.DataFrame(meta).to_csv(mp, index=False)
    return gp, mp


def test_scalar_settlement_step_on_the_four_blank_games(tmp_path):
    gp, mp = four_games(tmp_path)
    before = gp.read_bytes()
    g = A.apply_scalar_settlements(pd.read_csv(gp), pd.read_csv(mp)).set_index("game_id")
    for gid, *_ in BLANKS:
        assert g.loc[gid, "settlement_result"] == 0.5
        assert g.loc[gid, "settlement_source"] == "kalshi scalar (home market)"
    assert g.loc["nfl_20251005_x_y", "settlement_result"] == 1.0
    assert g.loc["nfl_20251005_x_y", "settlement_source"] == "yes/no"
    assert gp.read_bytes() == before                                              # the games file is not edited
    # only the away market recorded: 1 - its value; no scalar record anywhere: stays blank
    m = pd.read_csv(mp)
    away_only = m[~((m.game_id == "nfl_20250808_lv_sea") & (m.side == "home"))].copy()
    away_only.loc[(away_only.game_id == "nfl_20250808_lv_sea"), "settlement_value_dollars"] = "0.2500"
    r = A.apply_scalar_settlements(pd.read_csv(gp), away_only).set_index("game_id")
    assert r.loc["nfl_20250808_lv_sea", "settlement_result"] == 0.75
    none = A.apply_scalar_settlements(pd.read_csv(gp), m[m.game_id != "nfl_20250817_jac_no"])
    assert none.set_index("game_id")["settlement_result"].isna().sum() == 1


def test_load_games_ticks_and_preseason_assert(tmp_path):
    gp, mp = four_games(tmp_path)
    gs = A.load_games(gp, mp, expect_preseason=0)                 # all five kick off on 2025-09-28
    assert [g.result for g in gs] == [0.5, 0.5, 0.5, 0.5, 1.0]
    assert gs[0].tick == {"DAL": 0.01, "GB": 0.01} and gs[2].tick == {"CHI": 0.01}   # MIA not found: default
    assert A.fill_cap(gs[2], "MIA") == 0.99
    with pytest.raises(AssertionError):
        A.load_games(gp, mp)                                      # the training default expects 49
    assert A.top_step('[{"end": "0.1", "start": "0", "step": "0.001"}, {"end": "1", "start": "0.1", "step": "0.01"}]') == 0.01
    assert math.isnan(A.top_step(None))
