# Post-hoc Idea 6: training results

**Label: post-hoc, exploratory; designed and selected on training only.** Spec: SPEC.md (7c78c2c; 5-min fill
window note 9c6c4b9, before this run). Run 2026-10-04 04:12 ET, scripts/posthoc_idea6.py, 1,267 training games.
Holdout not run (only on "run idea6 holdout").

## Selected D (training rule: >= 50 winner trades, highest direct ROC)

**None.** No D reaches 50 winner trades (20, 14, 14). Under the rule, nothing is selected.

## Headline: the winner-leg numbers are NOT a valid edge (bad E), read before the table

All winner trades win, at a mean fill of about 0.73. Of the 20 games with a winner trade, 15 have ESPN plays whose
wallclock is 15 to 162 minutes AFTER the end-marker wallclock E, so ESPN's marker wallclock is wrong (too early)
and the fills happen while the game is still being played, with the final score already known. That is lookahead,
not edge.

- 10 NFL preseason games (Aug 8 to 16, 2025): "END GAME" wallclock is about 23:59 UTC on the kickoff date, about
  1 h after kickoff; the real last plays are about 02:00 to 02:40 UTC. Looks like a placeholder timestamp.
- 5 CFB games (byu_ecu, haw_afa, wku_del, jvst_shsu, ariz_hou): "End of 4th Quarter" wallclock 15 to 52 min
  before the last real play.
- 5 games have E equal to the latest play wallclock (gb_ind, txst_utsa, la_phi, psu_iowa, pit_det; fills 0.98 to
  0.69). Not shown bad, not shown clean.
- Separately, 52 late-night CFB games have E about 17 to 21 h BEFORE kickoff (ESPN wallclock date appears off by
  one day). Those never filled (no Kalshi trades at t), so they only inflate "no post-decision trade".

So the spec's end-marker rule does not by itself guarantee a valid E. Not patched (spec unchanged); a fix (e.g.
E = max(marker wallclock, every play wallclock), and E between kickoff + 2 h and kickoff + 6 h) needs Divi's call.

## Table (Kalshi direct fees; costs x1, and x2 for the winner leg)

| D_s | leg | costs | trades | losses | mean_fill | roc_mean | roc_ci_lo | roc_ci_hi | cents_per_contract | pnl_total | sharpe_x365 | sharpe_daily | max_drawdown | worst_trade | excl_top5_roc | median_fill_delay_s | capacity_median |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 60 | winner | x1 | 20 | 0 | 0.748 | 0.375 | 0.246 | 0.515 | 24.000 | 48.000 | 3.543 | 0.955 | 0.000 | 0.180 | 0.219 | 14.910 | 46010.000 |
| 60 | winner | x2 | 20 | 0 | 0.758 | 0.329 | 0.214 | 0.456 | 21.850 | 43.700 | 3.505 | 0.935 | 0.000 | 0.080 | 0.189 | 14.910 | 46010.000 |
| 60 | placebo | x1 | 547 | 547 | 0.030 | -1.000 | -1.000 | -1.000 | -3.247 | -177.620 | -8.388 | -0.569 | 177.620 | -6.070 | -1.000 | 14.517 | 1402.000 |
| 180 | winner | x1 | 14 | 0 | 0.705 | 0.454 | 0.297 | 0.631 | 28.136 | 39.390 | 3.187 | 1.167 | 0.000 | 0.560 | 0.238 | 15.978 | 45552.000 |
| 180 | winner | x2 | 14 | 0 | 0.715 | 0.402 | 0.261 | 0.561 | 25.857 | 36.200 | 3.172 | 1.154 | 0.000 | 0.420 | 0.207 | 15.978 | 45552.000 |
| 180 | placebo | x1 | 269 | 269 | 0.036 | -1.000 | -1.000 | -1.000 | -3.904 | -105.030 | -6.332 | -0.516 | 105.030 | -6.170 | -1.000 | 20.637 | 787.000 |
| 600 | winner | x1 | 14 | 0 | 0.731 | 0.415 | 0.249 | 0.615 | 25.664 | 35.930 | 3.044 | 1.049 | 0.000 | 0.460 | 0.203 | 16.302 | 44077.000 |
| 600 | winner | x2 | 14 | 0 | 0.741 | 0.366 | 0.217 | 0.546 | 23.486 | 32.880 | 3.021 | 1.032 | 0.000 | 0.340 | 0.176 | 16.302 | 44077.000 |
| 600 | placebo | x1 | 49 | 49 | 0.102 | -1.000 | -1.000 | -1.000 | -10.739 | -52.620 | -3.376 | -0.473 | 52.620 | -5.980 | -1.000 | 61.258 | 2773.000 |

Webull lines and all columns (games with any trade after t, skew, excl. top 5 P&L, median time E to last trade,
capacity mean) are in training_results.csv. Trades: training_trades.csv. Per-game E, winner, prices: training_games.csv.
Losing winner trades: none at any D. Placebo (loser) loses every trade (547, 269, 49), as expected.

## Skips (winner leg)

| D | end/mapping skips | no post-decision trade (within 5 min) | fill at 0.99 | other excluded | traded |
|---|---|---|---|---|---|
| 60 | 202 | 391 | 653 | 1 | 20 |
| 180 | 202 | 671 | 379 | 1 | 14 |
| 600 | 202 | 998 | 52 | 1 | 14 |

## Descriptive a to d

See training_descriptive.md (counts and game id lists).
