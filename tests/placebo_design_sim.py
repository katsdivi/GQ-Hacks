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
(linked); "rev" (added 2026-10-03): the other venue leads Kalshi by the same per-game jitter draw (O_rev drawn last
in game(), so K, O_zero, O_lead and the jitter are byte-identical to the 14:52 ET run and the lead/zero cells
reproduce it).
Shared-shift nulls (added 2026-10-03, lag level, not series level): real and placebo lags come from the SAME
distribution, centered at +2 s. They cannot be built from unrelated-game series (an unrelated pair's xcorr lag is
spread over [-15, 15] whatever the timestamps), so they are drawn directly as lags, with the same block / pair
structure as the ring (D1 = pairs (i, i+1), D2 = pairs (i, i+k), k = 1..5):
  "shift_iid": every real and placebo lag = round(2 + N(0, 2 s)), independent. THIS is the one the preset rule uses.
  "shift_clustered" (sensitivity only, not in the rule): per Kalshi game i an effect a_i ~ N(0, 2/sqrt 2) shared by
  its real lag and all its placebo pairs, plus residual N(0, 2/sqrt 2): same N(0, 2 s) marginal, but the 5 Design 2
  placebos that reuse Kalshi game i are correlated (0.5). This is the mechanism that could make Design 2 oversized.
  Draws use their own RNG ([SEED, 7, venue, n]) so the block starts (and the ring cells) are unchanged.
Reported per rep: decide() result (full rule, alpha 0.05) and the Mann-Whitney p alone; per-rep rows are written
to placebo_design_reps.csv so Wilson CIs can be recomputed anywhere.
Run: python tests/placebo_design_sim.py [M] [reps] [procs] [out_dir]
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
    o_lead = other(rng, p, float(jit), venue)
    o_rev = other(rng, p, -float(jit), venue)        # drawn last: earlier draws identical to the 14:52 ET run
    return {"K": k, "O_zero": o_zero, "O_lead": o_lead, "O_rev": o_rev, "true_lead": jit}


def lags_chunk(args):
    """Real lags for ring games [i0, i1) and placebo lags vs the next K games' O_zero (ring)."""
    venue, i0, i1, M = args
    res = []
    for i in range(i0, i1):
        g = game(venue, i)
        row = {"i": i, "true_lead": g["true_lead"],
               "real_lead": X.game_lag_mid(g["K"], "kalshi", g["O_lead"], "other"),
               "real_zero": X.game_lag_mid(g["K"], "kalshi", g["O_zero"], "other"),
               "real_rev": X.game_lag_mid(g["K"], "kalshi", g["O_rev"], "other")}
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


SHIFT_C, SHIFT_SD = 2.0, 2.0


def shift_lags(rng, n: int, clustered: bool):
    """Shared-shift null for one rep: real lags (n,) and placebo lags pl[k][i] for pair (i, i+k), k = 1..5."""
    if clustered:
        a = rng.normal(0, SHIFT_SD / np.sqrt(2), n)
        e_sd = SHIFT_SD / np.sqrt(2)
    else:
        a, e_sd = np.zeros(n), SHIFT_SD
    real = np.round(SHIFT_C + a + rng.normal(0, e_sd, n))
    pl = {k: np.round(SHIFT_C + a[: n - k] + rng.normal(0, e_sd, n - k)) for k in range(1, K_PAIRS + 1)}
    return real, pl


def judge(real, pl, venue):
    oth = "other"
    d = X.decide(real, pl, 0.0, "kalshi", oth, min_lead_s=MIN_LEAD[venue])
    return {"n_placebo": int((~np.isnan(pl)).sum()), "kalshi": d["result"] == "kalshi leads",
            "reverse": d["result"] == f"{oth} leads", "mw_p": X.mann_whitney_p(real, pl)}


def reps(tab: pd.DataFrame, venue: str, n: int, n_reps: int, rng) -> list[dict]:
    M = len(tab)
    out = []
    srng = np.random.default_rng([SEED, 7, list(VENUES).index(venue), n])
    for r in range(n_reps):
        s = int(rng.integers(0, M))
        idx = [(s + j) % M for j in range(n)]
        blk = tab.iloc[idx].reset_index(drop=True)
        pl1 = blk["pl1"].iloc[: n - 1].to_numpy(float)
        pl5 = np.concatenate([blk[f"pl{k}"].iloc[: n - k].to_numpy(float) for k in range(1, K_PAIRS + 1)])
        cases = [(scen, blk[f"real_{scen}"].to_numpy(float), pl1, pl5) for scen in ("lead", "zero", "rev")]
        for scen, clu in (("shift_iid", False), ("shift_clustered", True)):
            real, pl = shift_lags(srng, n, clu)
            cases.append((scen, real, pl[1], np.concatenate([pl[k] for k in range(1, K_PAIRS + 1)])))
        for scen, real, d1, d2 in cases:
            for design, pl in (("D1", d1), ("D2", d2)):
                out.append({"venue": venue, "n": n, "scenario": scen, "design": design, "rep": r, "block_start": s,
                            **judge(real, pl, venue)})
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
              f"real zero median {tab.real_zero.median():+.1f}, real rev median {tab.real_rev.median():+.1f} "
              f"({time.time() - t0:.0f} s)", flush=True)
        for n in NS_GAMES:
            rows += reps(tab, venue, n, n_reps, rng)
    r = pd.DataFrame(rows)
    r["mw_sig"] = r["mw_p"] < 0.05
    r.to_csv(f"{tmp}/placebo_design_reps.csv", index=False)
    t = r.groupby(["venue", "scenario", "n", "design"]).agg(reps=("kalshi", "size"), n_placebo=("n_placebo", "median"),
                                                            kalshi_leads=("kalshi", "mean"), reverse=("reverse", "mean"),
                                                            mw_sig=("mw_sig", "mean"))
    print(t.round(3).to_string())
    t.to_csv(f"{tmp}/placebo_design_table.csv")
    print(f"total {time.time() - t0:.0f} s; seed {SEED}; M {M}; reps {n_reps}")


if __name__ == "__main__":
    main()
