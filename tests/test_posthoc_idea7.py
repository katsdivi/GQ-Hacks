"""Synthetic tests for scripts/posthoc_idea7.py (post-hoc Idea 7). No real data."""
from __future__ import annotations

import pandas as pd
import pytest

import posthoc_idea7 as I

NS = I.NS
KO = pd.Timestamp("2025-10-04 20:00", tz="UTC")
T = KO.value - 5 * 60 * NS
EV = "KXNCAAFGAME-25OCT04AAABBB"


def game(settle_home=1.0, kickoff=KO):
    return {"game_id": "g", "league": "CFB", "kickoff": kickoff, "home_ticker": f"{EV}-BBB",
            "away_ticker": f"{EV}-AAA", "settle": {f"{EV}-BBB": settle_home, f"{EV}-AAA": 1.0 - settle_home}}


def ktr(rows):
    """rows: (ts_ns, market 'home'/'away', own YES price). Stored as P(home)."""
    out = []
    for ts, mk, p in rows:
        out.append({"ts": ts, "venue": "kalshi", "market_id": f"{EV}-BBB" if mk == "home" else f"{EV}-AAA",
                    "kind": "trade", "price": p if mk == "home" else round(1 - p, 4), "size": 10.0, "side": "buy"})
    return pd.DataFrame(out)


def ptr(rows):
    """rows: (ts_ns, P(home))."""
    return pd.DataFrame([{"ts": ts, "venue": "polymarket", "market_id": "0xabc", "kind": "trade", "price": p,
                          "size": 10.0, "side": "buy"} for ts, p in rows])


def base_k():
    # home K 0.50, away K 0.50 at t - 60 s; post-decision fills
    return [(T - 60 * NS, "home", 0.50), (T - 60 * NS, "away", 0.50),
            (T + 2 * NS, "home", 0.51), (T + 2 * NS, "away", 0.49)]


def sig(rows, k=0.03, leg="signal"):
    return [r for r in rows if r["k"] == k and r["leg"] == leg][0]


def test_trade_after_t_never_changes_signal():
    kt, pt = ktr(base_k()), ptr([(T - 30 * NS, 0.56)])
    a = I.evaluate_game(game(), kt, pt)
    # add trades after t on both venues that would flip the gap
    kt2 = pd.concat([kt, ktr([(T + 1, "home", 0.90), (T + NS // 2, "away", 0.10)])], ignore_index=True)
    pt2 = pd.concat([pt, ptr([(T + 1, 0.20), (T + 10 * NS, 0.10)])], ignore_index=True)
    b = I.evaluate_game(game(), kt2, pt2)
    for x, y in zip(a, b):
        assert x.get("team") == y.get("team") and x.get("g") == y.get("g") and x["skip"] == y["skip"]
        assert x.get("K_home") == y.get("K_home") and x.get("Q_home") == y.get("Q_home")


def test_trade_exactly_at_t_is_used():
    kt, pt = ktr(base_k()), ptr([(T - 30 * NS, 0.50), (T, 0.56)])
    r = sig(I.evaluate_game(game(), kt, pt))
    assert r["Q_home"] == 0.56 and r["team"] == "home"


def test_fill_never_before_t_plus_1s():
    kt = ktr(base_k() + [(T + NS - 1, "home", 0.40)])     # 1 ns too early: must not be the fill
    pt = ptr([(T - 30 * NS, 0.56)])
    r = sig(I.evaluate_game(game(), kt, pt))
    assert r["entered"] and r["fill_ts"] >= T + NS and r["trade_px"] == 0.51


def test_fill_window_5_min():
    kt = ktr([(T - 60 * NS, "home", 0.50), (T - 60 * NS, "away", 0.50), (T + NS + 300 * NS + 1, "home", 0.51)])
    r = sig(I.evaluate_game(game(), kt, ptr([(T - 30 * NS, 0.56)])))
    assert not r["entered"] and r["skip"] == "no post-decision trade"


def test_stale_price_skips_game():
    kt = ktr([(T - 11 * 60 * NS, "home", 0.50), (T - 60 * NS, "away", 0.50), (T + 2 * NS, "home", 0.51)])
    r = sig(I.evaluate_game(game(), kt, ptr([(T - 30 * NS, 0.56)])))
    assert r["skip"] == "stale or missing price"


def test_orientation_swap_same_trade():
    """Same game with home/away labels swapped on both venues buys the same real team at the same price."""
    kt, pt = ktr(base_k()), ptr([(T - 30 * NS, 0.56)])
    a = sig(I.evaluate_game(game(), kt, pt))
    # swapped: the real home team (BBB) is now listed as away; polymarket stored as P(new home) = 1 - 0.56
    g2 = {"game_id": "g", "league": "CFB", "kickoff": KO, "home_ticker": f"{EV}-AAA", "away_ticker": f"{EV}-BBB",
          "settle": {f"{EV}-BBB": 1.0, f"{EV}-AAA": 0.0}}
    rows = []
    for ts, mk, p in base_k():
        tick = f"{EV}-BBB" if mk == "home" else f"{EV}-AAA"
        new_home = tick == f"{EV}-AAA"
        rows.append({"ts": ts, "venue": "kalshi", "market_id": tick, "kind": "trade",
                     "price": p if new_home else round(1 - p, 4), "size": 10.0, "side": "buy"})
    b = sig(I.evaluate_game(g2, pd.DataFrame(rows), ptr([(T - 30 * NS, 0.44)])))
    assert a["ticker"] == b["ticker"] == f"{EV}-BBB"
    assert a["fill"] == b["fill"] and a["g"] == pytest.approx(b["g"]) and a["pnl_direct"] == b["pnl_direct"]


def test_placebo_buys_negative_gap_team():
    kt, pt = ktr(base_k()), ptr([(T - 30 * NS, 0.56)])     # g_home +0.06, g_away -0.06
    rows = I.evaluate_game(game(), kt, pt)
    p = sig(rows, leg="placebo")
    assert p["team"] == "away" and p["g"] == pytest.approx(-0.06)
    assert sig(rows, k=0.05)["team"] == "home"


def test_threshold_k():
    kt, pt = ktr(base_k()), ptr([(T - 30 * NS, 0.52)])     # g_home +0.02
    rows = I.evaluate_game(game(), kt, pt)
    assert sig(rows, k=0.02)["entered"] and sig(rows, k=0.03)["skip"] == "no signal"


def test_payout_from_kalshi_settlement_and_void():
    kt, pt = ktr(base_k()), ptr([(T - 30 * NS, 0.56)])
    assert sig(I.evaluate_game(game(settle_home=0.0), kt, pt))["payout"] == 0.0
    assert sig(I.evaluate_game(game(settle_home=0.5), kt, pt))["payout"] == 0.5
    g = game()
    g["settle"][f"{EV}-BBB"] = None
    assert sig(I.evaluate_game(g, kt, pt))["skip"] == "void/unsettled"


@pytest.mark.parametrize("p,fee", [(0.3, 0.15), (0.5, 0.18), (0.8, 0.12)])
def test_fee_function(p, fee):
    # 0.07 x 10 x P(1-P) rounded up to the cent: 0.147 -> 0.15, 0.175 -> 0.18, 0.112 -> 0.12
    assert float(I.fee_direct(I.D(p))) == fee
    assert float(I.fee_webull(I.D(p))) == 0.20


def test_holdout_refused():
    with pytest.raises(ValueError):
        I.evaluate_game(game(kickoff=pd.Timestamp("2026-08-02", tz="UTC")), ktr(base_k()), ptr([(T, 0.5)]))


def test_orientation_flag_rule():
    assert I.orientation_flag(0.30, 0.70) and not I.orientation_flag(0.50, 0.52)
