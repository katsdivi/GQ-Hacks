# Post-hoc Idea 7: training results

**Label: post-hoc, exploratory; selected on training only.** Spec: SPEC.md (a413026). Script and tests: 6ca085d
(14 synthetic tests passed). Run 2026-10-04 about 04:40 ET, scripts/posthoc_idea7.py, training only (963 B games
= 977 minus the 14 run_strategy_b.EXCLUDED_A1 games). Holdout not run (only on "run idea7 holdout").

## Selected k (training rule: >= 100 signal trades, highest direct ROC)

**None.** Signal trades per k: 19 (k 0.02), 0 (k 0.03), 0 (k 0.05). No k reaches 100 trades.

## Table (Kalshi direct fees, costs x1; all games; ROC CI = game bootstrap, 2,000 reps, seed 20261004)

| k | leg | trades | ROC [95% CI] | c/contract | mean g | win rate vs mean fill | Sharpe x365 / daily | max DD | worst day | ROC excl top 5 | corr with A |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.02 | signal | 19 | -0.124 [-0.521, +0.292] | +1.70 | +0.020 | 0.526 vs 0.495 | +0.29 / +0.05 | $10.02 | -$6.57 | -0.545 | +0.04 |
| 0.02 | placebo | 274 | -0.015 [-0.136, +0.121] | +1.88 | -0.021 | 0.558 vs 0.526 | +1.10 / +0.09 | $36.64 | -$9.73 | -0.090 | -0.04 |
| 0.03 | signal | 0 | | | | | | | | | |
| 0.03 | placebo | 24 | -0.176 [-0.468, +0.111] | -0.43 | -0.031 | 0.583 vs 0.574 | -0.08 / -0.01 | $15.17 | -$6.47 | -0.427 | -0.14 |
| 0.05 | signal | 0 | | | | | | | | | |
| 0.05 | placebo | 1 | +0.701 | +41.20 | -0.050 | 1.000 vs 0.570 | | $0 | | | -0.17 |

Costs x2 and Webull lines: training_results.csv (e.g. k 0.02 signal ROC -0.162 x2 direct; placebo -0.064).
Orientation rule (B, 0014b1e) at t: 0 games flagged, so the "excl_flagged" lines equal "all".

## Skips (per k, both legs)

- stale or missing price (any of K_home, K_away, polymarket.com trade older than 10 min before t, or absent): 94
- no signal: signal leg 850 / 869 / 869 (k 0.02 / 0.03 / 0.05); placebo 591 / 845 / 868
- no post-decision trade within 5 min: 0 (signal), 4 (placebo, k 0.02); void/unsettled: 0
- capped 0.99 fills: 0 (signal), 1 (placebo, k 0.02)

## Surprise: the gap is structurally negative

For each game, g_home + g_away = (Q_home + Q_away) - (K_home + K_away) = 1 - (K_home + K_away). Kalshi's two
markets' last trades sum to a median 1.01 (p10 1.00, p90 1.02), so the two gaps sum to a median -0.01. On the
869 games with prices: max g has median 0.00, is >= 0.02 in 2.2% of games and never >= 0.03; min g is <= -0.02 in
32% of games. So the signal leg almost never fires and the placebo fires mostly because of the Kalshi overround,
not because the venues disagree. At kickoff - 5 min the two venues agree to within about 1 to 2 cents.
Spec not changed.

## Conclusion

No variant has a positive ROC point estimate with enough trades to select; no k selected; holdout not run.
