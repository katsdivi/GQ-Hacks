"""Synthetic tests for Post-hoc Idea 9 (post-hoc, exploratory; ESPN data used as a signal only)."""
from decimal import Decimal

import pandas as pd
import pytest

import posthoc_idea9 as P
import strategy_a as A

NS = P.NS
KO = pd.Timestamp("2025-10-04 20:00", tz="UTC")
KO_NS = KO.value


def game(result=1.0, home="HOM", away="AWY"):
    return A.Game(game_id="syn", league="CFB", home=home, away=away, event="EV", kickoff=KO,
                  kickoff_source="espn", result=result)


def trades(rows, g):
    """rows: (seconds after kickoff, team, own YES price). Stored as P(home) like the tick contract."""
    out = []
    for s, team, p in rows:
        out.append({"ts": KO_NS + int(s * NS), "venue": "kalshi", "market_id": f"EV-{team}", "kind": "trade",
                    "price": p if team == g.home else 1 - p, "size": 10.0, "side": "buy"})
    return pd.DataFrame(out)


def summary(wp_plays, espn_home="Home Team", espn_away="Away Team", markers=(), abbr=("HOM", "AWY")):
    """wp_plays: (seconds after kickoff for wallclock, ESPN homeWinPercentage)."""
    plays, wp = [], []
    for i, (s, hw) in enumerate(wp_plays):
        pid = f"p{i}"
        wc = (KO + pd.Timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%SZ")
        plays.append({"id": pid, "wallclock": wc, "text": "run for 3 yds"})
        wp.append({"playId": pid, "homeWinPercentage": hw, "tiePercentage": 0.0})
    for j, s in enumerate(markers):
        plays.append({"id": f"m{j}", "wallclock": (KO + pd.Timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "text": "End of 4th Quarter"})
    comp = {"competitors": [
        {"homeAway": "home", "team": {"displayName": espn_home, "abbreviation": abbr[0]}},
        {"homeAway": "away", "team": {"displayName": espn_away, "abbreviation": abbr[1]}}]}
    return {"header": {"competitions": [comp]}, "drives": {"previous": [{"plays": plays}]}, "winprobability": wp}


NAMES = ("Home Team", "Away Team")


def entered(rows, k, d, lg):
    return [r for r in rows if r["k"] == k and r["delay"] == d and r["leg"] == lg][0]


def test_espn_never_used_before_wallclock_plus_delay():
    g = game()
    # Kalshi home steady at 0.50 with fresh trades every 10 s; ESPN says 0.70 for the home team at wallclock 1800 s.
    tr = trades([(s, "HOM", 0.50) for s in range(1500, 3000, 10)] + [(s, "AWY", 0.50) for s in range(1500, 3000, 10)], g)
    rows = P.evaluate_game(tr, g, summary([(1800, 0.70)]), NAMES)
    for d in P.DELAYS:
        r = entered(rows, 0.05, d, "signal")
        assert r["t_ns"] == KO_NS + (1800 + d) * NS
        assert r["team"] == "HOM"


def test_kalshi_trade_after_t_never_changes_signal():
    g = game()
    base = [(s, "HOM", 0.50) for s in range(1500, 3000, 10)] + [(s, "AWY", 0.50) for s in range(1500, 3000, 10)]
    s1 = summary([(1800, 0.70)])
    r1 = entered(P.evaluate_game(trades(base, g), g, s1, NAMES), 0.05, 60, "signal")
    t = r1["t_ns"]
    # add a trade 1 ns after t at an extreme price; the decision (t, team, g) must not change
    extra = trades(base, g)
    extra = pd.concat([extra, pd.DataFrame([{"ts": t + 1, "venue": "kalshi", "market_id": "EV-HOM", "kind": "trade",
                                             "price": 0.95, "size": 1.0, "side": "buy"}])]).sort_values("ts")
    r2 = entered(P.evaluate_game(extra, g, s1, NAMES), 0.05, 60, "signal")
    assert (r2["t_ns"], r2["team"], r2["g"], r2["kalshi_p"]) == (r1["t_ns"], r1["team"], r1["g"], r1["kalshi_p"])


def test_fill_never_before_t_plus_1s():
    g = game()
    t_s = 1800 + 60
    rows = [(s, "HOM", 0.50) for s in range(1500, t_s + 1, 10)] + [(s, "AWY", 0.50) for s in range(1500, 3000, 10)]
    rows += [(t_s + 0.5, "HOM", 0.40), (t_s + 1.0, "HOM", 0.55)]
    r = entered(P.evaluate_game(trades(rows, g), g, summary([(1800, 0.70)]), NAMES), 0.05, 60, "signal")
    assert r["entered"]
    assert r["fill_ts"] >= r["t_ns"] + NS
    assert r["trade_px"] == 0.55 and r["fill"] == 0.56


def test_no_fill_after_5_min_window():
    g = game()
    t_s = 1800 + 60
    rows = [(s, "HOM", 0.50) for s in range(1500, t_s + 1, 10)] + [(s, "AWY", 0.50) for s in range(1500, 3000, 10)]
    tr = trades(rows, g)
    late = pd.DataFrame([{"ts": KO_NS + (t_s + 1 + 300) * NS + 1, "venue": "kalshi", "market_id": "EV-HOM",
                          "kind": "trade", "price": 0.55, "size": 1.0, "side": "buy"}])
    r = entered(P.evaluate_game(pd.concat([tr, late]), g, summary([(1800, 0.70)]), NAMES), 0.05, 60, "signal")
    assert not r["entered"] and r["skip"] == "no post-decision trade"


def test_orientation_swap_mirrors_trade():
    g = game()
    rows = [(s, "HOM", 0.50) for s in range(1500, 3000, 10)] + [(s, "AWY", 0.50) for s in range(1500, 3000, 10)]
    tr = trades(rows, g)
    # ESPN lists the teams reversed (ESPN home = Kalshi away). ESPN home 0.70 means Kalshi AWAY at 0.70.
    s_swapped = summary([(1800, 0.70)], espn_home="Away Team", espn_away="Home Team", abbr=("AWY", "HOM"))
    r = entered(P.evaluate_game(tr, g, s_swapped, NAMES), 0.05, 60, "signal")
    assert r["team"] == "AWY"
    s_same = summary([(1800, 0.70)])
    assert entered(P.evaluate_game(tr, g, s_same, NAMES), 0.05, 60, "signal")["team"] == "HOM"
    # the placebo is the other team in each case
    assert entered(P.evaluate_game(tr, g, s_swapped, NAMES), 0.05, 60, "placebo")["team"] == "HOM"


def test_window_and_marker():
    g = game()
    rows = [(s, "HOM", 0.50) for s in range(0, 4 * 3600, 10)] + [(s, "AWY", 0.50) for s in range(0, 4 * 3600, 10)]
    tr = trades(rows, g)
    # before kickoff + 20 min: ignored; after the first end marker: ignored
    s = summary([(600, 0.90), (5000, 0.90)], markers=(4000,))
    out = P.evaluate_game(tr, g, s, NAMES)
    assert all(not r["entered"] and r["skip"] == "no signal" for r in out)


def test_stale_kalshi_price_skips_t():
    g = game()
    rows = [(1500, "HOM", 0.50), (1500, "AWY", 0.50), (1900, "HOM", 0.50), (1900, "AWY", 0.50)]
    out = P.evaluate_game(trades(rows, g), g, summary([(1800, 0.90)]), NAMES)
    assert entered(out, 0.05, 60, "signal")["skip"] == "no signal"   # last trade 360 s before t = 1860 s


def test_payout_uses_kalshi_settlement():
    g = game(result=0.0)   # Kalshi settled home loses, whatever ESPN said
    rows = [(s, "HOM", 0.50) for s in range(1500, 3000, 10)] + [(s, "AWY", 0.50) for s in range(1500, 3000, 10)]
    r = entered(P.evaluate_game(trades(rows, g), g, summary([(1800, 0.99)]), NAMES), 0.05, 60, "signal")
    assert r["team"] == "HOM" and r["payout"] == 0.0 and r["pnl_direct"] < 0


@pytest.mark.parametrize("p,fee", [(0.3, "0.15"), (0.5, "0.18"), (0.8, "0.12")])
def test_fee_function(p, fee):
    # 0.07 x 10 x P x (1 - P), rounded up to the cent: 0.147 -> 0.15, 0.175 -> 0.18, 0.112 -> 0.12
    assert P.fee_direct(Decimal(str(p))) == Decimal(fee)
    assert P.fee_webull(Decimal(str(p))) == Decimal("0.20")


def test_holdout_game_refused():
    g = A.Game(game_id="h", league="CFB", home="HOM", away="AWY", event="EV",
               kickoff=pd.Timestamp("2026-09-05", tz="UTC"), kickoff_source="espn", result=1.0)
    with pytest.raises(ValueError):
        P.evaluate_game(trades([(0, "HOM", 0.5), (0, "AWY", 0.5)], g), g, summary([]), NAMES)
