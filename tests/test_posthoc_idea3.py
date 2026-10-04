"""Synthetic-book tests for scripts/posthoc_idea3.py (IDEA 3, POST-HOC, EXPLORATORY)."""
import numpy as np
import pandas as pd
import pytest

import costs
import posthoc_idea3 as P

NS, MS = P.NS, P.MS
S = 1_000_000 * NS      # base time (far from kickoff)
KO = S + 10_000 * NS    # kickoff well after everything below
LO, HI = S, S + 5_000 * NS
LAT = 30 * MS           # book receipt delay


def book_rows(snaps):
    """snaps: (venue_t_s, bid, bsz, ask, asz); receipt = venue + 30 ms. Stored P(home) terms."""
    out = []
    for t, b, bs, a, az in snaps:
        src = S + int(round(t * NS))
        for kind, px, sz in (("bid", b, bs), ("ask", a, az)):
            if px == px:
                out.append(dict(ts=src + LAT, kind=kind, price=px, size=sz, side=kind == "bid" and "buy" or "sell",
                                src_ts_ns=src, recv_ns=src + LAT))
    return pd.DataFrame(out)


def trade_rows(prints):
    """prints: (venue_t_s, size, side, recv_lag_s)."""
    return pd.DataFrame([dict(ts=S + int(round(t * NS)), kind="trade", price=0.5, size=sz, side=sd,
                              src_ts_ns=pd.NA, recv_ns=S + int(round((t + lag) * NS))) for t, sz, sd, lag in prints])


def small_prints(n=40):
    return [(1 + i * 0.5, 1.0, "buy", 1.0) for i in range(n)]


def base_book():
    # mid 0.50 before the print at t=100, mid 0.53 after (buy print pushes it up)
    return [(0, 0.49, 50, 0.51, 50), (99.9, 0.49, 50, 0.51, 50), (100.0005, 0.52, 50, 0.54, 50)]


def run_signals(book, prints):
    sn, _ = P.book_snapshots(book_rows(book))
    c = {}
    return P.find_signals(P.dedupe_trades(trade_rows(prints)), sn, LO, HI, KO, "M", c), sn, c


def test_signal_found_and_direction():
    sig, _, _ = run_signals(base_book(), small_prints() + [(100.0007, 100.0, "buy", 1.0)])
    assert len(sig) == 1 and sig[0]["d"] == 1 and sig[0]["move"] == pytest.approx(0.03)


def test_ms_tie_book_delta_in_print_millisecond_counts_as_after():
    # book delta at venue 100.000 s (truncated ms), print at 100.0007 s: same ms -> "after"
    book = [(0, 0.49, 50, 0.51, 50), (100.000, 0.52, 50, 0.54, 50)]
    sig, _, _ = run_signals(book, small_prints() + [(100.0007, 100.0, "buy", 1.0)])
    assert len(sig) == 1


def test_no_signal_when_post_book_received_after_t():
    # post-print book received 30 ms after venue time; print receipt only 10 ms after trade -> not yet received
    _, _, c0 = run_signals(base_book(), small_prints() + [(100.0007, 100.0, "buy", 1.0)])
    sig, _, c = run_signals(base_book(), small_prints() + [(100.0007, 100.0, "buy", 0.010)])
    # the 40 small (also "big" at a size-1 threshold) prints never have a received post book; the big one now too
    assert sig == [] and c["post_book_not_received"] == c0["post_book_not_received"] + 1


def test_future_books_do_not_change_signal():
    prints = small_prints() + [(100.0007, 100.0, "buy", 1.0)]
    a, _, _ = run_signals(base_book(), prints)
    later = base_book() + [(100.5, 0.10, 5, 0.90, 5), (101.5, 0.80, 5, 0.82, 5), (300, 0.2, 1, 0.3, 1)]
    b, _, _ = run_signals(later, prints)
    assert a == b


def test_move_below_2c_or_wrong_direction_no_signal():
    book = [(0, 0.49, 50, 0.51, 50), (100.0005, 0.50, 50, 0.52, 50)]   # +1 c only
    sig, _, _ = run_signals(book, small_prints() + [(100.0007, 100.0, "buy", 1.0)])
    assert sig == []
    sig, _, _ = run_signals(base_book(), small_prints() + [(100.0007, 100.0, "sell", 1.0)])  # mid up, sell print
    assert sig == []


def test_threshold_is_95th_pct_of_window():
    prints = small_prints() + [(100.0007, 1.0, "buy", 1.0)]   # all size 1 -> threshold 1 -> every print is big
    sn, _ = P.book_snapshots(book_rows(base_book()))
    c = {}
    P.find_signals(P.dedupe_trades(trade_rows(prints)), sn, LO, HI, KO, "M", c)
    assert c["big_prints"] == len(prints)


def test_fill_uses_no_quote_before_t_plus_L_and_exit_crosses_spread():
    book = base_book() + [
        (100.9, 0.60, 50, 0.62, 50),        # received 100.93 < t + L = 101.0007 + 0.25: must NOT be used
        (101.3, 0.55, 4, 0.57, 50),         # received 101.33 >= 101.2507: fill here, sell at bid 0.55, qty 4
        (111.0, 0.50, 50, 0.52, 50),        # received 111.03 < fill + 10 s = 111.33
        (111.4, 0.48, 50, 0.51, 50),        # received 111.43: exit, buy back at ASK 0.51
    ]
    prints = small_prints() + [(100.0007, 100.0, "buy", 1.0)]
    sig, sn, _ = run_signals(book, prints)
    t = sig[0]["t"]
    c = {}
    tr = P.simulate(sig, {"M": sn}, 0.25, KO, HI, c)
    assert len(tr) == 1
    x = tr[0]
    assert x["fill_recv"] >= t + int(0.25 * NS)
    assert x["side"] == "short_home" and x["entry"] == pytest.approx(0.55) and x["qty"] == 4
    assert x["exit_recv"] >= x["fill_recv"] + 10 * NS
    assert x["exit"] == pytest.approx(0.51)
    assert x["gross_c"] == pytest.approx(4.0)
    fe = costs.fee(0.55, 4, "buy", "kalshi", route="direct") * 100 / 4
    fx = costs.fee(0.51, 4, "buy", "kalshi", route="direct") * 100 / 4
    assert x["net_c"] == pytest.approx(4.0 - fe - fx)


def test_long_fade_exits_at_bid():
    book = [(0, 0.51, 50, 0.53, 50), (100.0005, 0.47, 50, 0.49, 50),
            (101.5, 0.47, 50, 0.49, 50), (112, 0.46, 50, 0.50, 50)]
    sig, sn, _ = run_signals(book, small_prints() + [(100.0007, 100.0, "sell", 1.0)])
    tr = P.simulate(sig, {"M": sn}, 0.5, KO, HI, {})
    assert tr[0]["side"] == "long_home" and tr[0]["entry"] == pytest.approx(0.49)
    assert tr[0]["exit"] == pytest.approx(0.46) and tr[0]["gross_c"] == pytest.approx(-3.0)


def test_fees_kalshi_direct_rounded_up_per_order():
    # 0.07 x 10 x 0.5 x 0.5 = 0.175 -> 0.18 dollars -> 1.8 c/contract
    assert P.fee_c(0.5, 10) == pytest.approx(1.8)
    # 0.07 x 10 x 0.1 x 0.9 = 0.063 -> 0.07 -> 0.7 c/contract
    assert P.fee_c(0.1, 10) == pytest.approx(0.7)


def test_one_position_at_a_time():
    book = base_book() + [(101.5, 0.52, 50, 0.54, 50), (112, 0.52, 50, 0.54, 50), (200, 0.52, 50, 0.54, 50)]
    sig, sn, _ = run_signals(book, small_prints() + [(100.0007, 100.0, "buy", 1.0)])
    s2 = dict(sig[0], t=sig[0]["t"] + 2 * NS)
    c = {}
    tr = P.simulate(sig + [s2], {"M": sn}, 0.25, KO, HI, c)
    assert len(tr) == 1 and c["busy"] == 1


def test_kickoff_cut_excludes_prints():
    ko = S + 100 * NS
    sn, _ = P.book_snapshots(book_rows(base_book()))
    c = {}
    sig = P.find_signals(P.dedupe_trades(trade_rows(small_prints() + [(100.0007, 100.0, "buy", 1.0)])),
                         sn, LO, HI, ko, "M", c)
    assert sig == []
