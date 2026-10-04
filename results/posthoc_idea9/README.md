# posthoc_idea9

## Close-out (2026-10-04 04:28 ET)

**Label: post-hoc, exploratory; ESPN data used as a signal only; selected on training only.**

Closed on training: no variant positive; holdout not run.

- Highest ROC point estimate of any row (any leg, fee line, cost level) is -0.019 (k 0.10, delay 60 s, signal leg, Kalshi direct, costs x1; CI includes 0).
- Brier score at entry, ESPN vs Kalshi, on the traded games: Kalshi lower than ESPN in all 8 rows.

| k | delay (s) | leg | trades | Brier ESPN | Brier Kalshi |
|---|---|---|---|---|---|
| 0.05 | 60 | signal | 1015 | 0.2006 | 0.1907 |
| 0.05 | 60 | placebo | 1039 | 0.1945 | 0.1879 |
| 0.10 | 60 | signal | 841 | 0.2196 | 0.2085 |
| 0.10 | 60 | placebo | 896 | 0.2094 | 0.2033 |
| 0.05 | 180 | signal | 1025 | 0.1984 | 0.1887 |
| 0.05 | 180 | placebo | 1049 | 0.1916 | 0.1839 |
| 0.10 | 180 | signal | 918 | 0.2200 | 0.2056 |
| 0.10 | 180 | placebo | 947 | 0.2107 | 0.2024 |

- Caveat: ESPN wallclocks are unreliable on many games (584 of 1,087 traded games flagged); see "Wallclock diagnostic" in TRAINING.md and training_wallclock_diag.csv. Variants: 4.

## Per-trade files (not in git)

2026-10-04: per-trade files with Kalshi prices or timestamps are kept on disk but untracked (no vendor data in git): training_trades.csv . Regenerate them (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea9.py   # needs ../wt-idea6/data/espn_raw/ or its own data/espn_raw/
```
