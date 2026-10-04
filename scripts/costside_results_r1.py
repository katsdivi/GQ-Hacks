"""Write the Round 1 section of results/posthoc_costside/RESULTS.md from committed logs (post-hoc, exploratory)."""
import json

import pandas as pd

import costside_common as C

l = pd.read_csv(C.OUT / "trials_log.csv")
c = json.loads((C.OUT / "correction.json").read_text())
d = pd.read_parquet(C.CACHE / "diag_round1.parquet")
d = d[d.status.isin(["filled", "unfilled"]) & d.payout.notna()]
d["sig"] = d.trial.str.split(".").str[2]
d["cfg"] = d.trial.str.split(".", n=3).str[3]
a = d.groupby(["sig", "cfg", "status"]).payout.agg(["mean", "count"]).unstack("status")
a.columns = [f"{x}_{y}" for x, y in a.columns]
a.round(3).reset_index().to_csv(C.OUT / "round1_adverse_selection.csv", index=False)
cols = ["trial", "trades", "roc", "roc_lo", "roc_hi", "c_per_contract", "alt_roc", "alt_c_per_contract", "excl5_pnl",
        "sharpe_x365", "holm_p"]
top = l[l["round"] == 1].sort_values("roc", ascending=False)[cols].head(10).round(4)
b = c["in_sample_best_by_roc"]
txt = f"""# Post-hoc cost-side search: results

**Label: post-hoc, exploratory; training only (walk-forward test weeks); every trial counted; holdout not run.**

## Round 1 (79 trials; run 2026-10-04 05:45 ET)

Bug disclosed: the first Round 1 run mapped no signals for Ideas 7 and 12 (their files store team as "home"/"away";
0 trades in those 8 trials). Fixed (mapped to Kalshi codes) and Round 1 rerun once; the first run's log and trials
table are kept on disk (data/costside_cache/*first_bugged*, gitignored). Verdict unchanged.

### Maker fill rate and adverse selection (win rate of filled vs unfilled signals)

{C.md(a.round(3), index=True)}

Makers get filled when they are wrong: Idea 9 filled signals win about 0.42 vs 0.47 to 0.55 unfilled; Strategy A
0.90 vs 0.92. Strategy A fill rates are low (1% to 44%).

### Top 10 Round 1 trials by ROC (primary line; alt = maker0 for maker trials, else same)

{C.md(top)}

### Block summary

- A (maker execution of existing signals): best with >= 100 trades is Strategy A, limit at last trade, W 300 s:
  ROC +0.032 [-0.030, +0.084], 124 trades.
- B (fee bands, walk-forward): B1 -0.004 (100 trades); B2 13 trades.
- C1 (polymarket.com leads Kalshi): only maker + hold to settlement at d 0.05, s 15 is positive, +0.019
  [-0.036, +0.076], 764 trades; every H60/H300 exit is negative.
- C2 (CME): skipped, 1 mapped game.
- C3 (Kalshi own 5 c moves): every trial negative (best -0.025); no momentum or reversal edge.
- C4 (in-game band at kickoff + 20 min): longshot bias is strong below 0.20 (win 0.070 vs break-even 0.128,
  ROC -0.45); 0.20 to 0.40 is +0.045 [-0.101, +0.192]; 0.80 to 0.99 slightly negative.

### Correction after Round 1 (own 79 + broad search 54 = 133 trials; helpers not yet available)

Reality Check p for the best by t-stat ({c['best_by_t']}): {c['rc_p_best_by_t']:.3f}. DSR of that best:
{c['dsr_best']:.2e} (project convention, report_book.deflated_sharpe; normal-returns version
{c['dsr_best_normal_returns']:.2e}; SR0 {c['sr0']:.3f} is inflated by consistently losing trials). Holm survivors:
none. Stop condition: not met.

IN-SAMPLE BEST, after {c['cumulative_trials']} trials, not expected to persist: {b['trial']}, ROC {b['roc']:.3f}
[{b['roc_lo']:.3f}, {b['roc_hi']:.3f}] on {b['trades']} trades.
"""
(C.OUT / "RESULTS.md").write_text(txt)
