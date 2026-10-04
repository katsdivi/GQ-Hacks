"""laggard.py on synthetic books only. Kalshi mid steps 0.50 -> 0.56 at second 100; the follower copies it
at second 108 (8 s late). Books: bid = mid - 1c, ask = mid + 1c, a snapshot whenever the mid changes,
received 0.2 s into the second. Hand-derived expectations in the comments.
polymarket.com delay: per-market seconds_delay (data/live/holdout_seconds_delay.csv: all 112 holdout markets at 1 s,
read 16:22 ET Oct 3), so the synthetic market "P" is given 1 s (D1); the missing -> 3 s fallback is tested
separately."""
import numpy as np
import pandas as pd
import pytest

import costs
import laggard as L

NS = 1_000_000_000
T0 = int(pd.Timestamp("2026-10-03 18:00", tz="UTC").value)      # synthetic, dated after the PM US fee start
KO = pd.Timestamp("2026-10-03 18:30", tz="UTC")
W = 300
D1 = dict(condition="P", delays={"P": 1})          # the holdout value: 1 s for every polymarket.com market


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
                           holdout_run=True, **D1)


def test_signal_and_exact_pnl_at_1s_market_delay():
    t = run()
    r = t[t.latency_s == 1.0].iloc[0]
    assert r.direction == 1 and r.exit_reason == "gap_closed"
    # jump at label 100 -> decision at 101 s; fill at 101 + 1 s = 102 s: follower ask still 0.51
    assert r.entry_fill_ns == T0 + 102 * NS and r.entry_px == pytest.approx(0.51)
    # gap closes at label 108 -> exit decision 109 s, fill at 110 s: follower bid 0.55
    assert r.exit_fill_ns == T0 + 110 * NS and r.exit_px == pytest.approx(0.55)
    # fees, polymarket.com, 5 decimals: 0.05*10*0.51*0.49 = 0.12495, 0.05*10*0.55*0.45 = 0.12375
    assert (r.fee_entry, r.fee_exit) == (0.12495, 0.12375)
    assert r.pnl_cents == pytest.approx((0.04 * 10 - 0.12495 - 0.12375) * 100)       # 15.13
    assert r.edge_cents_per_contract == pytest.approx(1.513)


def test_latency_curve_starts_at_market_delay_and_edge_dies_after_follower_moves():
    t = run(latencies=L.LATENCIES_S)
    c = L.latency_curve(t)
    assert c.latency_s.tolist() == [1.0, 1.25, 1.5, 2.0, 3.0, 6.0, 11.0]
    e = c.set_index("latency_s")["edge_cents_mean"]
    assert e[1.0] > 0 and e[6.0] > 0          # 1 + 5 s: entry fill at 107 s, before the follower moves (108.2 s)
    # 1 + 10 s: entry fill at 112 s, after the follower moved: buys at 0.57, sells at 0.55
    r = t[t.latency_s == 11.0].iloc[0]
    assert r.entry_px == pytest.approx(0.57) and r.exit_px == pytest.approx(0.55)
    assert e[11.0] < 0
    assert (c.n_trades == 1).all() and c.edge_ci_low.isna().all()                     # one trade: no CI


def test_polymarket_us_has_no_delay_and_cent_fees():
    t = run(venue="polymarket_us", latencies=(0.0,))
    r = t.iloc[0]
    assert r.latency_s == 0.0 and r.entry_fill_ns == T0 + 101 * NS
    assert r.fee_entry == costs.fee(0.51, 10, "buy", "polymarket_us", ts=T0) == 0.17   # raw 0.1736805


def test_fill_uses_quote_at_exactly_fill_time_never_after():
    fill = T0 + 102 * NS
    at = [{"ts": fill, "kind": "bid", "price": 0.51}, {"ts": fill, "kind": "ask", "price": 0.53}]
    after = [{"ts": fill + 1, "kind": "bid", "price": 0.51}, {"ts": fill + 1, "kind": "ask", "price": 0.53}]
    assert run(extra=at, latencies=(0.0,)).iloc[0].entry_px == pytest.approx(0.53)     # ts == fill: used
    assert run(extra=after, latencies=(0.0,)).iloc[0].entry_px == pytest.approx(0.51)  # 1 ns later: not used


def test_empty_side_at_fill_skips_instead_of_carrying_old_ask():
    one_sided = [{"ts": T0 + 101 * NS + 500_000_000, "kind": "bid", "price": 0.49}]   # ask side empty
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
                        latencies=(0.0,), holdout_run=True, **D1).iloc[0]
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
                        outages=[(T0 + 60 * NS, T0 + 65 * NS)], latencies=(0.0,), holdout_run=True, **D1)
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
    # window ends at 110 s: entry fills at 102 s; the gap closes at label 108, exit decision 109 s, fill at
    # 110 s = the window end -> the round trip is skipped, never filled from the last quote before the end
    t = L.evaluate_game("syn", KO, k, o, "polymarket", T0, T0 + 110 * NS, latencies=(0.0,), holdout_run=True,
                        **D1)
    r = t.iloc[0]
    assert not r.filled and r.skip == "after window end at exit"
    c = L.latency_curve(t)
    assert c.n_skipped_after_end.item() == 1 and c.n_trades.item() == 0


def test_fill_scheduled_across_outage_is_skipped():
    # outage 101.5 to 101.9 s: the signal at label 100 stands (decision 101 s), but the 1 s fill at 102 s
    # would use the 0.2 s snapshot from before the outage -> skipped as "break"
    out = [(T0 + 101_500_000_000, T0 + 101_900_000_000)]
    t = L.evaluate_game("syn", KO, books(step(100), "kalshi", "K"), books(step(108), "polymarket", "P"),
                        "polymarket", T0, T0 + W * NS, outages=out, latencies=(0.0,), holdout_run=True, **D1)
    r = t.iloc[0]
    assert r.entry_fill_ns == T0 + 102 * NS and not r.filled and r.skip == "break at entry"
    assert L.latency_curve(t).n_skipped_break.item() == 1
    q = L.book(books(step(108), "polymarket", "P"), "polymarket")
    br = [(a * NS, (b + 1) * NS) for a, b in L._breaks_g((), out)]
    assert L.quote_at(q, T0 + 102 * NS, "ask", br)[2] == "break"
    assert L.quote_at(q, T0 + 109 * NS, "ask", br)[:2][0] == pytest.approx(0.57)  # snapshot after it: fine


def test_capacity_is_best_level_size_at_fill():
    o = books(step(108), "polymarket", "P")
    o["size"] = np.where(o["kind"] == "ask", 25.0, 40.0)
    t = L.evaluate_game("syn", KO, books(step(100), "kalshi", "K"), o, "polymarket", T0, T0 + W * NS,
                        latencies=(0.0,), holdout_run=True, **D1)
    r = t.iloc[0]
    assert r.cap_contracts == 25.0 and r.cap_dollars == pytest.approx(25 * 0.51)   # buy at the ask 0.51
    cap = L.capacity(t)
    assert cap.cap_contracts_median.item() == 25.0 and cap.cap_dollars_total.item() == pytest.approx(12.75)
    us = L.evaluate_game("syn", KO, books(step(100), "kalshi", "K"), books(step(108), "polymarket_us", "P"),
                         "polymarket_us", T0, T0 + W * NS, latencies=(0.0,), holdout_run=True)
    assert np.isnan(us.iloc[0].cap_contracts) and np.isnan(L.capacity(us).cap_contracts_total.item())


# --- v2 Amendment 5 draft: causal trading end = min(kickoff + 4.5 h, pin_start + 60 s) ----------------------

def test_trading_end_is_causal():
    ko = KO.value
    assert L.trading_end_ns(ko, None) == ko + int(4.5 * 3600) * NS
    assert L.trading_end_ns(ko, float("nan")) == ko + int(4.5 * 3600) * NS
    pin = T0 // NS + 200
    assert L.trading_end_ns(ko, pin) == (pin + 60) * NS                   # the pin is observable at pin + 60 s
    assert L.trading_end_ns(ko, ko // NS + 5 * 3600) == ko + int(4.5 * 3600) * NS   # a late pin: 4.5 h wins


def _run_until(end_ns, cut_ns=None):
    k, o = books(step(100), "kalshi", "K"), books(step(108), "polymarket", "P")
    if cut_ns is not None:
        k, o = k[k.ts <= cut_ns], o[o.ts <= cut_ns]
    return L.evaluate_game("syn", KO, k, o, "polymarket", T0, end_ns, latencies=(0.0,), holdout_run=True, **D1)


def test_fill_before_pin_plus_60_fills_after_is_skipped():
    # 1 s market: entry fill at 102 s, exit fill at 110 s (test_signal_and_exact_pnl_at_1s_market_delay)
    pin = T0 // NS + 80                                   # exit fill at 110 s = pin + 30 s: inside, fills
    r = _run_until(L.trading_end_ns(KO.value, pin)).iloc[0]
    assert r.filled and r.exit_fill_ns == (pin + 30) * NS
    pin = T0 // NS + 49                                   # exit fill at 110 s = pin + 61 s: after the end, skipped
    r = _run_until(L.trading_end_ns(KO.value, pin)).iloc[0]
    assert not r.filled and r.skip == "after window end at exit"


def test_rows_after_pin_plus_60_change_no_filled_trade():
    pin = T0 // NS + 80
    end = L.trading_end_ns(KO.value, pin)
    full = _run_until(end)
    cut = _run_until(end, cut_ns=(pin + 60) * NS)
    f, c = full[full.filled.astype(bool)], cut[cut.filled.astype(bool)]
    cols = ["entry_fill_ns", "exit_fill_ns", "entry_px", "exit_px", "pnl_cents"]
    assert len(f) and f[cols].reset_index(drop=True).equals(c[cols].reset_index(drop=True))


def test_latency_curve_ci_is_game_bootstrap():
    """Two games, one trade each, edges 10 and 20 cents: the bootstrap resamples games, so the CI lies within
    [10, 20] and equals a hand recomputation; the per-trade normal CI is kept only as labelled extra columns."""
    t = pd.DataFrame({"game_id": ["g1", "g2", "g2"], "latency_s": 1.0, "filled": [True, True, False],
                      "skip": ["", "", "no quote at entry"], "edge_cents_per_contract": [10.0, 20.0, np.nan],
                      "pnl_cents": [100.0, 200.0, np.nan]})
    c = L.latency_curve(t).iloc[0]
    rng = np.random.default_rng(20261003)
    idx = rng.integers(0, 2, size=(2000, 2))
    m = np.array([10.0, 20.0])[idx].sum(axis=1) / 2
    assert c.n_games == 2 and c.n_trades == 2 and c.n_skipped_no_quote == 1
    assert (c.edge_ci_low, c.edge_ci_high) == (np.percentile(m, 2.5), np.percentile(m, 97.5))
    assert 10 <= c.edge_ci_low <= c.edge_ci_high <= 20
    assert "per_trade_normal_ci_low (not the plan's CI)" in c.index


def test_gradual_move_is_stamped_at_detection_not_start():
    """Kalshi mid 0.50, then +1 cent per second from label 100 (0.50) to label 107 (0.57); the 4-cent threshold
    (vs the trailing 10 s minimum 0.50) is first crossed at label 104 (0.54). The follower stays at 0.50.
    The entry must be decided at the detection label 104 and stamped 105 s, never at the start label + 1 s
    (101 s), and the entry gap must be the gap at label 104 (4 cents), not at the start (0)."""
    path = np.full(W, 0.50)
    for i, lab in enumerate(range(100, 108)):
        path[lab] = round(0.50 + 0.01 * i, 2)
    path[108:] = 0.57
    k = books(path, "kalshi", "K")
    o = books(np.full(W, 0.50), "polymarket", "P")
    sig = L.signals(k, o, "polymarket", T0, T0 + W * NS)
    s = sig.iloc[0]
    g0 = T0 // NS
    assert s.entry_g == g0 + 104 and s.direction == 1
    assert s.entry_decision_ns == (g0 + 105) * NS >= (g0 + 105) * NS
    assert s.entry_decision_ns != (g0 + 101) * NS
    assert s.gap_at_entry_cents == pytest.approx(4.0)                      # read at 104: 0.54 - 0.50
    j = L.leadlag.detect_jumps(L._grid(k, "kalshi", g0, g0 + W - 1, []), 4.0, 10).iloc[0]
    assert j.jump_g == g0 + 104 and j.start_g < g0 + 104                   # start label kept as information only


def test_exit_reason_window_end_vs_timeout():
    """Follower never converges: with a long window the exit is a 60 s timeout; with the window ending 20 s after
    the jump the exit is at the last label with reason "window end"."""
    k, o = books(step(100), "kalshi", "K"), books(np.full(W, 0.50), "polymarket", "P")
    s = L.signals(k, o, "polymarket", T0, T0 + W * NS).iloc[0]
    assert s.exit_reason == "timeout" and s.exit_g == s.entry_g + 60
    s = L.signals(k, o, "polymarket", T0, T0 + 121 * NS).iloc[0]
    assert s.exit_reason == "window end" and s.exit_g == T0 // NS + 120
