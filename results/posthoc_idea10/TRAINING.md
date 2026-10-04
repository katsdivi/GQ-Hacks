# Post-hoc Idea 10: training results

**post-hoc, exploratory; selected on training only.** Spec 3a02690; script and tests d5232d7. Holdout not run (only on "run idea10 holdout").

Selected s (training rule: highest mean net c/contract, Kalshi direct, costs x1, fade, >= 200 trades): **0.10**. Every s and both legs lose; the selection is mechanical.

## Kalshi direct, costs x1

| s | leg | trades | games | exits at settlement | net c/contract [95% CI] | gross c/contract | per-trade Sharpe | daily Sharpe x365 (game days) | max DD $ | skew (trade) | excl top 5 net c/contract | P&L $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.03 | fade | 2533 | 862 | 36 | -4.42 [-4.67, -4.14] | -1.93 | -0.673 | -12.6 | 1118.67 | 1.38 | -4.53 | -1118.67 |
| 0.03 | placebo | 2540 | 864 | 38 | -4.28 [-4.56, -4.00] | -1.80 | -0.622 | -13.6 | 1087.58 | -1.26 | -4.39 | -1087.58 |
| 0.05 | fade | 1586 | 674 | 29 | -4.30 [-4.69, -3.92] | -1.69 | -0.578 | -12.4 | 681.61 | 2.32 | -4.48 | -681.61 |
| 0.05 | placebo | 1601 | 682 | 29 | -4.57 [-4.97, -4.15] | -1.98 | -0.572 | -13.7 | 731.28 | -2.32 | -4.72 | -731.28 |
| 0.1 | fade | 577 | 368 | 19 | -3.89 [-4.56, -3.20] | -1.23 | -0.454 | -11.9 | 224.39 | 2.33 | -4.31 | -224.39 |
| 0.1 | placebo | 588 | 378 | 19 | -5.03 [-5.84, -4.22] | -2.40 | -0.519 | -15.1 | 295.86 | -2.06 | -5.32 | -295.84 |

Webull and costs x2 lines: training_results.csv (all worse).

## Skips

| item | count |
|---|---|
| games | 1267 |
| games_used | 1265 |
| game_skip: missing market (KXNCAAFGAME-25AUG30LAMUNT-UNT: no rows in the trade file) | 1 |
| game_skip: team mapping | 1 |
| event_skip: no wallclock | 60 |
| event_skip: no single scoring side | 125 |
| event_skip: outside window | 1258 |
| event_skip: no pre/post price | 2725 |
| events_in_window_study | 9733 |

## Event study (descriptive, not a variant): scoring team's own YES price move from the pre-price, cents

| play type | events | n | median +10 s | +30 s | +60 s | +180 s | +300 s | mean +60 s | mean +180 s | mean +300 s |
|---|---|---|---|---|---|---|---|---|---|---|
| field-goal | 2962 | 2620 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.88 | 0.76 | 0.74 |
| safety | 54 | 45 | 0.0 | 0.0 | 0.0 | 1.0 | 1.0 | 2.22 | 2.84 | 2.84 |
| touchdown | 6717 | 5427 | 0.0 | 1.0 | 2.0 | 2.0 | 2.0 | 3.33 | 3.94 | 3.85 |
| all | 9733 | 8092 | 0.0 | 1.0 | 1.0 | 1.0 | 1.0 | 2.53 | 2.91 | 2.84 |

Reading: the mean move keeps growing from +60 s to +180 s after touchdowns (3.33 to 3.94 c), so there is no overreaction to fade at this horizon. Both fade and follow lose about the 2 cents of crossing (entry + 1 c, exit - 1 c) plus fees. Gross c/contract includes those 2 cents.

## ESPN wallclock defects (diagnostic, report only; rule not changed)

See training_wallclock_defects.md. 783 of 11,006 scoring events (260 outside [kickoff, kickoff + 6 h], 562 out of order with neighbouring plays), in 343 games. Trades in those games carry 13 to 17% of each leg's P&L, which is about their share of trades (14 to 16%).
