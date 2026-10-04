"""Synthetic-book tests for scripts/posthoc_idea1.py (IDEA 1, POST-HOC, EXPLORATORY)."""
import numpy as np
import pandas as pd
import pytest

import costs
import posthoc_idea1 as P

NS = P.NS
S = 1_000 * NS          # base time


def book(rows, away=False):
    """rows: (t_s, bid, bsz, ask, asz) in OWN terms; stored in P(home) terms like the collector does."""
    out = []
    for t, b, bs, a, az in rows:
        if away:
            hb, ha, hbs, has = 1 - a, 1 - b, az, bs
        else:
            hb, ha, hbs, has = b, a, bs, az
        out += [dict(recv_ns=S + int(t * NS), kind="bid", price=round(hb, 4), size=hbs),
                dict(recv_ns=S + int(t * NS), kind="ask", price=round(ha, 4), size=has)]
    return P.snapshots(pd.DataFrame(out), away=away)


def test_deflip_away_market():
    a = book([(0, 0.40, 7, 0.42, 9)], away=True)
    assert a["bid"].iat[0] == pytest.approx(0.40) and a["bsz"].iat[0] == 7
    assert a["ask"].iat[0] == pytest.approx(0.42) and a["asz"].iat[0] == 9


def test_fee_rounding_up_to_cent_matches_costs():
    for p in np.round(np.arange(0.01, 1.0, 0.01), 2):
        exp = costs.fee(p, 10, "buy", "kalshi", route="direct")
        assert P.fee_units_10(P.p4([p]), "direct")[0] == round(exp * 10000)
    # 0.07 * 10 * 0.5 * 0.5 = 0.175 -> 0.18 ; 0.07*10*0.1*0.9 = 0.063 -> 0.07
    assert costs.fee(0.5, 10, "buy", "kalshi", route="direct") == 0.18
    assert costs.fee(0.1, 10, "buy", "kalshi", route="direct") == 0.07
    assert P.order_fee(0.1, 3.5, "direct") == 0.03     # 0.07*3.5*0.09 = 0.02205 -> 0.03
    assert P.order_fee(0.4, 10, "webull") == pytest.approx(0.2)


def test_clear_threshold_strict():
    # 0.45 + 0.50: 10*0.95 = 9.50 + fees 0.18 + 0.18 = 9.86 < 10 -> clears (direct)
    assert P.clears(P.p4([0.45]), P.p4([0.50]), "direct")[0]
    # 0.48 + 0.50: 9.80 + 0.18 + 0.18 = 10.16 -> no
    assert not P.clears(P.p4([0.48]), P.p4([0.50]), "direct")[0]
    # webull: 9.60 + 0.40 = 10.00 not < 10
    assert not P.clears(P.p4([0.46]), P.p4([0.50]), "webull")[0]
    assert P.clears(P.p4([0.45]), P.p4([0.50]), "webull")[0]


def test_signal_uses_no_data_after_t():
    h = book([(0, 0.50, 50, 0.52, 50), (10, 0.44, 50, 0.45, 50)])
    a = book([(0, 0.47, 50, 0.49, 50), (5, 0.48, 50, 0.50, 50)])
    sig = P.signal_table(h, a, S, S + 100 * NS, ko_ns=-10**15, schedule="direct")
    # at t=5 the home book is still the t=0 one (0.52 + 0.50 does not clear) even though a clearing
    # home quote arrives at t=10
    r5 = sig[sig.t == S + 5 * NS].iloc[0]
    assert not r5.yes
    r10 = sig[sig.t == S + 10 * NS].iloc[0]
    assert r10.yes


def test_fill_never_uses_quote_before_t_plus_L():
    h = book([(0, 0.40, 50, 0.45, 50), (0.3, 0.40, 50, 0.44, 4), (0.6, 0.40, 50, 0.46, 6)])
    a = book([(0, 0.48, 50, 0.50, 50), (0.4, 0.48, 50, 0.49, 8), (0.8, 0.48, 50, 0.50, 7)])
    at = P.attempt(h, a, S, "yes", 0.5, S + 100 * NS, "direct")
    assert at.fill_h_ns == S + int(0.6 * NS) and at.fill_a_ns == S + int(0.8 * NS)
    assert at.price_h == pytest.approx(0.46) and at.price_a == pytest.approx(0.50)
    assert at.executed and at.q_h == 6 and at.q_a == 7
    # nothing at or after t + L on one leg: missed, no earlier quote used
    a2 = book([(0, 0.48, 50, 0.50, 50), (0.4, 0.48, 50, 0.49, 8)])
    at2 = P.attempt(h, a2, S, "yes", 0.5, S + 100 * NS, "direct")
    assert not at2.executed and at2.reason.startswith("no snapshot")


def test_fill_first_snapshot_at_or_after_and_sizes_with_unwind():
    h = book([(0, 0.40, 50, 0.45, 50), (0.3, 0.40, 50, 0.45, 50), (0.6, 0.40, 50, 0.45, 4),
              (2.0, 0.41, 50, 0.46, 50)])
    a = book([(0, 0.48, 50, 0.50, 50), (0.7, 0.48, 50, 0.50, 25)])
    at = P.attempt(h, a, S, "yes", 0.5, S + 100 * NS, "direct")
    assert at.executed
    assert at.fill_h_ns == S + int(0.6 * NS) and at.fill_a_ns == S + int(0.7 * NS)
    assert at.q_h == 4 and at.q_a == 10 and at.q == 4          # min(10, displayed) at t+L, per leg
    assert at.excess_leg == "away" and at.excess == 6
    assert at.unwind_price is not None and np.isnan(at.unwind_price)   # no later away quote
    # excess held to settlement in that case; with a later away quote it is sold at own bid
    a2 = book([(0, 0.48, 50, 0.50, 50), (0.7, 0.48, 50, 0.50, 25), (1.5, 0.47, 50, 0.50, 25)])
    at2 = P.attempt(h, a2, S, "yes", 0.5, S + 100 * NS, "direct")
    assert at2.unwind_price == pytest.approx(0.47) and at2.unwind_ns == S + int(1.5 * NS)
    pnl = P.position_pnl(at2, 1.0, 0.0, "direct")
    exp = 4 * 1.0 - (4 * 0.45 + costs.fee(0.45, 4, "buy", "kalshi", route="direct")) \
        - (10 * 0.50 + costs.fee(0.50, 10, "buy", "kalshi", route="direct")) \
        + 6 * 0.47 - costs.fee(0.47, 6, "sell", "kalshi", route="direct")
    assert pnl == pytest.approx(exp)


def test_missed_when_sum_stops_clearing():
    h = book([(0, 0.40, 50, 0.45, 50), (0.4, 0.44, 50, 0.49, 50)])
    a = book([(0, 0.48, 50, 0.50, 50), (0.6, 0.48, 50, 0.50, 50)])
    at = P.attempt(h, a, S, "yes", 0.25, S + 100 * NS, "direct")
    assert not at.executed and at.reason == "sum no longer clears at t+L"


def test_no_direction_and_tie_payout():
    # NO: (1 - 0.55) + (1 - 0.50) = 0.95 -> clears
    h = book([(0, 0.55, 30, 0.57, 30), (1, 0.55, 30, 0.57, 30)])
    a = book([(0, 0.50, 30, 0.52, 30), (1, 0.50, 30, 0.52, 30)])
    at = P.attempt(h, a, S, "no", 0.5, S + 100 * NS, "webull")
    assert at.executed and at.price_h == pytest.approx(0.45) and at.price_a == pytest.approx(0.50)
    assert at.q == 10 and at.excess == 0
    assert P.position_pnl(at, 0.5, 0.5, "webull") == pytest.approx(10 - 4.5 - 5.0 - 0.4)


def test_one_position_per_game_and_kickoff_cut():
    h = book([(0, 0.40, 50, 0.45, 50), (0.3, 0.40, 50, 0.45, 40), (1, 0.40, 50, 0.52, 50),
              (2, 0.40, 50, 0.45, 50), (2.3, 0.40, 50, 0.45, 40), (3, 0.40, 50, 0.52, 50),
              (4, 0.40, 50, 0.45, 50), (4.3, 0.40, 50, 0.45, 40), (5, 0.40, 50, 0.52, 50)])
    a = book([(0, 0.48, 50, 0.50, 50), (0.3, 0.48, 50, 0.50, 49)])
    rr, ats = P.simulate_game(h, a, S, S + 100 * NS, ko_ns=-10**15, L=0.25, schedule="direct")
    assert (rr["dir"] == "yes").sum() == 3
    assert len(ats) == 1 and ats[0].executed
    # kickoff cut covering everything: no runs
    rr2, ats2 = P.simulate_game(h, a, S, S + 100 * NS, ko_ns=S + 60 * NS, L=0.25, schedule="direct")
    assert len(rr2) == 0 and ats2 == []
