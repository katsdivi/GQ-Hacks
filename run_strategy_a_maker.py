"""Strategy A-maker on TRAINING games only (v3 Amendment 5 draft; holdout never loaded).

Reports per leg (favorite, underdog placebo): attempts, fills, fill rate, unfilled, skips by reason, mean fill,
win rate and win rate minus fill price, ROC on the Webull line and the Kalshi-direct line (TAKER formula, an upper
bound: Kalshi's maker fee is not confirmed first-party) with a game-level bootstrap 95% CI (2,000 resamples, seed
20261003), total P&L, and costs x2 (fees x2 and the fill 1 cent worse). Appends 2 rows to experiments/variants.csv
(the new variant, favorite and placebo) unless --no-variants-log.

Usage: python run_strategy_a_maker.py   (outputs under out/strategy_a_maker/, gitignored)
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import run_strategy_a as RA
import strategy_a as A
import strategy_a_maker as M

OUT = Path("out/strategy_a_maker")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-variants-log", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    games = A.load_games(RA.GAMES, RA.META, ticks_dir=RA.TICKS)
    assert all(g.kickoff < A.SEAL for g in games), "training only"
    rows = []
    for g in games:
        tr = pd.read_parquet(RA.TICKS / f"{g.game_id}.parquet")
        for r in M.evaluate_game(tr, g):
            r.update(kickoff=g.kickoff)
            rows.append(r)
    rows = pd.DataFrame(rows)
    rows.drop(columns=[c for c in rows.columns if c.startswith("_")], errors="ignore").to_parquet(OUT / "rows.parquet")
    s = M.summarize(rows)
    skips = rows.groupby(["placebo", "skip"]).size().rename("n").reset_index()
    ci = []
    for pl, r in rows.groupby("placebo"):
        e = r[r["entered"].astype(bool)]
        x2 = M.costs_x2(e) if len(e) else e
        for name, d in (("primary", e), ("costs x2", x2)):
            for line in ("webull", "direct"):
                x = d[f"roc_{line}"].to_numpy(float) if len(d) else np.array([])
                lo, hi = RA.boot_ci(x, np.random.default_rng(RA.SEED))
                ci.append({"leg": "placebo (underdog)" if pl else "favorite", "sample": name,
                           "line": line if line == "webull" else "direct (taker formula, upper bound)",
                           "n": len(x), "roc_mean": x.mean() if len(x) else np.nan, "ci_lo": lo, "ci_hi": hi,
                           "pnl_total": d[f"pnl_{line}"].sum() if len(d) else 0.0})
    ci = pd.DataFrame(ci)
    s.to_csv(OUT / "summary.csv", index=False)
    ci.to_csv(OUT / "roc_ci.csv", index=False)
    skips.to_csv(OUT / "skips.csv", index=False)
    if not a.no_variants_log:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        var = []
        for r in s.itertuples():
            e = rows[rows["entered"].astype(bool) & (rows["placebo"].astype(bool) == (r.leg != "favorite"))]
            cents = float(e["pnl_webull"].sum() / (A.QTY * len(e)) * 100) if len(e) else ""
            var.append({"ts_utc": now, "git_sha": sha, "game_set": f"strategy_a_maker training ({len(games)} games)",
                        "jump_cents": "", "window_s": "", "entry_gap": "", "timeout_s": "", "latency_s": M.LATENCY_S,
                        "n_games": r.games, "n_trades": r.fills, "edge_cents_mean": cents,
                        "notes": f"Strategy A-maker (v3 A5 draft); theta 0.80; {r.leg}; limit = as-of - 1c, fill on "
                                 f"trade-through in (t + 1 s, kickoff]; attempts {r.attempts}, fills {r.fills}; "
                                 f"edge = net cents per contract (Webull)"})
        pd.DataFrame(var).to_csv(RA.VARIANTS, mode="a", header=False, index=False)
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(s.round(4).to_string(index=False))
    print(ci.round(4).to_string(index=False))
    print(skips.to_string(index=False))


if __name__ == "__main__":
    main()
