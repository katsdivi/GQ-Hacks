# Post-hoc Idea 13: training results

**Label: post-hoc, exploratory; sportsbook closing line used as a signal only; selected on training only.**
Spec: SPEC.md (03ab9a5). Script and tests: 4fea143 (9 synthetic tests passed). Run 2026-10-04 ~04:40 ET,
scripts/posthoc_idea13.py, 331 training NFL games. Holdout not run (only on "run idea13 holdout").

Limitation: nflverse line timestamps are not published; a line captured after kickoff would be lookahead.

## Selected e (training rule: >= 40 signal trades, highest Kalshi direct ROC)

**None.** No e reaches 40 signal trades (23, 1, 0). Under the rule, nothing is selected.

## Games

331 NFL training games: 282 evaluated, 49 skipped for no nflverse line (all preseason; nflverse has no preseason
games). No game skipped for a missing Kalshi price, Strategy A exclusion, fill, or void.

## Kalshi vs the no-vig closing line, all 282 games

- Brier score (home win, Kalshi settlement): nflverse no-vig p 0.2111, Kalshi K at kickoff 0.2113. Equivalent.
- |p_home - K_home|: median 0.012, p90 0.028. Kalshi tracks the closing line within about a cent.
- K_home + K_away (last trades): median 1.01, p10 1.01, p90 1.02. Kalshi's two last prices sum above 1 by about a
  cent, so K - p tends to be positive: the placebo (Kalshi rich) qualifies about 4 times as often as the signal.

## Table (costs x1; full grid with x2, Webull, skew, excl. top 5 in training_results.csv)

| e | leg | trades | wins | mean fill | win rate | mean gap | ROC direct [95% CI] | c/contract | Sharpe x365 | max DD | excl top 5 ROC |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.02 | signal | 23 | 7 | 0.458 | 0.304 | 0.026 | -0.452 [-0.791, -0.085] | -16.97 | -2.25 | $39.04 | -0.873 |
| 0.02 | placebo | 92 | 49 | 0.574 | 0.533 | 0.028 | -0.123 [-0.301, +0.055] | -5.63 | -1.40 | $88.06 | -0.234 |
| 0.04 | signal | 1 | 0 | 0.370 | 0.000 | 0.047 | -1.000 | -38.70 | -1.43 | $3.87 | n/a |
| 0.04 | placebo | 6 | 4 | 0.578 | 0.667 | 0.047 | +0.032 [-0.517, +0.577] | +7.22 | +0.54 | $9.62 | -1.000 |
| 0.06 | signal | 0 | | | | | | | | | |
| 0.06 | placebo | 0 | | | | | | | | | |

Webull and costs x2 are worse in every populated row. With 23 signal trades the e = 0.02 CI is wide; read it as
"no evidence of an edge", not as a reliable loss estimate.

## Reading

On training, Kalshi's last price at kickoff and the no-vig closing moneyline are almost the same forecast (Brier
0.2113 vs 0.2111; median gap 1.2 cents). Gaps of 4 cents or more are rare (7 games either way), and the 23 games
with a 2-cent cheap-vs-line Kalshi side lost money. No variant qualifies for selection; nothing to carry to the
holdout.

Per-trade and per-game files (training_trades.csv, training_games.csv) are on disk only (README.md). No
experiments/variants.csv rows written (3 variants held for the later combined commit).
