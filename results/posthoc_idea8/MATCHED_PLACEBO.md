# Post-hoc Idea 8: matched-games placebo comparison

## 2026-10-04 04:13 ET

**Label: post-hoc diagnostic, computed after training results were seen; not a variant.** Decided after the Idea 8 training results were seen. Source: results/posthoc_idea8/training_trades.csv (committed 1e241e6); script scripts/posthoc_idea8_matched.py (run at HEAD 9c35d9e). No strategy rerun, no new fills; SPEC.md, training_results.csv and TRAINING.md are unchanged. Matched set = games where both the fade and the follow (placebo) leg entered at that x. ROC CIs: game bootstrap, 2,000 reps, seed 20261004 (paired difference resamples games).

Kalshi direct, costs x1:

| x | matched games | leg | trades | ROC | 95% CI | c/contract | win rate | mean fill | total P&L $ |
|---|---|---|---|---|---|---|---|---|---|
| 0.2 | 766 | fade | 766 | -0.1049 | [-0.1812, -0.0263] | -3.78 | 0.511 | 0.535 | -289.47 |
| 0.2 | 766 | follow | 766 | -0.0771 | [-0.1623, 0.0143] | -2.18 | 0.489 | 0.497 | -167.13 |
| 0.4 | 519 | fade | 519 | -0.1541 | [-0.2452, -0.0618] | -5.97 | 0.495 | 0.542 | -309.91 |
| 0.4 | 519 | follow | 519 | -0.0276 | [-0.1447, 0.0900] | 0.10 | 0.505 | 0.490 | 5.32 |
| 0.6 | 273 | fade | 273 | -0.1372 | [-0.2578, -0.0128] | -5.09 | 0.526 | 0.564 | -138.94 |
| 0.6 | 273 | follow | 273 | -0.0659 | [-0.2244, 0.1173] | -0.55 | 0.474 | 0.467 | -14.97 |

Paired difference, fade minus follow, per matched game (Kalshi direct, costs x1):

| x | games | mean ROC diff | 95% CI | mean P&L diff $ per game | 95% CI |
|---|---|---|---|---|---|
| 0.2 | 766 | -0.0278 | [-0.1788, 0.1206] | -0.160 | [-0.784, 0.467] |
| 0.4 | 519 | -0.1266 | [-0.3132, 0.0610] | -0.607 | [-1.319, 0.107] |
| 0.6 | 273 | -0.0713 | [-0.3302, 0.1869] | -0.454 | [-1.403, 0.507] |

Fade leg on the matched games, other fee lines (x2 ROC rebuilt as pnl_x2 / (fill_x2 x 10 + fee_x2) from committed columns):

| x | line | trades | ROC | 95% CI | c/contract | total P&L $ |
|---|---|---|---|---|---|---|
| 0.2 | Webull, x1 | 766 | -0.1161 | [-0.1914, -0.0399] | -4.40 | -337.30 |
| 0.2 | Kalshi direct, x2 | 766 | -0.1494 | [-0.2208, -0.0771] | -6.14 | -470.24 |
| 0.2 | Webull, x2 | 766 | -0.1684 | [-0.2380, -0.0999] | -7.40 | -567.10 |
| 0.4 | Webull, x1 | 519 | -0.1659 | [-0.2541, -0.0765] | -6.64 | -344.80 |
| 0.4 | Kalshi direct, x2 | 519 | -0.1955 | [-0.2786, -0.1102] | -8.28 | -429.84 |
| 0.4 | Webull, x2 | 519 | -0.2154 | [-0.2948, -0.1338] | -9.64 | -500.50 |
| 0.6 | Webull, x1 | 273 | -0.1500 | [-0.2669, -0.0290] | -5.84 | -159.40 |
| 0.6 | Kalshi direct, x2 | 273 | -0.1777 | [-0.2894, -0.0621] | -7.31 | -199.66 |
| 0.6 | Webull, x2 | 273 | -0.1995 | [-0.3064, -0.0871] | -8.84 | -241.30 |

Tie-back to the full table (training_results.csv): trades per leg, games dropped from each leg because the other leg did not enter, matched games:

| x | fade trades (full) | fade excluded | follow trades (full) | follow excluded | matched |
|---|---|---|---|---|---|
| 0.2 | 792 | 26 | 881 | 115 | 766 |
| 0.4 | 540 | 21 | 626 | 107 | 519 |
| 0.6 | 290 | 17 | 371 | 98 | 273 |

