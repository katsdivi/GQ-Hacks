"""Post-hoc leadlag2 Round 2: multi-hour pre-game lead-lag, polymarket.com vs Kalshi.

post-hoc, exploratory; training only. Spec: results/posthoc_leadlag2/SPEC.md (Round 2, 5a02d77, committed before any
full-history data was read).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/leadlag2_r2.py --source fullhist     full-history files (data/raw/fullhist/{kalshi,polymarket})
  python scripts/leadlag2_r2.py --source existing     fallback: existing files, W = 30 min only
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

import leadlag2_common as C
import leadlag2_r1 as R1

MIN = 60 * C.NS
STALE = 10 * MIN


def load(source: str) -> list[dict]:
    sett = C._settle_map()
    ko = pd.read_csv(C.DATA / "raw" / "kalshi_only_games.csv")
    b = pd.read_csv(C.OUTB / "b_games_espn.csv")
    bset = set(b["game_id"]) - C.EXCLUDED_A1
    games = []
    for r in ko.itertuples():
        k = pd.Timestamp(r.kickoff_utc_espn)
        assert k < C.SEAL, "training only"
        if r.game_id not in bset:
            continue
        if source == "fullhist":
            pk = C.DATA / "raw" / "fullhist" / "kalshi" / f"{r.game_id}.parquet"
            pp = C.DATA / "raw" / "fullhist" / "polymarket" / f"{r.game_id}.parquet"
        else:
            pk = C.DATA / "raw" / "kalshi_only" / f"{r.game_id}.parquet"
            pp = C.DATA / "ticks" / f"{r.game_id}_polymarket.parquet"
        if not (pk.exists() and pp.exists()):
            continue
        t = pd.read_parquet(pk)
        q = pd.read_parquet(pp)
        t = t[t["ts"] < k.value + 6 * 3600 * C.NS]
        games.append({"game_id": r.game_id, "league": r.league, "home": r.home, "away": r.away,
                      "kickoff_ns": k.value,
                      "pay": {r.home: sett.get((r.game_id, "home"), np.nan),
                              r.away: sett.get((r.game_id, "away"), np.nan)},
                      "own": {r.home: C._own(t, f"{r.kalshi_event}-{r.home}", False),
                              r.away: C._own(t, f"{r.kalshi_event}-{r.away}", True)},
                      "kph": C._phome(t), "pm": C._phome(q)})
    return games


def signals(g: dict, w_min: int, d: float, direction: str) -> list[tuple[int, int]]:
    kt, kp = g["kph"]
    pt, pp = g["pm"]
    if len(kt) == 0 or len(pt) == 0:
        return []
    start = max(kt[0], pt[0]) + w_min * MIN
    end = g["kickoff_ns"] - 10 * MIN
    if start >= end:
        return []
    grid = np.arange(start, end + 1, MIN, dtype=np.int64)
    k, ka = R1.asof_grid(kt, kp, grid)
    q, qa = R1.asof_grid(pt, pp, grid)
    k0, _ = R1.asof_grid(kt, kp, grid - w_min * MIN)
    q0, _ = R1.asof_grid(pt, pp, grid - w_min * MIN)
    mk, mq = k - k0, q - q0
    fresh = (ka <= STALE) & (qa <= STALE)
    if direction == "pm":
        ok = fresh & (np.abs(mq) >= d - 1e-9) & (np.abs(mk) < d / 2) & np.isfinite(mk)
        sg = np.sign(mq)
    else:
        ok = fresh & (np.abs(mk) >= d - 1e-9) & (np.abs(mq) < d / 2) & np.isfinite(mq)
        sg = np.sign(mk)
    return [(int(a), int(b)) for a, b in zip(grid[ok], sg[ok])]


def exit_kickoff(ts, px, ko: int):
    lo = ko - 5 * MIN
    i = np.searchsorted(ts, lo, side="left")
    if i >= len(ts) or ts[i] > lo + 10 * MIN:
        return None
    return int(ts[i]), max(round(px[i] - 0.01, 4), 0.01)


def trade(g, sigs, trial, exec_mode, exit_mode):
    for t, dirn in sigs:
        team = g["home"] if dirn > 0 else g["away"]
        ts, px = g["own"][team]
        pay = g["pay"][team]
        if exec_mode == "taker":
            f = C.taker_entry(ts, px, t, 60)
            fe, fa = C.fee_taker, C.fee_taker
        else:
            last = C.asof(ts, px, t)
            f = C.maker_entry(ts, px, t, last, 300) if last == last else None
            fe, fa = C.fee_maker175, C.fee_maker0
        if f is None:
            continue
        fill_ts, entry = f
        if pay != pay:
            return []
        if exit_mode == "ko" and fill_ts < g["kickoff_ns"] - 5 * MIN:
            ex = exit_kickoff(ts, px, g["kickoff_ns"])
            if ex is not None:
                return [R1.row(trial, g, team, t, entry, fe(entry), fa(entry), None, exit_px=ex[1],
                               extra={"held": False})]
        return [R1.row(trial, g, team, t, entry, fe(entry), fa(entry), pay,
                       extra={"held": True})]
    return []


def registry(source: str) -> list[dict]:
    reg = []
    for dr in ("pm", "k"):
        for w in ((30, 120) if source == "fullhist" else (30,)):
            for d in (0.02, 0.04):
                for ex in ("taker", "maker"):
                    for xm in ("ko", "settle"):
                        reg.append({"round": 2, "trial": f"LL2.R2.{dr}.W{w}.d{int(d * 100)}.{ex}.{xm}",
                                    "method": "pre-game: polymarket.com leads, buy Kalshi" if dr == "pm"
                                    else "pre-game placebo: Kalshi leads, buy Kalshi momentum",
                                    "params": f"source={source} dir={dr} W={w}min d={d} exec={ex} exit={xm}",
                                    "cost_line": "taker (alt taker)" if ex == "taker" else "maker175 (alt maker0)",
                                    "dir": dr, "w": w, "d": d, "exec": ex, "xm": xm})
    return reg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["fullhist", "existing"], required=True)
    a = ap.parse_args()
    games = load(a.source)
    wk = R1.week_map()
    print(f"R2 games ({a.source}): {len(games)}", flush=True)
    span = [(g["kickoff_ns"] - max(g["kph"][0][0], g["pm"][0][0])) / 3600e9 for g in games
            if len(g["kph"][0]) and len(g["pm"][0])]
    print(f"pre-game span both venues (h): median {np.median(span):.1f}, p10 {np.percentile(span, 10):.1f}", flush=True)
    rows = []
    for r in registry(a.source):
        for g in games:
            if wk[g["game_id"]] < C.HIST_WEEKS:
                continue
            rows += trade(g, signals(g, r["w"], r["d"], r["dir"]), r["trial"], r["exec"], r["xm"])
    T = pd.DataFrame(rows)
    T.to_parquet(C.CACHE / "trades_round2.parquet", index=False)
    pd.DataFrame(registry(a.source)).drop(columns=["dir", "w", "d", "exec", "xm"]).to_csv(
        C.CACHE / "registry_round2.csv", index=False)
    print(f"R2 trades: {len(T)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
