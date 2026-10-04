"""Post-hoc Idea 8 matched-games placebo comparison (diagnostic, not a variant).

post-hoc diagnostic, computed after training results were seen; not a variant.
Reads only results/posthoc_idea8/training_trades.csv (committed 1e241e6). No strategy rerun, no new fills.
For each x: games where BOTH legs (fade, placebo = follow) entered; per-leg metrics and the per-game paired
difference fade minus follow, with game-bootstrap 95% CIs (2,000 reps, seed 20261004).

Usage (cwd = repo root): python scripts/posthoc_idea8_matched.py  -> results/posthoc_idea8/MATCHED_PLACEBO.md
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path("results/posthoc_idea8")
SEED, N_BOOT, QTY = 20261004, 2000, 10
LABEL = "post-hoc diagnostic, computed after training results were seen; not a variant"


def boot_ci(x: np.ndarray) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    m = x[rng.integers(0, len(x), size=(N_BOOT, len(x)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def leg_line(e: pd.DataFrame, line: str, sfx: str) -> dict:
    roc, pnl = e[f"roc_{line}{sfx}"].to_numpy(float), e[f"pnl_{line}{sfx}"].to_numpy(float)
    lo, hi = boot_ci(roc)
    return {"trades": len(e), "roc": roc.mean(), "lo": lo, "hi": hi, "cpc": pnl.sum() / (QTY * len(e)) * 100,
            "win": e["payout"].mean(), "fill": e[f"fill{sfx}"].mean(), "pnl": pnl.sum()}


def roc_x2_webull(e: pd.DataFrame) -> pd.Series:
    """roc_webull_x2 is not in the trades file; rebuild it from committed columns (fill_x2, fee, pnl)."""
    return e["pnl_webull_x2"] / (e["fill_x2"] * QTY + e["fee_webull_x2"])


def main() -> None:
    t = pd.read_csv(OUT / "training_trades.csv")
    t["roc_direct_x2"] = t["pnl_direct_x2"] / (t["fill_x2"] * QTY + t["fee_direct_x2"])
    t["roc_webull_x2"] = roc_x2_webull(t)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    L = [f"# Post-hoc Idea 8: matched-games placebo comparison\n",
         f"## {pd.Timestamp.now(tz='America/New_York'):%Y-%m-%d %H:%M} ET\n",
         f"**Label: {LABEL}.** Decided after the Idea 8 training results were seen. Source: "
         "results/posthoc_idea8/training_trades.csv (committed 1e241e6); script scripts/posthoc_idea8_matched.py "
         f"(run at HEAD {sha}). No strategy rerun, no new fills; SPEC.md, training_results.csv and TRAINING.md are "
         "unchanged. Matched set = games where both the fade and the follow (placebo) leg entered at that x. ROC "
         "CIs: game bootstrap, 2,000 reps, seed 20261004 (paired difference resamples games).\n",
         "Kalshi direct, costs x1:\n",
         "| x | matched games | leg | trades | ROC | 95% CI | c/contract | win rate | mean fill | total P&L $ |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    extra, paired, excl = [], [], []
    for x in (0.2, 0.4, 0.6):
        tx = t[t["x"] == x]
        f, p = tx[tx["leg"] == "fade"].set_index("game_id"), tx[tx["leg"] == "placebo"].set_index("game_id")
        both = sorted(set(f.index) & set(p.index))
        fm, pm = f.loc[both], p.loc[both]
        assert (fm["team"] != pm["team"]).all() and np.allclose(fm["I"], pm["I"])
        for name, e in (("fade", fm), ("follow", pm)):
            r = leg_line(e, "direct", "")
            L.append(f"| {x} | {len(both)} | {name} | {r['trades']} | {r['roc']:.4f} | [{r['lo']:.4f}, {r['hi']:.4f}] "
                     f"| {r['cpc']:.2f} | {r['win']:.3f} | {r['fill']:.3f} | {r['pnl']:.2f} |")
        d = (fm["roc_direct"] - pm["roc_direct"]).to_numpy(float)
        dp = (fm["pnl_direct"] - pm["pnl_direct"]).to_numpy(float)
        lo, hi = boot_ci(d)
        plo, phi = boot_ci(dp)
        paired.append(f"| {x} | {len(both)} | {d.mean():.4f} | [{lo:.4f}, {hi:.4f}] | {dp.mean():.3f} | [{plo:.3f}, {phi:.3f}] |")
        for line, sfx, nm in (("webull", "", "Webull, x1"), ("direct", "_x2", "Kalshi direct, x2"), ("webull", "_x2", "Webull, x2")):
            r = leg_line(fm, line, sfx)
            extra.append(f"| {x} | {nm} | {r['trades']} | {r['roc']:.4f} | [{r['lo']:.4f}, {r['hi']:.4f}] | {r['cpc']:.2f} | {r['pnl']:.2f} |")
        excl.append(f"| {x} | {len(f)} | {len(f) - len(both)} | {len(p)} | {len(p) - len(both)} | {len(both)} |")
    L += ["", "Paired difference, fade minus follow, per matched game (Kalshi direct, costs x1):", "",
          "| x | games | mean ROC diff | 95% CI | mean P&L diff $ per game | 95% CI |", "|---|---|---|---|---|---|", *paired,
          "", "Fade leg on the matched games, other fee lines (x2 ROC rebuilt as pnl_x2 / (fill_x2 x 10 + fee_x2) from "
          "committed columns):", "", "| x | line | trades | ROC | 95% CI | c/contract | total P&L $ |",
          "|---|---|---|---|---|---|---|", *extra,
          "", "Tie-back to the full table (training_results.csv): trades per leg, games dropped from each leg because "
          "the other leg did not enter, matched games:", "",
          "| x | fade trades (full) | fade excluded | follow trades (full) | follow excluded | matched |",
          "|---|---|---|---|---|---|", *excl, ""]
    (OUT / "MATCHED_PLACEBO.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
