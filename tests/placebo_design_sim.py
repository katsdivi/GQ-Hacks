"""Placebo design comparison (synthetic only; run as a script, not a pytest test).

Design 1 (current runner): each qualifying game A is paired with the next game B -> about n - 1 placebo pairs.
Design 2 (proposed): each game A is paired with the next K = 5 games -> about 5n placebo pairs (series reused).

Setup: book mids under the Amendment 2 mid rule (xcorr_lead.game_lag_mid), tests/test_activity_bias.py quote
generator, both venues: polymarket.com-like streamed quotes and Polymarket-US-like 1 s polled quotes.

To keep the reuse structure of Design 2 exact while making 500+ reps feasible, a ring of M synthetic games is
built once per venue. Game i has its own hidden path, a Kalshi series K_i and other-venue series O_i (one per
scenario). Precomputed: real lags lag(K_i, O_i^scenario) and placebo lags lag(K_i, O_j^zero) for j = i+1..i+5
(unrelated paths). A rep takes a random block of n consecutive ring games; Design 1 uses pairs (i, i+1) inside
the block, Design 2 pairs (i, i+k), k = 1..5, inside the block. Blocks of different reps overlap (M >> n keeps
this mild); the Monte Carlo SE quoted assumes independent reps and is therefore a little optimistic.

Series are regenerated from a per-game seed (numpy SeedSequence [SEED, venue, i]) instead of stored.
Scenarios: "lead5": true lag per game 5 s + N(0, 2 s) jitter, rounded, clipped to [0, 12]; "zero": true lag 0
(linked). Reported: share of reps with decide() = "kalshi leads" and = "<other> leads" (reverse), alpha 0.05.
Run: python tests/placebo_design_sim.py [M] [reps] [procs]
"""
from __future__ import annotations

import sys
import time
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
import xcorr_lead as X  # noqa: E402
from tests.test_activity_bias import hidden_path, quotes  # noqa: E402

K_PAIRS = 5
NS_GAMES = (30, 40, 60)
SEED = 20261003
VENUES = {"polymarket.com": dict(flicker_per_min=2), "Polymarket US": dict(flicker_per_min=1, poll_s=1, recv_delay_s=0.3)}
MIN_LEAD = {"polymarket.com": 1.0, "Polymarket US": 1.5}


def other(rng, path, lag, venue):
    return quotes(rng, path, lag, venue="other", **VENUES[venue])


def game(venue: str, i: int) -> dict:
    """Ring game i, regenerated from its own seed (same series every time it is needed)."""
    rng = np.random.default_rng([SEED, list(VENUES).index(venue), i])
    p = hidden_path(rng)
    k = quotes(rng, p, 0.0, 6, "kalshi")
    o_zero = other(rng, p, 0.0, venue)
    jit = int(np.clip(round(5 + rng.normal(0, 2)), 0, 12))
    return {"K": k, "O_zero": o_zero, "O_lead": other(rng, p, float(jit), venue), "true_lead": jit}


def lags_chunk(args):
    """Real lags for ring games [i0, i1) and placebo lags vs the next K games' O_zero (ring)."""
    venue, i0, i1, M = args
    res = []
    for i in range(i0, i1):
        g = game(venue, i)
        row = {"i": i, "true_lead": g["true_lead"],
               "real_lead": X.game_lag_mid(g["K"], "kalshi", g["O_lead"], "other"),
               "real_zero": X.game_lag_mid(g["K"], "kalshi", g["O_zero"], "other")}
        for k in range(1, K_PAIRS + 1):
            row[f"pl{k}"] = X.game_lag_mid(g["K"], "kalshi", game(venue, (i + k) % M)["O_zero"], "other")
        res.append(row)
    return res


def build(venue, M, procs, tmp):
    jobs = [(venue, a, min(a + 25, M), M) for a in range(0, M, 25)]
    with Pool(procs) as pool:
        rows = [r for part in pool.imap_unordered(lags_chunk, jobs) for r in part]
    tab = pd.DataFrame(rows).sort_values("i").reset_index(drop=True)
    tab.to_csv(f"{tmp}/ring_{list(VENUES).index(venue)}.csv", index=False)
    return tab


def reps(tab: pd.DataFrame, venue: str, n: int, n_reps: int, rng) -> list[dict]:
    M = len(tab)
    out = []
    oth = "other"
    for _ in range(n_reps):
        s = int(rng.integers(0, M))
        idx = [(s + j) % M for j in range(n)]
        blk = tab.iloc[idx].reset_index(drop=True)
        pl1 = blk["pl1"].iloc[: n - 1].to_numpy(float)
        pl5 = np.concatenate([blk[f"pl{k}"].iloc[: n - k].to_numpy(float) for k in range(1, K_PAIRS + 1)])
        for scen in ("lead", "zero"):
            real = blk[f"real_{scen}"].to_numpy(float)
            for design, pl in (("D1", pl1), ("D2", pl5)):
                d = X.decide(real, pl, 0.0, "kalshi", oth, min_lead_s=MIN_LEAD[venue])
                out.append({"venue": venue, "n": n, "scenario": scen, "design": design,
                            "n_placebo": int((~np.isnan(pl)).sum()),
                            "kalshi": d["result"] == "kalshi leads", "reverse": d["result"] == f"{oth} leads"})
    return out


def main():
    M = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    n_reps = int(sys.argv[2]) if len(sys.argv) > 2 else 500
    procs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    tmp = sys.argv[4] if len(sys.argv) > 4 else "."
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    rows, ring = [], {}
    for venue in VENUES:
        tab = build(venue, M, procs, tmp)
        ring[venue] = tab
        pl = tab[[f"pl{k}" for k in range(1, 6)]]
        # Dependence check for Design 2: do placebo lags that share a Kalshi series correlate?
        a, b = tab["pl1"].to_numpy(float), tab["pl2"].to_numpy(float)
        ok = ~np.isnan(a) & ~np.isnan(b)
        print(f"{venue}: M {M}, placebo lag median {np.nanmedian(pl.to_numpy()):+.1f}, corr(pl1, pl2) same Kalshi "
              f"{np.corrcoef(a[ok], b[ok])[0, 1]:+.3f}, real lead median {tab.real_lead.median():+.1f}, "
              f"real zero median {tab.real_zero.median():+.1f} ({time.time() - t0:.0f} s)", flush=True)
        for n in NS_GAMES:
            rows += reps(tab, venue, n, n_reps, rng)
    r = pd.DataFrame(rows)
    t = r.groupby(["venue", "scenario", "n", "design"]).agg(reps=("kalshi", "size"), n_placebo=("n_placebo", "median"),
                                                            kalshi_leads=("kalshi", "mean"), reverse=("reverse", "mean"))
    print(t.round(3).to_string())
    t.to_csv(f"{tmp}/placebo_design_table.csv")
    print(f"total {time.time() - t0:.0f} s; seed {SEED}; M {M}; reps {n_reps}")


if __name__ == "__main__":
    main()
