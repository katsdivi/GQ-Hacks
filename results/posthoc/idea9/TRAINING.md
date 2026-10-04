# Post-hoc Idea 9: training results

**post-hoc, exploratory; ESPN data used as a signal only; selected on training only.**

Spec df80d2c (04:03:47 ET), script and tests 8616fd4 (12 synthetic tests passed). One training run, 1,267 games,
04:14 to 04:15 ET. Full table: training_results.csv; trades: training_trades.csv. Holdout not run.

## Kalshi direct, costs x1

| k | delay s | leg | trades | ROC [95% CI] | c/contract | win rate | mean fill | mean g | Brier ESPN | Brier Kalshi | Sharpe x365 | max DD $ | ROC excl top 5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.05 | 60 | signal | 1015 | -0.077 [-0.170, +0.023] | -3.47 | 0.410 | 0.431 | +0.089 | 0.201 | 0.191 | -4.06 | 372.78 | -0.139 |
| 0.05 | 60 | placebo | 1039 | -0.088 [-0.145, -0.025] | -3.01 | 0.555 | 0.572 | -0.094 | 0.194 | 0.188 | -3.13 | 360.79 | -0.114 |
| 0.10 | 60 | signal | 841 | -0.019 [-0.111, +0.075] | -0.97 | 0.437 | 0.432 | +0.140 | 0.220 | 0.209 | -1.05 | 139.72 | -0.065 |
| 0.10 | 60 | placebo | 896 | -0.108 [-0.168, -0.040] | -4.98 | 0.555 | 0.591 | -0.139 | 0.209 | 0.203 | -4.44 | 451.67 | -0.137 |
| 0.05 | 180 | signal | 1025 | -0.136 [-0.219, -0.055] | -3.90 | 0.401 | 0.426 | +0.094 | 0.198 | 0.189 | -4.25 | 420.93 | -0.170 |
| 0.05 | 180 | placebo | 1049 | -0.082 [-0.142, -0.019] | -2.78 | 0.565 | 0.580 | -0.099 | 0.192 | 0.184 | -2.92 | 302.29 | -0.115 |
| 0.10 | 180 | signal | 918 | -0.030 [-0.117, +0.065] | -1.28 | 0.415 | 0.413 | +0.138 | 0.220 | 0.206 | -1.57 | 158.15 | -0.071 |
| 0.10 | 180 | placebo | 947 | -0.085 [-0.149, -0.019] | -4.36 | 0.564 | 0.593 | -0.141 | 0.211 | 0.202 | -3.91 | 418.78 | -0.117 |

Selected by the training rule: k = 0.10, delay = 60 s (ROC -0.019, CI includes 0; costs x2 -0.083; Webull -0.037).
No variant has a positive ROC point estimate on any fee line. Kalshi's price at entry has a lower Brier score
than ESPN's probability in all 8 rows: on the traded games Kalshi was better calibrated than ESPN.

## Wallclock diagnostic (not a variant; training_wallclock_diag.csv)

Of 1,087 traded games, 584 have a suspect ESPN wallclock (a play more than 5 min earlier than the previous play:
367; outside [kickoff, kickoff + 6 h]: 11; both: 206). Mostly CFB, all play types (rush, timeout, pass). Selected
variant: 432 of 841 trades are in flagged games, P&L -2.56 of -81.83 (unflagged ROC -0.024). Because known-time =
wallclock + delay, a wallclock that is too early makes ESPN data usable before it existed (possible lookahead)
and one too late delays it. Not patched; results above include these games.
