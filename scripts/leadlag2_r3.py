"""Post-hoc leadlag2 Round 3: CME vs Kalshi in-game lead-lag on the newly mapped training games (descriptive only).

post-hoc, exploratory; training only. Spec: results/posthoc_leadlag2/SPEC.md (Round 3, a815df2, committed before the
CME map was read). Coverage is 10 games (< 30), so by the spec there are no trading trials.

Inputs: map from branch data-cme-train 2126c45 (data/raw/cme_train_v2/map.csv, the ignored copy of
results/data_cme/map.csv); CME 1 s BBO data/raw/fg_cg_train_bbo-1s.parquet; Kalshi data/raw/kalshi_only.
CME P(home) = mean of the home contract mid and 1 - the away contract mid, where each exists (mid only when bid and
ask both exist). Kalshi P(home) = last trade. 1 s grid, backward as-of.

Usage (cwd = repo root, PYTHONPATH=.:scripts): python scripts/leadlag2_r3.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import leadlag
import leadlag2_common as C
import leadlag2_r1 as R1

S = C.NS


def cme_phome(bbo: pd.DataFrame, m: pd.DataFrame, game: str, home: str, away: str) -> pd.Series:
    parts = []
    for team, flip in ((home, False), (away, True)):
        sym = m[(m.game_id == game) & (m.team == team)]["symbol"]
        if sym.empty:
            continue
        x = bbo[bbo.symbol == sym.iloc[0]]
        x = x[(x.bid_px_00 > 0) & (x.ask_px_00 > 0) & (x.ask_px_00 < 1.5)]
        mid = (x.bid_px_00 + x.ask_px_00) / 2
        s = pd.Series((1 - mid if flip else mid).to_numpy(), index=x.index.as_unit("ns").asi8)
        s = s[~s.index.duplicated(keep="last")].sort_index()
        parts.append(s)
    if not parts:
        return pd.Series(dtype=float)
    return pd.concat(parts, axis=1).sort_index().ffill().mean(axis=1)


def grid_series(ts: np.ndarray, px: np.ndarray, lo: int, hi: int) -> pd.Series:
    g = np.arange(lo, hi + 1, S, dtype=np.int64)
    p, _ = R1.asof_grid(ts, px, g)
    return pd.Series(p, index=np.arange(len(g)))


def main() -> None:
    m = pd.read_csv(C.DATA / "raw" / "cme_train_v2" / "map.csv")
    m = m[(m.cme_bbo_rows_in_window > 0) & (m.kalshi_trades_in_window > 0)]
    bbo = pd.read_parquet(C.DATA / "raw" / "fg_cg_train_bbo-1s.parquet")
    ko = pd.read_csv(C.DATA / "raw" / "kalshi_only_games.csv").set_index("game_id")
    rows, series = [], {}
    for gid in sorted(m.game_id.unique()):
        r = ko.loc[gid]
        k0 = pd.Timestamp(r.kickoff_utc_espn).value
        assert k0 < C.SEAL.value, "training only"
        t = pd.read_parquet(C.DATA / "raw" / "kalshi_only" / f"{gid}.parquet", columns=["ts", "kind", "price"])
        kts, kpx = C._phome(t)
        cm = cme_phome(bbo, m, gid, r.home, r.away)
        if cm.empty:
            continue
        lo = max(k0 + 20 * 60 * S, int(cm.index[0]))
        hi = min(k0 + 4 * 3600 * S, int(kts[-1]))
        if hi - lo < 1800 * S:
            rows.append({"game_id": gid, "note": "under 30 min of overlap"})
            continue
        cg = grid_series(cm.index.to_numpy(np.int64), cm.to_numpy(float), lo, hi)
        kg = grid_series(kts, kpx, lo, hi)
        series[gid] = (lo - k0, cg, kg)          # offset from kickoff, for game-clock placebo alignment
        dc, dk = cg.diff().fillna(0).to_numpy(), kg.diff().fillna(0).to_numpy()
        lag, corr = leadlag.xcorr_lag(cg, kg, 15)   # levels; xcorr_lag differences internally
        jc = leadlag.detect_jumps(cg, 3.0, 10)
        rc = leadlag.response_times(jc, kg, 0.8, 60)
        jk = leadlag.detect_jumps(kg, 3.0, 10)
        rk = leadlag.response_times(jk, cg, 0.8, 60)
        vec = R1.vecm_shares(cg.to_numpy(float), kg.to_numpy(float))
        rows.append({"game_id": gid, "minutes": (hi - lo) / 60 / S, "cme_changes": int((dc != 0).sum()),
                     "kalshi_changes": int((dk != 0).sum()), "xcorr_lag_s": lag,
                     "cme_jumps": len(jc), "kalshi_cover_share": float(rc.covered.mean()) if len(rc) else np.nan,
                     "kalshi_resp_median_s": float(rc.response_s.median()) if len(rc) else np.nan,
                     "kalshi_jumps": len(jk), "cme_cover_share": float(rk.covered.mean()) if len(rk) else np.nan,
                     "cme_resp_median_s": float(rk.response_s.median()) if len(rk) else np.nan,
                     "is_cme": vec.get("is_pm"), "gg_cme": vec.get("gg_pm")})
    D = pd.DataFrame(rows)
    # placebo pairs: CME of game A vs Kalshi of game B, aligned on time since kickoff (unrelated games; real games on
    # the same clock time barely overlap in-game, so clock-time pairs are not available)
    plc = []
    ids = list(series)
    for a in ids:
        for b in ids:
            if a == b:
                continue
            la, ca, _ = series[a]
            lb, _, kb = series[b]
            off = (la - lb) // S
            ka = kb.copy()
            ka.index = ka.index - off
            j = ca.index.intersection(ka.index)
            if len(j) < 1800:
                continue
            xa, xb = ca.loc[j].reset_index(drop=True), ka.loc[j].reset_index(drop=True)
            if xa.diff().std() == 0 or xb.diff().std() == 0:
                continue
            lag, _ = leadlag.xcorr_lag(xa, xb, 15)
            plc.append({"cme_game": a, "kalshi_game": b, "xcorr_lag_s": lag})
    P = pd.DataFrame(plc)
    C.OUT.mkdir(parents=True, exist_ok=True)
    D.to_csv(C.OUT / "r3_cme_games.csv", index=False)
    P.to_csv(C.OUT / "r3_cme_placebo.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(D.round(3).to_string(index=False))
    print("placebo pairs:", len(P), P.xcorr_lag_s.describe().round(2).to_dict() if len(P) else {})


if __name__ == "__main__":
    sys.exit(main())
