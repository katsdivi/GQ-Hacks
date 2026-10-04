"""scripts/posthoc_tns.py on SYNTHETIC T&S prints and synthetic Kalshi books only (no real data)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import costs  # noqa: E402
import laggard as L  # noqa: E402
import posthoc_tns as P  # noqa: E402

NS = P.NS
T0 = int(pd.Timestamp("2026-10-03 14:00", tz="UTC").value)      # 10:00 ET, after the PM US fee start
END = T0 + 3600 * NS                                              # synthetic coverage end


def sig(entry_g, exit_g, direction=1, reason="gap_closed"):
    return pd.DataFrame([{"entry_g": entry_g, "exit_g": exit_g, "direction": direction, "qty": 10,
                          "exit_reason": reason, "entry_decision_ns": (entry_g + 1) * NS,
                          "exit_decision_ns": (exit_g + 1) * NS, "gap_at_entry_cents": 5.0}])


def run1(prints, s, lat=1.0, end=END):
    ts = np.array([p[0] for p in prints], dtype="int64")
    px = np.array([p[1] for p in prints], float)
    return P.simulate(s, ts, px, lat, cover_end_ns=end).iloc[0]


G = T0 // NS + 100          # entry label; decision at T0 + 101 s


def test_trade_before_entry_time_not_used_even_if_closest():
    # decision T0+101 s, L = 1 s -> entry time T0+102 s. Print 1 ns before it (closest) must be ignored.
    prints = [(T0 + 102 * NS - 1, 0.40), (T0 + 110 * NS, 0.45), (T0 + 130 * NS, 0.60)]
    r = run1(prints, sig(G, G + 20))
    assert r.status == "filled"
    assert r.entry_trade_ns == T0 + 110 * NS and r.entry_trade_price == 0.45


def test_first_trade_at_or_after_entry_time_used():
    prints = [(T0 + 102 * NS, 0.50), (T0 + 102 * NS, 0.52), (T0 + 103 * NS, 0.55), (T0 + 130 * NS, 0.60)]
    r = run1(prints, sig(G, G + 20))
    assert r.entry_trade_ns == T0 + 102 * NS and r.entry_trade_price == 0.50   # first in file order at equal ns
    assert r.entry_time_ns == T0 + 102 * NS and r.decision_ns == T0 + 101 * NS


def test_plus_minus_one_cent_and_cap():
    assert P.fill_price(0.50, True) == 0.51 and P.fill_price(0.50, False) == 0.49
    assert P.fill_price(0.985, True) == 0.99 and P.fill_price(0.995, True) == 0.99
    assert P.fill_price(0.015, False) == 0.01 and P.fill_price(0.005, False) == 0.01
    # long: buy at entry +1 c, sell at exit -1 c
    r = run1([(T0 + 102 * NS, 0.50), (T0 + 122 * NS, 0.60)], sig(G, G + 20, 1))
    assert (r.entry_fill, r.exit_fill) == (0.51, 0.59)
    # short: sell at entry -1 c, buy at exit +1 c
    r = run1([(T0 + 102 * NS, 0.60), (T0 + 122 * NS, 0.50)], sig(G, G + 20, -1))
    assert (r.entry_fill, r.exit_fill) == (0.59, 0.51)
    # exact P&L, long: (0.59 - 0.51) * 10 - fee(0.51) - fee(0.59)
    r = run1([(T0 + 102 * NS, 0.50), (T0 + 122 * NS, 0.60)], sig(G, G + 20, 1))
    # 0.0695*10*0.51*0.49 = 0.1736805 -> 0.17; 0.0695*10*0.59*0.41 = 0.1681205 -> 0.17
    assert (r.fee_entry, r.fee_exit) == (0.17, 0.17)
    assert r.pnl_usd == pytest.approx(0.8 - 0.34) and r.net_c_per_contract == pytest.approx(4.6)


def test_no_trade_within_60s_skips_with_reason():
    # entry time T0+102 s; next print at T0+162 s + 1 ns (> 60 s) -> skip
    r = run1([(T0 + 50 * NS, 0.5), (T0 + 162 * NS + 1, 0.5), (T0 + 400 * NS, 0.5)], sig(G, G + 20))
    assert r.status == P.SKIP_ENTRY
    # exactly 60 s later is inside (inclusive)
    r = run1([(T0 + 162 * NS, 0.5), (T0 + 200 * NS, 0.5)], sig(G, G + 20))
    assert r.status == "filled"
    # exit side: exit time T0+121 s, no print in [121, 181] s
    r = run1([(T0 + 102 * NS, 0.5), (T0 + 182 * NS, 0.5)], sig(G, G + 20))
    assert r.status == P.SKIP_EXIT
    # window reaching the coverage end without a print -> outside coverage, not a skip
    r = run1([(T0 + 102 * NS, 0.5)], sig(G, G + 20), end=T0 + 150 * NS)
    assert r.status == P.OUTSIDE
    r = run1([(T0 + 102 * NS, 0.5)], sig(G, G + 20), end=T0 + 101 * NS)    # decision at the end
    assert r.status == P.OUTSIDE


def test_exit_uses_first_trade_at_or_after_exit_time_without_latency():
    # exit decision at T0+121 s; print 1 ns earlier is ignored; first at/after is used (no L added to exit)
    prints = [(T0 + 102 * NS, 0.50), (T0 + 121 * NS - 1, 0.70), (T0 + 121 * NS, 0.58), (T0 + 125 * NS, 0.65)]
    r = run1(prints, sig(G, G + 20), lat=5.0)
    assert r.exit_time_ns == T0 + 121 * NS
    assert r.exit_trade_ns == T0 + 121 * NS and r.exit_trade_price == 0.58 and r.exit_fill == 0.57
    assert r.entry_trade_ns == T0 + 121 * NS - 1          # L = 5 s: entry time 106 s, first print at/after


def test_fee_polymarket_us_bankers_rounding():
    # 0.0695 * 10 * 0.5 * 0.5 = 0.17375 -> 0.17; 0.0695*10*0.1*0.9 = 0.06255 -> 0.06
    assert costs.fee(0.5, 10, "buy", "polymarket_us", ts=T0) == 0.17
    assert costs.fee(0.1, 10, "sell", "polymarket_us", ts=T0) == 0.06
    # exact tie: 0.0695 * 120 * 0.25 = 2.085 -> 2.08 under half to even (half up would give 2.09)
    assert costs.fee(0.5, 120, "buy", "polymarket_us", ts=T0) == 2.08
    # exact tie with odd cent digit: 0.0695 * 200 * 0.25 = 3.475 -> 3.48
    assert costs.fee(0.5, 200, "buy", "polymarket_us", ts=T0) == 3.48
    with pytest.raises(ValueError):
        costs.fee(0.5, 10, "buy", "polymarket_us", ts=int(pd.Timestamp("2026-10-01 13:00", tz="UTC").value))


def test_price_series_backward_only():
    ts = np.array([T0 + 10 * NS, T0 + 20 * NS, T0 + 20 * NS, T0 + 30 * NS], dtype="int64")
    px = np.array([0.40, 0.45, 0.47, 0.60])
    assert np.isnan(P.price_at(ts, px, T0 + 10 * NS - 1))
    assert P.price_at(ts, px, T0 + 10 * NS) == 0.40
    assert P.price_at(ts, px, T0 + 20 * NS) == 0.47        # last in file order at equal ns
    assert P.price_at(ts, px, T0 + 30 * NS - 1) == 0.47     # the later print is not used
    # the grid the signal sees: label g = last print before (g + 1) s
    syn = P.synthetic_ticks(ts, px, "S")
    g = L._grid(syn, "polymarket_us", T0 // NS, T0 // NS + 40, [])
    assert g.loc[T0 // NS + 19] == 0.40 and g.loc[T0 // NS + 20] == 0.47 and g.loc[T0 // NS + 29] == 0.47
    assert g.loc[T0 // NS + 30] == 0.60 and np.isnan(g.loc[T0 // NS + 9])


def test_parse_venue_time_exact_ns():
    s = pd.Series(["2026-10-03T12:00:00.123456789-04:00", "2026-10-03T12:00:00.1234567-04:00",
                   "2026-10-03T12:00:00.893-04:00", "2026-10-02T23:59:59-04:00"])
    v = P.parse_venue_time(s)
    base = int(pd.Timestamp("2026-10-03 16:00", tz="UTC").value)
    assert v[0] == base + 123456789 and v[1] == base + 123456700 and v[2] == base + 893000000
    assert v[3] == int(pd.Timestamp("2026-10-03 03:59:59", tz="UTC").value)
    with pytest.raises(ValueError):
        P.parse_venue_time(pd.Series(["2026-10-03T12:00:00.1-05:00"]))


def test_home_orientation():
    assert list(P.home_price(np.array([0.665, 0.085]), True)) == [0.335, 0.915]
    assert list(P.home_price(np.array([0.665]), False)) == [0.665]


def test_end_to_end_signal_from_synthetic_books():
    # Kalshi mid 0.50 -> 0.56 at second 100 (bid/ask +/- 1 c); follower T&S prints at 0.50 every 5 s until it
    # prints 0.56 at second 108. Jump at label 100: gap 6 c >= 3 c -> long. Gap closes at label 108 -> exit
    # decision at 109 s.
    W = 300
    k = []
    for s_, m in ((0, 0.50), (100, 0.56)):
        for kind, px in (("bid", m - 0.01), ("ask", m + 0.01)):
            k.append({"ts": T0 + s_ * NS + 200_000_000, "venue": "kalshi", "market_id": "K", "kind": kind,
                      "price": round(px, 4)})
    k = pd.DataFrame(k)
    pts = [(T0 + s_ * NS + 300_000_000, 0.50) for s_ in range(0, 105, 5)] + \
          [(T0 + 108 * NS + 500_000_000, 0.56), (T0 + 115 * NS, 0.56)]
    ts = np.array([p[0] for p in pts], dtype="int64")
    px = np.array([p[1] for p in pts])
    sg = L.signals(k, P.synthetic_ticks(ts, px, "S"), "polymarket_us", T0, T0 + W * NS)
    assert len(sg) == 1
    r = sg.iloc[0]
    assert r.entry_g == T0 // NS + 100 and r.direction == 1 and r.exit_g == T0 // NS + 108
    t = P.simulate(sg, ts, px, 1.0, cover_end_ns=END).iloc[0]
    # entry time 102 s -> last 0.50 print was at 100.3 s, so the first print at/after is 108.5 s at 0.56 -> buy 0.57;
    # exit time 109 s -> 115 s at 0.56 -> sell 0.55
    assert t.entry_trade_ns == T0 + 108 * NS + 500_000_000 and t.entry_fill == 0.57
    assert t.exit_trade_ns == T0 + 115 * NS and t.exit_fill == 0.55
