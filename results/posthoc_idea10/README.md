# posthoc_idea10

## Close-out (2026-10-04 04:28 ET)

**Label: post-hoc, exploratory; selected on training only.**

Closed on training: no variant positive; holdout not run.

- Best net c/contract of any row is -3.89 (s 0.10, fade, Kalshi direct, costs x1). Fade and placebo both lose at every s.
- Event study (descriptive, not a variant): median Kalshi move of the scoring team's own price, cents, after ESPN scoring plays (events with a pre-price):

| play type | n | +10 s | +30 s | +60 s | +180 s | +300 s |
|---|---|---|---|---|---|---|
| touchdown | 5427 | 0 | 1 | 2 | 2 | 2 |
| field goal | 2620 | 0 | 0 | 0 | 0 | 0 |
| safety | 45 | 0 | 0 | 0 | 1 | 1 |
| all | 8092 | 0 | 1 | 1 | 1 | 1 |

  Prices keep rising after touchdowns through +300 s; no overreaction to fade at these horizons. Source: training_event_study.csv. Variants: 3.

## Per-trade files (not in git)

2026-10-04: per-trade files with Kalshi prices or timestamps are kept on disk but untracked (no vendor data in git): training_trades.csv . Regenerate them (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea10.py   # needs the ESPN summary cache
```
