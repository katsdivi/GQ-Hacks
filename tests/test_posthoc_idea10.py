"""Synthetic tests for Post-hoc Idea 10 (scoring-event fade). post-hoc, exploratory; selected on training only."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import posthoc_idea10 as I
import strategy_a as A

NS = I.NS
KO = pd.Timestamp("2025-10-04 20:00", tz="UTC")
WC = KO.value + 3600 * NS          # scoring play 1 h after kickoff


def game(result=1.0, home="HOM", away="AWY"):
    return A.Game(game_id="g1", league="CFB", home=home, away=away, event="EV", kickoff=KO,
                  kickoff_source="espn", result=result)


def ticks(rows, g):
    """rows: (seconds after WC, team, own YES price). Stored per the tick contract: price = P(home)."""
    out = []
    for s, team, p in rows:
        out.append({"ts": WC + int(s * NS), "venue": "kalshi", "market_id": f"{g.event}-{team}", "kind": "trade",
                    "price": p if team == g.home else 1 - p, "size": 10.0, "side": "buy"})
    return pd.DataFrame(out)


def base_rows(g, after_t=None):
    """Home scores at WC: home YES 0.50 before, 0.60 by t (move +0.10). Away mirrors."""
    r = [(-30, g.home, 0.50), (-30, g.away, 0.50), (50, g.home, 0.60), (50, g.away, 0.40),
         (62, g.away, 0.41), (62, g.home, 0.59), (245, g.away, 0.45), (245, g.home, 0.55)]
    return r + (after_t or [])


EV = [{"wc_ns": WC, "side": "home", "ptype": "touchdown", "order": 1}]


def run(g, rows, ev=EV, orientation="same", ss=(0.05,)):
    out, _, _ = I.evaluate_game(ticks(rows, g), g, ev, orientation, ss=ss)
    return pd.DataFrame(out)


def test_basic_fade_trade():
    g = game()
    r = run(g, base_rows(g))
    f = r[r.leg == "fade"].iloc[0]
    assert f.team == "AWY" and f.m == pytest.approx(0.10)
    assert f.entry_trade == pytest.approx(0.41) and f.entry == pytest.approx(0.42)
    assert f.exit_trade == pytest.approx(0.45) and f.exit == pytest.approx(0.44)
    p = r[r.leg == "placebo"].iloc[0]
    assert p.team == "HOM"


def test_no_trade_after_t_feeds_signal():
    g = game()
    a = run(g, base_rows(g))
    # add trades after t = WC + 60 s that would change the post-price if used (and none in (t-30, t])
    b = run(g, base_rows(g, after_t=[(60.5, g.home, 0.90), (61, g.home, 0.10)]))
    fa, fb = a[a.leg == "fade"].iloc[0], b[b.leg == "fade"].iloc[0]
    assert fa.m == fb.m == pytest.approx(0.10)
    # a trade exactly at t counts (at or before t), one just after does not
    s = I.signal({g.home: (np.array([WC - NS, WC + 60 * NS + 1]), np.array([0.5, 0.9])),
                  g.away: (np.array([], np.int64), np.array([]))}, g.home, WC)
    assert s is None                     # only post trade is after t; last at/before t is WC - 1 s, > 30 s before t


def test_entry_never_before_t_plus_1s():
    g = game()
    rows = base_rows(g) + [(60.0, g.away, 0.30), (60.999, g.away, 0.31)]
    f = run(g, rows)
    f = f[f.leg == "fade"].iloc[0]
    assert f.entry_ts >= WC + 61 * NS
    assert f.entry_trade == pytest.approx(0.41)


def test_exit_never_before_t_plus_180s():
    g = game()
    rows = base_rows(g) + [(239.9, g.away, 0.80)]
    f = run(g, rows)
    f = f[f.leg == "fade"].iloc[0]
    assert f.exit_ts >= WC + 240 * NS and f.exit_trade == pytest.approx(0.45)


def test_exit_at_settlement_when_no_exit_trade():
    g = game(result=0.0)                                  # away wins
    rows = [x for x in base_rows(g) if x[0] != 245]
    f = run(g, rows)
    f = f[f.leg == "fade"].iloc[0]
    assert bool(f.exit_settle) and f.exit == 1.0
    assert f.fee_direct == pytest.approx(float(I.fee_direct(I.D(0.42))))   # no exit fee at settlement


def test_orientation_swap_mirrors():
    g = game()
    a = run(g, base_rows(g))
    # same market data, ESPN labels swapped: ESPN 'away' scored, orientation 'swapped' -> same Kalshi scorer
    ev2 = [{**EV[0], "side": "away"}]
    b = run(g, base_rows(g), ev=ev2, orientation="swapped")
    cols = ["leg", "team", "m", "entry", "exit", "pnl_direct"]
    pd.testing.assert_frame_equal(a[cols].reset_index(drop=True), b[cols].reset_index(drop=True))
    # swapping Kalshi home/away codes (with prices stored as P(new home)) gives the mirrored trade
    g2 = game(result=0.0, home="AWY", away="HOM")
    c = run(g2, base_rows(game()), ev=[{**EV[0], "side": "away"}], orientation="same")
    fa, fc = a[a.leg == "fade"].iloc[0], c[c.leg == "fade"].iloc[0]
    assert fc.team == "AWY" and fc.pnl_direct == pytest.approx(fa.pnl_direct)


def test_below_threshold_no_trade_and_one_position():
    g = game()
    assert run(g, base_rows(g), ss=(0.11,)).empty
    ev = EV + [{"wc_ns": WC + 100 * NS, "side": "home", "ptype": "field-goal", "order": 2}]   # during open position
    r = run(g, base_rows(g), ev=ev)
    assert (r.leg == "fade").sum() == 1


@pytest.mark.parametrize("p,fee", [(0.3, 0.15), (0.5, 0.18), (0.8, 0.12), (0.95, 0.04), (0.99, 0.01)])
def test_fee_function(p, fee):
    # 0.07 x 10 x P x (1 - P), rounded up to the cent
    assert float(I.fee_direct(I.D(p))) == pytest.approx(fee)
    assert float(I.fee_webull(I.D(p))) == pytest.approx(0.20)


def test_holdout_refused():
    g = A.Game(game_id="h", league="CFB", home="HOM", away="AWY", event="EV",
               kickoff=pd.Timestamp("2026-09-05", tz="UTC"), kickoff_source="espn", result=1.0)
    with pytest.raises(ValueError):
        I.exclusion(ticks(base_rows(game()), g), g, final_test=False)


def test_scoring_events_side_and_wallclock():
    s = {"drives": {"previous": [{"plays": [
        {"homeScore": 0, "awayScore": 0, "text": "kick"},
        {"homeScore": 7, "awayScore": 0, "scoringPlay": True, "scoringType": {"name": "touchdown"},
         "wallclock": "2025-10-04T21:00:00Z"},
        {"homeScore": 7, "awayScore": 3, "scoringPlay": True, "scoringType": {"name": "field-goal"}},
        {"homeScore": 9, "awayScore": 3, "scoringPlay": True, "scoringType": {"name": "safety"},
         "wallclock": "2025-10-04T21:30:00Z"}]}]}}
    ev, sk = I.scoring_events(s)
    assert [e["side"] for e in ev] == ["home", "home"] and sk["no wallclock"] == 1
