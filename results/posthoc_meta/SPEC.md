# Post-hoc meta-model over base strategies (walk-forward, training only)

**Label: post-hoc, exploratory; meta-model over strategies already seen to fail on training; walk-forward on training only.**

Written and committed 2026-10-04 (ET) before any model touches real data. Every base strategy below has
already been run on training and seen to lose (results/posthoc/SUMMARY.md); this test asks whether a model that
learns, walk-forward, which candidates tend to win can pick a profitable subset. Variants: 2 (M1, M2).

## Candidates (training only, kickoff < 2026-08-01; one row per entered base trade)

Settings fixed in advance (training-selected, or the one listed); nothing is chosen by peeking at meta results.

| strategy id | source (on disk, gitignored) | sha256 (first 16) | setting, legs |
|---|---|---|---|
| A | staleline/out/strategy_a/rows.parquet | e0b1a2a3fe8b7056 | theta 0.80, favorite leg, entered |
| B | staleline/out/strategy_b/trades.parquet | 9bda2e71484354c2 | selected k 0.05, m 10, T 300 (results/numbers.json B.selected_setting), filled round trips |
| I4 | wt-idea4/results/posthoc_idea4/training_trades.csv | 6d21bf086ccc658a | theta 0.90, favorite and placebo |
| I7 | wt-idea7/results/posthoc_idea7/training_trades.csv | 50edecde754da08f | k 0.02, signal and placebo, entered |
| I8 | wt-idea8/results/posthoc_idea8/training_trades.csv | c889b3c3df54d03b | x 0.2, fade and follow |
| I9 | wt-idea9/results/posthoc_idea9/training_trades.csv | d6832e9615fcbdab | k 0.10, delay 60, signal and placebo |
| I10 | wt-idea10/results/posthoc_idea10/training_trades.csv | d1ebc7c4dd3d9918 | s 0.10, fade and placebo, entered (round trips) |
| I12 | wt-idea12/results/posthoc_idea12/training_trades.csv | bfc0a994dabed223 | k 0.03, signal and placebo, entered |
| I13 | wt-idea13/results/posthoc_idea13/training_trades.csv | eca56d1645bd496c | e 0.02, signal and placebo, entered |

Excluded: Idea 3 (invalid, lookahead), Idea 6 winner leg (invalid, bad ESPN end times), Ideas 1, 2, 11
(holdout-period data, no training), T&S laggard (holdout-period data). A strategy "cell" = strategy id + leg.
B dominates the candidate count (several round trips per game); its candidates are kept as the base strategy
produced them (B already allows sequential positions per game). At most one position per game per strategy cell
holds for every hold-to-settlement strategy as produced; the meta-model only filters, never adds positions.

Net P&L per candidate = the base file's pnl_direct (Kalshi direct fees, costs x1), in dollars for 10 contracts.
Capital per candidate (for ROC) = entry price x 10 + fee_direct (for B direction -1, entry price is
1 - entry_px, the away YES cost; for B and I10 this is an approximation for round trips). ROC = net / capital.

## Features (only information known at the candidate's own decision time t)

Decision time t: the file's decision timestamp (t_ns; B entry_dec_ns; A: ESPN kickoff - 5 min).
- strategy cell (one-hot);
- entry fill price (fill / entry / entry_px oriented to the bought team);
- signal strength: I4 signal_px, I7 g, I8 |I|, I9 g, I10 m, I12 g, I13 gap, B |d_at_entry_cents|/100, A 0;
- league (CFB flag); NFL preseason flag (NFL, ET date before 2025-09-04);
- minutes from ESPN kickoff to t;
- ET day of week (one-hot);
- agreement: among OTHER candidates in the same game with decision time strictly before t, the count on the
  same team and the count on the opposite team (team side from the game id's away/home codes; unknown = 0);
- trailing win rate of the candidate's strategy cell from candidates whose ET date is strictly before t's ET date
  (treated as settled), shrunk (wins + 1) / (n + 2).
Never used: payout, settlement, exit prices, later prices, P&L of the same game, or anything after t.

## Target and models

Target: net P&L > 0. Secondary: ridge regression on net P&L (alpha 1.0), reported as out-of-sample correlation
and as the P&L of taking predictions > 0.
- M1: L2 logistic regression, C = 1.0, features standardized on the training weeks only.
- M2: sklearn is not installed in .venv-run (checked 05:17 ET), so the fixed fallback is a depth-3 decision tree
  (Gini, min 30 samples per leaf), implemented in numpy, seed 20261004 not needed (deterministic).

Decision rule (fixed): take a candidate if predicted P(net > 0) > its break-even:
- hold-to-settlement candidates (A, I4, I7, I8, I9, I12, I13): break-even = fill + fee_direct / 10;
- round-trip candidates (B, I10): break-even = 0.5 + fee_direct / 10.

## Evaluation (walk-forward by ET calendar week, Monday start, training only)

For each week w: fit on all candidates in weeks before w, predict week w. Start at the first week with at least
6 earlier weeks containing candidates. No holdout data is used. A holdout version would require every base
strategy run on its holdout first; it runs only on the exact phrase "run meta holdout" plus each base idea's
holdout phrase.

Benchmarks on the same evaluation weeks: (a) take all candidates; (b) the single best strategy cell chosen
walk-forward (highest trailing mean ROC over weeks before w, at least 20 trades), all its week-w candidates;
(c) no trade (0).

Metrics per model and benchmark: trades, mean ROC with game-bootstrap 95% CI (2,000 reps, seed 20261004), net
c/contract, hit rate (net > 0) vs mean break-even, daily P&L on game days (ET date of t): daily Sharpe and x365
(daily x sqrt 365), max drawdown, ROC excluding the top 5 games by P&L, per-strategy-cell breakdown of picks.
Descriptive "what gets what right": per strategy cell and per league, hit rate vs mean break-even and mean net,
on the evaluation weeks.

## Scope note

An MCP server is a serving interface, not a modelling choice; it is out of scope for this test.
