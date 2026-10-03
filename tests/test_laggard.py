"""laggard.py on synthetic books only. Kalshi mid steps 0.50 -> 0.56 at second 100; the follower copies it
at second 108 (8 s late). Books: bid = mid - 1c, ask = mid + 1c, a snapshot whenever the mid changes,
received 0.2 s into the second. Hand-derived expectations in the comments."""
import numpy as np
import pandas as pd
import pytest

import costs
import laggard as L

NS = 1_000_000_000
T0 = int(pd.Timestamp("2026-10-03 18:00", tz="UTC").value)      # synthetic, dated after the PM US fee start
KO = pd.Timestamp("2026-10-03 18:30", tz="UTC")
W = 300


def books(path, venue, market, extra=()):
    rows, prev = [], None
    for s, m in enumerate(path):
        if m == prev:
            continue
        prev = m
        for k, px in (("bid", m - 0.01), ("ask", m + 0.01)):
            rows.append({"ts": T0 + s * NS + 200_000_000, "venue": venue, "market_id": market, "kind": k,
                         "price": round(px, 4)})
    rows += [dict(r, venue=venue, market_id=market) for r in extra]
    return pd.DataFrame(rows).sort_values("ts", kind="stable").reset_index(drop=True)


def step(at, lo=0.50, hi=0.56):
    return np.where(np.arange(W) >= at, hi, lo).round(2)


def run(k_at=100, o_at=108, venue="polymarket", extra=(), exclude=(), latencies=(0.0, 5.0)):
    k = books(step(k_at), "kalshi", "K")
    o = books(step(o_at), venue, "P", extra)
    return L.evaluate_game("syn", KO, k, o, venue, T0, T0 + W * NS, exclude=exclude, latencies=latencies,
                           holdout_run=True)


def test_signal_and_exact_pnl_at_3s():
    t = run()
    r = t[t.latency_s == 3.0].iloc[0]
    assert r.direction == 1 and r.exit_reason == "gap_closed"
    # jump at label 100 -> decision at 101 s; fill at 101 + 3 s = 104 s: follower ask still 0.51
    assert r.entry_fill_ns == T0 + 104 * NS and r.entry_px == pytest.approx(0.51)
    # gap closes at label 108 -> exit decision 109 s, fill at 112 s: follower bid 0.55
    assert r.exit_fill_ns == T0 + 112 * NS and r.exit_px == pytest.approx(0.55)
    # fees, polymarket.com, 5 decimals: 0.05*10*0.51*0.49 = 0.12495, 0.05*10*0.55*0.45 = 0.12375
    assert (r.fee_entry, r.fee_exit) == (0.12495, 0.12375)
    assert r.pnl_cents == pytest.approx((0.04 * 10 - 0.12495 - 0.12375) * 100)       # 15.13
    assert r.edge_cents_per_contract == pytest.approx(1.513)


def test_latency_curve_starts_at_3s_and_edge_dies_after_follower_moves():
    t = run(latencies=L.LATENCIES_S)
    c = L.latency_curve(t)
    assert c.latency_s.tolist() == [3.0, 3.25, 3.5, 4.0, 5.0, 8.0, 13.0]
    e = c.set_index("latency_s")["edge_cents_mean"]
    assert e[3.0] > 0
    # 3 + 5 s: entry fill at 109 s, after the follower moved (108.2 s): buys at 0.57, sells at 0.55
    r = t[t.latency_s == 8.0].iloc[0]
    assert r.entry_px == pytest.approx(0.57) and r.exit_px == pytest.approx(0.55)
    assert e[8.0] < 0 and e[13.0] < 0
    assert (c.n_trades == 1).all() and c.edge_ci_low.isna().all()                     # one trade: no CI


def test_polymarket_us_has_no_delay_and_cent_fees():
    t = run(venue="polymarket_us", latencies=(0.0,))
    r = t.iloc[0]
    assert r.latency_s == 0.0 and r.entry_fill_ns == T0 + 101 * NS
    assert r.fee_entry == costs.fee(0.51, 10, "buy", "polymarket_us", ts=T0) == 0.17   # raw 0.1736805


def test_fill_uses_quote_at_exactly_fill_time_never_after():
    fill = T0 + 104 * NS
    at = [{"ts": fill, "kind": "bid", "price": 0.51}, {"ts": fill, "kind": "ask", "price": 0.53}]
    after = [{"ts": fill + 1, "kind": "bid", "price": 0.51}, {"ts": fill + 1, "kind": "ask", "price": 0.53}]
    assert run(extra=at, latencies=(0.0,)).iloc[0].entry_px == pytest.approx(0.53)     # ts == fill: used
    assert run(extra=after, latencies=(0.0,)).iloc[0].entry_px == pytest.approx(0.51)  # 1 ns later: not used


def test_empty_side_at_fill_skips_instead_of_carrying_old_ask():
    one_sided = [{"ts": T0 + 103 * NS + 500_000_000, "kind": "bid", "price": 0.49}]   # ask side empty
    r = run(extra=one_sided, latencies=(0.0,)).iloc[0]
    assert not r.filled and r.skip == "no quote at entry"
    c = L.latency_curve(run(extra=one_sided, latencies=(0.0,)))
    assert c.n_trades.item() == 0 and c.n_skipped_no_quote.item() == 1


def test_no_trade_when_follower_leads_kalshi():
    # placebo direction: the follower moves first (second 92), Kalshi at 100 -> no gap at the Kalshi jump
    t = run(k_at=100, o_at=92)
    assert t.empty or not t["filled"].any()


def test_excluded_interval_blocks_entries():
    t = run(exclude=[(T0 // NS + 95, T0 // NS + 130)])
    assert len(run())                                                  # same game without it trades
    assert t.empty or not t["filled"].any()


def test_sealed_game_needs_holdout_flag_and_unknown_venue_raises():
    k, o = books(step(100), "kalshi", "K"), books(step(108), "polymarket", "P")
    with pytest.raises(ValueError):
        L.evaluate_game("syn", KO, k, o, "polymarket", T0, T0 + W * NS)
    with pytest.raises(ValueError):
        L.evaluate_game("syn", KO, k, o, "kalshi", T0, T0 + W * NS, holdout_run=True)


def test_no_lookahead_future_rows_do_not_change_past_decisions():
    """Truncating the data after the exit fill must not change the trade."""
    full = run(latencies=(0.0,)).iloc[0]
    k = books(step(100), "kalshi", "K")
    o = books(step(108), "polymarket", "P")
    cut = T0 + 112 * NS
    t = L.evaluate_game("syn", KO, k[k.ts <= cut], o[o.ts <= cut], "polymarket", T0, T0 + W * NS,
                        latencies=(0.0,), holdout_run=True).iloc[0]
    assert (t.entry_fill_ns, t.exit_fill_ns, t.entry_px, t.exit_px) == \
        (full.entry_fill_ns, full.exit_fill_ns, full.entry_px, full.exit_px)


# --- v2 Amendment 3: per-market delay, no carry across breaks or the window end, capacity ---------------

def test_per_market_delay_from_file_and_missing_counted(tmp_path):
    f = tmp_path / "d.csv"
    f.write_text("market_id,seconds_delay,fetched_at_utc\nC1,1,x\nC2,,x\n")
    delays = L.load_seconds_delay(f)
    assert delays == {"C1": 1}
    k, o = books(step(100), "kalshi", "K"), books(step(108), "polymarket", "P")
    t = L.evaluate_game("syn", KO, k, o, "polymarket", T0, T0 + W * NS, latencies=(0.0, 0.25), holdout_run=True,
                        condition="C1", delays=delays)
    assert t.latency_s.tolist() == [1.0, 1.25] and (t.delay_source == "seconds_delay file").all()
    assert t.iloc[0].entry_fill_ns == T0 + 102 * NS                       # decision 101 s + 1 s
    for cond in ("C2", None):                                              # blank in file, or not in it
        m = L.evaluate_game("syn", KO, k, o, "polymarket", T0, T0 + W * NS, latencies=(0.0,), holdout_run=True,
                            condition=cond, delays=delays)
        assert m.iloc[0].venue_delay_s == 3.0 and m.iloc[0].delay_source == "missing->3"
    us = L.evaluate_game("syn", KO, k, books(step(108), "polymarket_us", "P"), "polymarket_us", T0, T0 + W * NS,
                         latencies=(0.0,), holdout_run=True, condition="C1", delays=delays)
    assert us.iloc[0].venue_delay_s == 0.0


# The follower's only snapshots are at 0.2 s (mid 0.50) and 108.2 s (0.56). Without a break its 0.50 mid is
# carried to second 107 and the Kalshi jump at 100 trades (test_signal_and_exact_pnl_at_3s).

def test_mid_not_carried_across_outage():
    o = books(step(108), "polymarket", "P")
    br = L._breaks_g((), [(T0 + 60 * NS, T0 + 65 * NS)])
    assert br == [(T0 // NS + 60, T0 // NS + 64)]
    g = L._grid(o, "polymarket", T0 // NS, T0 // NS + W - 1, br)
    assert g.loc[T0 // NS + 59] == pytest.approx(0.50)                     # before the outage: carried
    assert g.loc[T0 // NS + 60:T0 // NS + 107].isna().all()               # in it and after it: undefined
    assert g.loc[T0 // NS + 108] == pytest.approx(0.56)                    # first snapshot after it
    t = L.evaluate_game("syn", KO, books(step(100), "kalshi", "K"), o, "polymarket", T0, T0 + W * NS,
                        outages=[(T0 + 60 * NS, T0 + 65 * NS)], latencies=(0.0,), holdout_run=True)
    assert t.empty or not t["filled"].any()


def test_mid_not_carried_across_kickoff_cut():
    o = books(step(108), "polymarket", "P")
    cut = (T0 // NS + 60, T0 // NS + 70)                                   # inclusive grid seconds
    g = L._grid(o, "polymarket", T0 // NS, T0 // NS + W - 1, [cut])
    assert g.loc[T0 // NS + 59] == pytest.approx(0.50) and g.loc[T0 // NS + 71:T0 // NS + 107].isna().all()
    assert g.loc[T0 // NS + 108] == pytest.approx(0.56)
    k = books(step(100), "kalshi", "K")
    gk = L._grid(k, "kalshi", T0 // NS, T0 // NS + W - 1, [cut])
    assert gk.loc[T0 // NS + 71:T0 // NS + 99].isna().all()                # Kalshi too: no carry past the cut
    t = run(exclude=[cut], latencies=(0.0,))
    assert t.empty or not t["filled"].any()


def test_mid_not_carried_past_window_end_and_fill_after_end_skipped():
    o = books(step(108), "polymarket", "P")
    hi_g = T0 // NS + 105
    g = L._grid(o, "polymarket", T0 // NS, hi_g, [])
    assert g.index.max() == hi_g                                           # nothing past the window end
    k = books(step(100), "kalshi", "K")
    # window ends at 110 s: entry fills at 104 s, exit decision at the last label (timeout clipped) fills
    # after 110 s -> the round trip is skipped, never filled from the last quote before the end
    t = L.evaluate_game("syn", KO, k, o, "polymarket", T0, T0 + 110 * NS, latencies=(0.0,), holdout_run=True)
    r = t.iloc[0]
    assert not r.filled and r.skip == "after window end at exit"
    c = L.latency_curve(t)
    assert c.n_skipped_after_end.item() == 1 and c.n_trades.item() == 0


def test_fill_scheduled_across_outage_is_skipped():
    # outage 102.5 to 103.5 s: the signal at label 100 stands (decision 101 s), but the 3 s fill at 104 s
    # would use the 0.2 s snapshot from before the outage -> skipped as "break"
    out = [(T0 + 102_500_000_000, T0 + 103_500_000_000)]
    t = L.evaluate_game("syn", KO, books(step(100), "kalshi", "K"), books(step(108), "polymarket", "P"),
                        "polymarket", T0, T0 + W * NS, outages=out, latencies=(0.0,), holdout_run=True)
    r = t.iloc[0]
    assert r.entry_fill_ns == T0 + 104 * NS and not r.filled and r.skip == "break at entry"
    assert L.latency_curve(t).n_skipped_break.item() == 1
    q = L.book(books(step(108), "polymarket", "P"), "polymarket")
    br = [(a * NS, (b + 1) * NS) for a, b in L._breaks_g((), out)]
    assert L.quote_at(q, T0 + 104 * NS, "ask", br)[2] == "break"
    assert L.quote_at(q, T0 + 109 * NS, "ask", br)[:2][0] == pytest.approx(0.57)  # snapshot after it: fine


def test_capacity_is_best_level_size_at_fill():
    o = books(step(108), "polymarket", "P")
    o["size"] = np.where(o["kind"] == "ask", 25.0, 40.0)
    t = L.evaluate_game("syn", KO, books(step(100), "kalshi", "K"), o, "polymarket", T0, T0 + W * NS,
                        latencies=(0.0,), holdout_run=True)
    r = t.iloc[0]
    assert r.cap_contracts == 25.0 and r.cap_dollars == pytest.approx(25 * 0.51)   # buy at the ask 0.51
    cap = L.capacity(t)
    assert cap.cap_contracts_median.item() == 25.0 and cap.cap_dollars_total.item() == pytest.approx(12.75)
    us = L.evaluate_game("syn", KO, books(step(100), "kalshi", "K"), books(step(108), "polymarket_us", "P"),
                         "polymarket_us", T0, T0 + W * NS, latencies=(0.0,), holdout_run=True)
    assert np.isnan(us.iloc[0].cap_contracts) and np.isnan(L.capacity(us).cap_contracts_total.item())
