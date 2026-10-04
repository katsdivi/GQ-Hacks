# Post-hoc meta-model: results (walk-forward, training only)

**Label: post-hoc, exploratory; meta-model over strategies already seen to fail on training; walk-forward on training only.**
Run once, 2026-10-04 05:20 ET. Spec 92f29b6 (05:18:40 ET), script and tests 3da957a (05:20:10 ET, 6 synthetic tests passed).
Variants: 2 (M1, M2). Holdout not run (needs "run meta holdout" plus every base idea's holdout run).

## Data

18,565 training candidates from 16 strategy cells (candidates_per_cell.csv; B is 9,242 of them). Walk-forward by ET
week: 19 evaluation weeks (2025-09-08 to 2026-01-12), 17,216 evaluation candidates. No input file missing.

## Walk-forward table (Kalshi direct, costs x1; ROC CI = game bootstrap, 2,000 reps, seed 20261004)

| book | trades | games | ROC [95% CI] | net c/contract | P&L | hit rate vs break-even | Sharpe daily / x365 | max DD | ROC excl top 5 |
|---|---|---|---|---|---|---|---|---|---|
| M1 logistic (C 1.0) | 2,463 | 938 | -0.121 [-0.222, -0.019] | -1.79 | -$440 | 0.321 vs 0.341 | -0.16 / -3.08 | $488 | -0.161 |
| M2 tree (depth 3) | 2,751 | 964 | -0.154 [-0.225, -0.077] | -3.02 | -$832 | 0.380 vs 0.410 | -0.34 / -6.50 | $832 | -0.178 |
| secondary: ridge pred > 0 | 935 | 606 | -0.070 [-0.189, +0.063] | -3.15 | -$295 | 0.441 vs 0.483 | -0.23 / -4.31 | $346 | -0.154 |
| benchmark a: all candidates | 17,216 | 1,023 | -0.095 [-0.110, -0.080] | -3.27 | -$5,626 | 0.319 vs 0.531 | -0.64 / -12.25 | $5,626 | -0.098 |
| benchmark b: best cell walk-forward | 514 | 514 | -0.112 [-0.203, -0.014] | -4.41 | -$227 | 0.520 vs 0.564 | -0.24 / -4.63 | $250 | -0.167 |
| benchmark c: no trade | 0 | 0 | 0 | 0 | $0 | | | | |

Both meta-models lose, with 95% CIs below zero. Neither beats "no trade". M1 loses less per contract than taking
everything, mainly because it avoids most of B (31 of 9,039 B candidates taken), not because it finds winners.

## Why a high AUC does not mean edge

Out-of-sample AUC for P(net > 0) is 0.77 (M1) and 0.77 (M2), but the ridge regression on net P&L has an
out-of-sample correlation of 0.015. The classifiers mostly learn the entry price (a 0.90 favorite usually wins), which
the market has already priced: hit rate stays below the fee-inclusive break-even in every book. Predicting who wins
is easy; predicting who wins MORE often than the price says is what pays, and nothing here does.

## What gets what right (evaluation weeks, all candidates; hit rate vs break-even)

Hold-to-settlement cells: break-even = fill + fee / 10. Round-trip cells (B, I10): break-even = 0.5 + fee / 10, so
their hit rate is not comparable (most round trips close at a small loss); read their mean ROC instead.

| cell | trades | hit rate | break-even | hit minus break-even | mean ROC | P&L |
|---|---|---|---|---|---|---|
| A favorite (theta 0.80) | 253 | 0.913 | 0.901 | +0.013 | +0.015 | +$31.64 |
| I7 placebo (k 0.02) | 271 | 0.561 | 0.539 | +0.022 | -0.008 | +$58.60 |
| I7 signal | 19 | 0.526 | 0.509 | +0.017 | -0.124 | +$3.23 |
| I9 signal | 723 | 0.450 | 0.457 | -0.007 | -0.016 | -$56.92 |
| I12 signal | 814 | 0.499 | 0.509 | -0.011 | -0.046 | -$80.83 |
| I4 favorite | 957 | 0.889 | 0.907 | -0.018 | -0.016 | -$165.26 |
| I4 placebo | 995 | 0.108 | 0.134 | -0.026 | -0.175 | -$264.07 |
| I8 placebo (follow) | 723 | 0.447 | 0.474 | -0.027 | -0.143 | -$196.74 |
| I8 fade | 673 | 0.522 | 0.555 | -0.034 | -0.090 | -$228.46 |
| I12 placebo | 853 | 0.496 | 0.548 | -0.052 | -0.133 | -$445.39 |
| I9 placebo | 764 | 0.545 | 0.601 | -0.056 | -0.124 | -$423.67 |
| I13 placebo | 84 | 0.512 | 0.587 | -0.075 | -0.156 | -$62.95 |
| I13 signal | 20 | 0.350 | 0.479 | -0.129 | -0.370 | -$25.73 |
| B signal (round trip) | 9,039 | 0.185 | 0.528 | n/a | -0.097 | -$3,318.52 |
| I10 fade (round trip) | 509 | 0.145 | 0.527 | n/a | -0.155 | -$195.83 |
| I10 placebo (round trip) | 519 | 0.185 | 0.526 | n/a | -0.084 | -$254.96 |
| league CFB | 12,631 | | | | -0.087 | -$3,994.33 |
| league NFL | 4,585 | | | | -0.087 | -$1,631.53 |

Only A favorite and I7 placebo beat their break-even on these weeks; both were already in the training-positive
book or near zero, and A favorite lost on the holdout (results/posthoc/positive_book). The meta-models do lean on A
favorite (M1 114 picks, +$31.91; M2 91 picks, +$40.21), but their other picks lose more (picks_by_cell.csv).

## Leakage checks and caveats

- Walk-forward fits use weeks before w only (asserted in code and tested). Features are limited to the SPEC list;
  a planted future column is ignored (tested). Agreement counts and trailing win rates use strictly earlier data.
- Mild bias in favor of the meta-model: each base setting was selected on all of training (not walk-forward), so
  the candidate pool is already slightly fitted. The meta-model still loses.
- ROC for round trips (B, I10) uses entry price x 10 + fee as capital, an approximation.

## Serving note

An MCP server could expose the per-cell "what gets what right" table and the model score as a read-only tool for
the demo; it would not change these numbers.
