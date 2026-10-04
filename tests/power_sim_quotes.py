"""Quote-based (book midpoint) power simulation, re-run 2026-10-03 (scipy Mann-Whitney, Amendment 2 mid rule).

Reuses hidden_path/quotes/quote_game from tests/test_activity_bias.py (synthetic data only).
Per (venue, games, study index): a fresh RNG seeded with [SEED, venue_idx, games, study]; games each of
no_link, zero_lag, lead_5s, lead_jitter (per-game true lag 5 s + N(0, 2 s), rounded, clipped to [0, 12]), plus a
no_link placebo of the same size. decide() at alpha 0.05 and 0.025; "kalshi leads" and reverse ("<other> leads")
rates. Output: per-cell counts (for binomial CIs) to <out_dir>/power_sim_quotes.csv.
Run:  .venv/bin/python tests/power_sim_quotes.py [studies] [procs] [out_dir]
"""
from __future__ import annotations

import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_activity_bias as tab  # noqa: E402
import xcorr_lead  # noqa: E402

SEED = 20261003
VENUES = ("polymarket.com", "Polymarket US")
GAMES = (30, 40, 60, 80)
CASES = ("no_link", "zero_lag", "lead_5s", "lead_jitter")


def game(rng, case: str, other: str) -> float:
    if case != "lead_jitter":
        return tab.quote_game(rng, case, other)
    pk = tab.hidden_path(rng)
    lag = float(np.clip(round(5 + rng.normal(0, 2)), 0, 12))
    qk = tab.quotes(rng, pk, 0.0, flicker_per_min=6, venue="kalshi")
    if other == "polymarket.com":
        qo = tab.quotes(rng, pk, lag, flicker_per_min=2, venue="other")
    else:
        qo = tab.quotes(rng, pk, lag, flicker_per_min=1, venue="other", poll_s=1, recv_delay_s=0.3)
    return xcorr_lead.game_lag_mid(qk, "kalshi", qo, "other")


def one_study(args):
    vi, games, i = args
    other = VENUES[vi]
    min_lead = 1.0 if other == "polymarket.com" else 1.5
    rng = np.random.default_rng([SEED, vi, games, i])
    lags = {c: [game(rng, c, other) for _ in range(games)] for c in CASES}
    placebo = [tab.quote_game(rng, "no_link", other) for _ in range(games)]
    res = {"venue": other, "games": games, "study": i}
    for c in CASES:
        r = np.array(lags[c], float)
        res[f"{c}_median"] = float(np.nanmedian(r)) if (~np.isnan(r)).any() else float("nan")
        for a in (0.05, 0.025):
            d = xcorr_lead.decide(r, placebo, 0.0, "kalshi", "other", min_lead_s=min_lead, alpha=a)["result"]
            res[f"{c}_lead_{a}"] = d == "kalshi leads"
            res[f"{c}_rev_{a}"] = d == "other leads"
    return res


def main(studies: int = 200, procs: int = 2, out_dir: str = "out"):
    t0 = time.time()
    tasks = [(vi, g, i) for vi in range(2) for g in GAMES for i in range(studies)]
    with Pool(procs) as p:
        rows = p.map(one_study, tasks, chunksize=1)
    df = pd.DataFrame(rows)
    out = []
    for (v, g), d in df.groupby(["venue", "games"]):
        row = {"venue": v, "games": g, "studies": len(d)}
        for c in CASES:
            for a in (0.05, 0.025):
                row[f"{c}_kalshi_k@{a}"] = int(d[f"{c}_lead_{a}"].sum())
                row[f"{c}_reverse_k@{a}"] = int(d[f"{c}_rev_{a}"].sum())
            row[f"{c}_median_lag"] = d[f"{c}_median"].median()
        out.append(row)
    res = pd.DataFrame(out)
    with pd.option_context("display.width", 250, "display.max_columns", 60):
        print(res.to_string(index=False))
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    res.to_csv(Path(out_dir) / "power_sim_quotes.csv", index=False)
    df.to_csv(Path(out_dir) / "power_sim_quotes_studies.csv", index=False)
    print(f"seed {SEED}, studies per cell {studies}, procs {procs}, runtime {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200, int(sys.argv[2]) if len(sys.argv) > 2 else 2,
         sys.argv[3] if len(sys.argv) > 3 else "out")
