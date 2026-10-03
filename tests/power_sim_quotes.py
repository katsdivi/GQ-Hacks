"""Quote-based (book midpoint) power simulation, re-run 2026-10-03 (scipy Mann-Whitney, Amendment 2 mid rule).

Reuses hidden_path/quotes/quote_game from tests/test_activity_bias.py (synthetic data only).
Per (venue, games, study index): a fresh RNG seeded with [SEED, venue_idx, games, study]; games each of
no_link, zero_lag, lead_5s, plus a no_link placebo of the same size. decide() at alpha 0.05 and 0.025.
Run:  .venv/bin/python tests/power_sim_quotes.py [studies]
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
CASES = ("no_link", "zero_lag", "lead_5s")


def one_study(args):
    vi, games, i = args
    other = VENUES[vi]
    min_lead = 1.0 if other == "polymarket.com" else 1.5
    rng = np.random.default_rng([SEED, vi, games, i])
    lags = {c: [tab.quote_game(rng, c, other) for _ in range(games)] for c in CASES}
    placebo = [tab.quote_game(rng, "no_link", other) for _ in range(games)]
    res = {"venue": other, "games": games, "study": i}
    for c in CASES:
        r = np.array(lags[c], float)
        res[f"{c}_median"] = float(np.nanmedian(r)) if (~np.isnan(r)).any() else float("nan")
        for a in (0.05, 0.025):
            res[f"{c}_lead_{a}"] = xcorr_lead.decide(r, placebo, 0.0, min_lead_s=min_lead, alpha=a)["result"] == "kalshi leads"
    return res


def main(studies: int = 200):
    t0 = time.time()
    tasks = [(vi, g, i) for vi in range(2) for g in GAMES for i in range(studies)]
    with Pool(2) as p:
        rows = p.map(one_study, tasks, chunksize=4)
    df = pd.DataFrame(rows)
    out = []
    for (v, g), d in df.groupby(["venue", "games"]):
        row = {"venue": v, "games": g, "studies": len(d)}
        for c in CASES:
            row[f"{c}_rate@0.05"] = d[f"{c}_lead_0.05"].mean()
            row[f"{c}_rate@0.025"] = d[f"{c}_lead_0.025"].mean()
            row[f"{c}_median_lag"] = d[f"{c}_median"].median()
        out.append(row)
    res = pd.DataFrame(out)
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(res.round(3).to_string(index=False))
    res.to_csv(Path(__file__).resolve().parents[1] / "out" / "power_sim_quotes_report.csv", index=False)
    print(f"seed {SEED}, studies per cell {studies}, runtime {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
