"""Append a Round k section to results/posthoc_costside/RESULTS.md from trials_log.csv and correction.json.

Usage: python scripts/costside_results_round.py <k> <notes.md>   (post-hoc, exploratory)
"""
import json
import sys

import pandas as pd

import costside_common as C

k, notes = int(sys.argv[1]), open(sys.argv[2]).read()
l = pd.read_csv(C.OUT / "trials_log.csv")
c = json.loads((C.OUT / "correction.json").read_text())
cols = ["trial", "trades", "roc", "roc_lo", "roc_hi", "c_per_contract", "alt_roc", "alt_c_per_contract", "excl5_pnl",
        "sharpe_x365", "holm_p"]
tab = l[l["round"] == k].sort_values("roc", ascending=False)[cols].round(4)
b = c["in_sample_best_by_roc"]
ext = "; ".join(f"{n} {v['trials']} ({v['status']})" for n, v in c["external"].items())
txt = f"""

## Round {k}

{notes.strip()}

### All Round {k} trials (primary line; alt = maker0 for maker trials, else same)

{C.md(tab)}

### Cumulative correction after Round {k}

Trials: own {c['own_trials']} + external ({ext}) = {c['cumulative_trials']}. Reality Check p for the best by t-stat
({c['best_by_t']}): {c['rc_p_best_by_t']:.3f}. DSR of that best: {c['dsr_best']:.2e} (project convention;
normal-returns version {c['dsr_best_normal_returns']:.2e}). Holm survivors at 0.05: {c['holm_survivors_005'] or 'none'}.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): {c['stop_candidates'] or 'none'}.
Stop condition met: {c['stop_condition_met']}.

IN-SAMPLE BEST (own trials), after {c['cumulative_trials']} trials, not expected to persist: {b['trial']}, ROC
{b['roc']:.3f} [{b['roc_lo']:.3f}, {b['roc_hi']:.3f}] on {b['trades']} trades.
"""
with open(C.OUT / "RESULTS.md", "a") as f:
    f.write(txt)
