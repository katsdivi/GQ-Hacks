"""Post-hoc training-positive book (results/posthoc/positive_book/SPEC.md, 5d568e4).

post-hoc, exploratory; cells chosen by training ROC after all results were seen.

Combines the committed holdout rows of the two included cells (Strategy A taker and Strategy A-maker, theta 0.80,
favorite leg), 10 contracts per trade as run, no reweighting, Kalshi direct. Reads committed files only:
results/holdout/strategy_a_rows.parquet, results/holdout/strategy_a_maker_rows.parquet. No strategy is run.
A-maker "direct" uses the taker fee formula (upper bound), as in the committed holdout output.

Usage (cwd = repo root): python scripts/posthoc_positive_book.py   -> results/posthoc/positive_book/metrics.json
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED, N_BOOT = 20261004, 2000
A_ROWS = "results/holdout/strategy_a_rows.parquet"
M_ROWS = "results/holdout/strategy_a_maker_rows.parquet"


def trades() -> pd.DataFrame:
    a = pd.read_parquet(A_ROWS)
    m = pd.read_parquet(M_ROWS)
    date = a.drop_duplicates("game_id").set_index("game_id")["date"]
    a = a[(~a["placebo"]) & a["entered"].astype(bool) & (a["theta"] == 0.8)].assign(cell="A taker")
    m = m[(~m["placebo"]) & m["entered"].astype(bool) & (m["theta"] == 0.8)].assign(cell="A-maker")
    m = m.assign(date=m["game_id"].map(date))
    cols = ["cell", "game_id", "date", "fill_price", "payout", "fee_direct", "pnl_direct", "roc_direct"]
    t = pd.concat([a[cols], m[cols]], ignore_index=True)
    assert t["date"].notna().all() and t["roc_direct"].notna().all()
    return t


def boot_ci(t: pd.DataFrame) -> tuple[float, float]:
    games = t["game_id"].unique()
    by = {g: x["roc_direct"].to_numpy(float) for g, x in t.groupby("game_id")}
    rng = np.random.default_rng(SEED)
    means = []
    for _ in range(N_BOOT):
        pick = rng.choice(games, size=len(games), replace=True)
        v = np.concatenate([by[g] for g in pick])
        means.append(v.mean())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def metrics(t: pd.DataFrame) -> dict:
    daily = t.groupby("date")["pnl_direct"].sum().sort_index()
    cum = np.concatenate([[0.0], daily.cumsum().to_numpy()])
    sd = daily.std(ddof=1)
    lo, hi = boot_ci(t)
    return {"trades": int(len(t)), "trades_by_cell": t["cell"].value_counts().to_dict(),
            "games": int(t["game_id"].nunique()), "pnl_total": float(t["pnl_direct"].sum()),
            "roc_mean": float(t["roc_direct"].mean()), "roc_ci_lo": lo, "roc_ci_hi": hi,
            "game_days": int(len(daily)), "sharpe_daily": float(daily.mean() / sd),
            "sharpe_x365": float(daily.mean() / sd * np.sqrt(365)),
            "max_drawdown": float((np.maximum.accumulate(cum) - cum).max()),
            "worst_day": float(daily.min()), "worst_day_date": str(daily.idxmin())}


if __name__ == "__main__":
    out = {"label": "post-hoc, exploratory; cells chosen by training ROC after all results were seen",
           "cells": ["Strategy A taker theta 0.80 favorite", "Strategy A-maker theta 0.80 favorite"],
           "sources": [A_ROWS, M_ROWS], "fee_line": "kalshi_direct (A-maker: taker formula, upper bound)",
           "sharpe_note": "daily P&L summed by ET kickoff date over game days only; x365 = daily Sharpe x sqrt(365)",
           **metrics(trades())}
    Path("results/posthoc/positive_book/metrics.json").write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))
