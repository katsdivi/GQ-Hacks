"""Part 2 calibration: observed statistics of the 88 posthoc-mm-signal polymarket.com games (Oct 3, kickoff by 20:00 ET,
Vultr, already used by posthoc-mm-signal b346230 / N_CHECK 863eb69). Writes results/posthoc_mm_v4_extra/synthetic/
calibration.json. Labelled: SYNTHETIC SIMULATION inputs, calibrated to one day of observed data.

Statistics (venue time, quoting window = posthoc-mm-signal window minus kickoff cut, residue removed as in the maker):
- spread: time-weighted distribution of best ask - best bid in cents (both sides present);
- quote-update rate: top-of-book changes per minute;
- taker trades: arrivals per minute and the empirical size distribution;
- through share: share of trades printing strictly through the prevailing best on the aggressor side (needed because
  the maker's F1 rule only fills on through prints);
- mid volatility: std of 10 s mid changes (cents) by phase (pre-game, first half, second half; halves split at the
  window midpoint after the kickoff cut);
- jumps: count of |mid move| >= 10 c within 60 s (non-overlapping) per hour, and their size distribution;
- informed share: mean signed mid move 60 s after a trade (sign = aggressor direction inferred from price vs mid),
  divided by the informed impact d_inf = 1 c (fixed in SIM_SPEC), clipped to [0, 1].

Usage (cwd = repo root, PYTHONPATH=.:scripts): python scripts/mm_v4_calibrate.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import posthoc_mm_v4 as M

NS = M.NS
OUT = Path("results/posthoc_mm_v4_extra/synthetic")
D_INF = 0.01


def main() -> None:
    import holdout_mid as H
    OUT.mkdir(parents=True, exist_ok=True)
    q = M.pm_windows()
    maps = H.load_maps(M.ROOT / "data/live/holdout_maps")
    ld = M.Loader()
    spreads, sp_w, upd_rates, trade_rates, sizes, through, vols, jumps_per_h, jump_sizes, imp = \
        [], [], [], [], [], [], {"pre": [], "h1": [], "h2": []}, [], [], []
    for _, a in q.iterrows():
        lo, hi, ko = int(a.window_start_ns), int(a.window_end_ns), int(a.ko.value)
        inst = H.instruments(a, maps)
        pt = ld.rows("polymarket", inst["polymarket"], lo, hi)
        b = ld.book("polymarket", pt)
        live = (b.ts >= lo) & (b.ts < hi) & ~M.in_cut(b.ts, ko)
        if live.sum() < 10:
            continue
        ts, bid, ask = b.ts[live], b.bid[live], b.ask[live]
        ok = ~np.isnan(bid) & ~np.isnan(ask)
        dur = np.diff(np.append(ts, hi)) / NS
        spreads += list(np.round((ask - bid)[ok] * 100))
        sp_w += list(dur[ok])
        mins = ((hi - lo) - (M.CUT[1] - M.CUT[0])) / NS / 60
        mid = (bid + ask) / 2
        chg = np.sum(np.diff(np.where(ok, mid, np.nan)) != 0)
        upd_rates.append(chg / mins)
        tr = pt[(pt["kind"] == "trade") & pt["src_ts_ns"].notna()]
        tts = tr["src_ts_ns"].astype("int64").to_numpy()
        keep = (tts >= lo) & (tts < hi) & ~M.in_cut(tts, ko)
        tts, tpx, tsz = tts[keep], tr["price"].to_numpy(float)[keep], tr["size"].to_numpy(float)[keep]
        trade_rates.append(len(tts) / mins)
        sizes += list(tsz)
        if len(tts):
            i = np.searchsorted(b.ts, tts - 1, side="right") - 1
            ii = np.maximum(i, 0)
            pb_, pa_ = b.bid[ii], b.ask[ii]
            m0 = (pb_ + pa_) / 2
            v = (i >= 0) & ~np.isnan(m0)
            d = np.sign(tpx - m0)                      # aggressor direction: above mid = buy
            thr = ((d > 0) & (tpx > pa_ + M.EPS)) | ((d < 0) & (tpx < pb_ - M.EPS))
            through += list(thr[v & (d != 0)])
            m60 = b.mid(tts + 60 * NS)
            mv = d * (m60 - m0)
            imp += list(mv[v & (d != 0) & ~np.isnan(mv)])
        # 10 s mid grid for vol and jumps
        grid = np.arange(lo, hi, 10 * NS)
        grid = grid[~M.in_cut(grid, ko)]
        mg = b.mid(grid)
        dm = np.diff(mg) * 100
        gg = grid[1:]
        mid_t = ko + M.CUT[1] + (hi - (ko + M.CUT[1])) / 2
        for ph, msk in (("pre", gg < ko + M.CUT[0]), ("h1", (gg >= ko + M.CUT[1]) & (gg < mid_t)), ("h2", gg >= mid_t)):
            x = dm[msk & ~np.isnan(dm)]
            if len(x) > 5:
                vols[ph].append(float(np.std(x)))
        m60g = mg[::6]
        j = np.abs(np.diff(m60g)) * 100
        j = j[~np.isnan(j)]
        jumps_per_h.append(float((j >= 10).sum() / max(1e-9, len(j) / 60)))
        jump_sizes += list(j[j >= 10])
    sp = np.array(spreads)
    w = np.array(sp_w)
    vals = np.unique(np.clip(sp, 1, 10))
    probs = [float(w[np.clip(sp, 1, 10) == v].sum() / w.sum()) for v in vals]
    imp = np.array(imp) * 100
    cal = {
        "label": "SYNTHETIC SIMULATION inputs, calibrated to one day of observed data (88 polymarket.com games, Oct 3)",
        "source": "Vultr data/vultr/data/live/polymarket; windows feadc99 holdout_windows.csv; maker code 1d3d68a",
        "games_used": len(upd_rates),
        "spread_c_values": [int(v) for v in vals], "spread_c_probs": probs,
        "quote_updates_per_min_median": float(np.median(upd_rates)),
        "trades_per_min_median": float(np.median(trade_rates)), "trades_per_min_mean": float(np.mean(trade_rates)),
        "trade_size_quantiles": {str(p): float(np.quantile(sizes, p)) for p in (0.1, 0.25, 0.5, 0.75, 0.9, 0.99)},
        "through_share": float(np.mean(through)) if through else 0.0,
        "vol10s_c": {k: float(np.median(v)) if v else 0.0 for k, v in vols.items()},
        "jumps_per_hour_mean": float(np.mean(jumps_per_h)),
        "jump_size_c_quantiles": {str(p): float(np.quantile(jump_sizes, p)) for p in (0.25, 0.5, 0.75, 0.9)} if jump_sizes else {},
        "mean_signed_move_60s_c": float(np.mean(imp)) if len(imp) else 0.0,
        "d_inf_c": D_INF * 100,
        "informed_share": float(np.clip(np.mean(imp) / (D_INF * 100), 0, 1)) if len(imp) else 0.0,
        "observed_N_maker_pnl60_c_per_contract": 1.09, "observed_N_maker_as60_c": -0.40,
    }
    (OUT / "calibration.json").write_text(json.dumps(cal, indent=2))
    print(json.dumps(cal, indent=2))


if __name__ == "__main__":
    main()
