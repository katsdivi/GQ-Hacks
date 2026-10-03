"""Strategy B on fake games only (HYPOTHESIS_v3.md Strategy B + Amendment 1 sections 3 and 5). Prices P(home).
Fake game: both venues trade every second at 0.50; from second S polymarket.com jumps to 0.55 (Kalshi below by
5 cents) and Kalshi follows at second S + F. Hand-derived expectations in the comments."""
import numpy as np
import pandas as pd
import pytest

import strategy_b as B

NS = 1_000_000_000
KO = pd.Timestamp("2025-10-04 20:00", tz="UTC")
LO = KO.value - B.PRE_S * NS                    # window start
S = 600                                         # seconds after window start


def series(venue, path, every=1, start=0, extra=()):
    rows = [{"ts": LO + (start + i) * NS + 200_000_000, "venue": venue, "market_id": venue, "kind": "trade",
             "price": float(p), "size": 1.0, "side": "buy"} for i, p in enumerate(path) if i % every == 0]
    rows += [dict(venue=venue, market_id=venue, kind="trade", size=1.0, side="buy", **r) for r in extra]
    return pd.DataFrame(rows).sort_values("ts", kind="stable").reset_index(drop=True)


def game(f=40, n=1200, k_every=1, p_every=1, p_jump=0.55):
    k = np.where(np.arange(n) >= S + f, 0.55, 0.50)
    p = np.where(np.arange(n) >= S, p_jump, 0.50)
    return series("kalshi", k, k_every), series("polymarket", p, p_every)


def run(kt, pt, settings=((0.03, 10, 60),)):
    t, _ = B.evaluate_game("g", KO, kt, pt, settings=settings)
    return t


def test_entry_after_m_seconds_and_fill_after_latency():
    t = run(*game())
    r = t.iloc[0]
    # d <= -3c from label LO+S (the 3 s median moves once 2 of 3 trades are new: label S+1); 10 s run ends at S+10
    assert r.direction == 1 and r.entry_g == LO // NS + S + 10
    # decision at (S + 11) s; fill = first Kalshi trade at or after S + 12 s (trade at S + 12.2 s) at 0.50 + 0.5c
    assert r.entry_dec_ns == LO + (S + 11) * NS and r.entry_fill_ts == LO + (S + 12) * NS + 200_000_000
    assert r.entry_px == pytest.approx(0.505)
    # Kalshi follows at S + 40: the gap closes (|d| < 1c) once its median is 0.55 (label S + 41) -> exit decision
    # at S + 42 s, fill at the S + 43.2 s trade, 0.55 - 0.5c
    assert r.exit_reason == "converged" and r.exit_px == pytest.approx(0.545)
    gross = (0.545 - 0.505) * 10
    assert r.pnl_webull == pytest.approx(gross - 0.40)
    assert r.fee_direct == B.fee_kalshi_direct(0.505, 10) + B.fee_kalshi_direct(0.545, 10)


def test_timeout_and_m_and_k():
    kt, pt = game(f=10_000)                                         # Kalshi never follows
    r = run(kt, pt, ((0.03, 10, 60),)).iloc[0]
    assert r.exit_reason == "timeout" and r.exit_g == r.entry_g + 60
    assert run(kt, pt, ((0.06, 10, 60),)).empty                     # 5c gap never reaches k = 6c
    r30 = run(kt, pt, ((0.03, 30, 60),)).iloc[0]
    assert r30.entry_g == r.entry_g + 20                            # m = 30 needs 20 more seconds


def test_staleness_60s_blocks_entry():
    kt, pt = game(f=10_000, p_every=90)                             # polymarket.com trades every 90 s only
    t = run(kt, pt)
    # d is valid only in the 60 s after each polymarket.com trade; entries need 10 valid seconds in a row
    g = B.build_grid(kt, pt, *B.window(KO))
    lab = np.arange(len(g.d))
    sec_since = (lab - (lab // 90) * 90)                            # seconds since the last trade (at 0.2 s)
    assert not g.valid[sec_since >= 60].any()
    for r in t.itertuples():
        e = r.entry_g - g.lo_g
        assert g.valid[e - 9:e + 1].all()


def test_no_fill_within_60s_skips_whole_trade():
    kt, pt = game(f=10_000)
    gap = kt[(kt.ts >= LO + (S + 11) * NS) & (kt.ts < LO + (S + 75) * NS)].index  # no Kalshi trade 11..75 s
    t = run(kt.drop(gap), pt)
    r = t.iloc[0]
    # the gap also makes Kalshi stale, so the first entry is after Kalshi resumes; the first signal must not fill
    # from a trade outside [dec + 1 s, dec + 60 s]
    for x in t.itertuples():
        if x.filled:
            assert x.entry_dec_ns + NS <= x.entry_fill_ts <= x.entry_dec_ns + 60 * NS
    tr = kt.sort_values("ts")
    assert B.first_fill(tr.ts.to_numpy(), tr.price.to_numpy(), LO + (S + 5) * NS) is not None
    kd = kt.drop(gap).sort_values("ts")
    assert B.first_fill(kd.ts.to_numpy(), kd.price.to_numpy(), LO + (S + 11) * NS) is None


def test_no_lookahead_future_rows_do_not_change_trade():
    kt, pt = game()
    full = run(kt, pt).iloc[0]
    cut = full.exit_fill_ts
    t = run(kt[kt.ts <= cut], pt[pt.ts <= cut]).iloc[0]
    assert (t.entry_g, t.exit_g, t.entry_px, t.exit_px) == (full.entry_g, full.exit_g, full.entry_px, full.exit_px)


def test_sell_direction_and_seal():
    kt, pt = game(p_jump=0.45)                                      # polymarket.com drops: Kalshi above -> sell
    kt.loc[kt.ts >= LO + (S + 40) * NS, "price"] = 0.45
    r = run(kt, pt).iloc[0]
    assert r.direction == -1 and r.entry_px == pytest.approx(0.495) and r.exit_px == pytest.approx(0.455)
    assert r.pnl_webull == pytest.approx((0.495 - 0.455) * 10 - 0.40)
    with pytest.raises(ValueError):
        B.evaluate_game("g", pd.Timestamp("2026-09-05", tz="UTC"), kt, pt)


def test_placebo_pairs_cyclic_within_30_min():
    g = pd.DataFrame({"game_id": ["a", "b", "c", "d"],
                      "espn_kickoff": ["2025-10-04 16:00Z", "2025-10-04 16:00Z", "2025-10-04 16:30Z", "2025-10-04 20:00Z"]})
    assert B.placebo_pairs(g) == [("a", "b"), ("b", "c"), ("c", "a")]


def test_select_setting_needs_30_trades():
    s = pd.DataFrame({"k": [0.03, 0.05], "m": [10, 10], "T": [60, 60], "n_trades": [29, 30],
                      "edge_webull_cents": [9.0, 1.0]})
    assert B.select_setting(s) == (0.05, 10, 60)
