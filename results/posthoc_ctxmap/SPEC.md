# Post-hoc context map: which idea is right in which situation

**Label: post-hoc, exploratory; context map over strategies already seen; walk-forward on training only; holdout not run.**

Written 2026-10-04 05:24 ET, committed and pushed before any map is computed. No model fitting, no regression.

## Inputs

- Candidate pool: the posthoc-meta pool, `../wt-meta/results/posthoc_meta/candidates.csv` (gitignored), built by
  `scripts/posthoc_meta.py` (script commit 3da957a, outputs commit 07738c9 on posthoc-meta), sha256
  a9ff5574a0457f79a557ea834a51e3821f991ba78e247dfa613216a64d108c33, 18,565 rows. Regenerate on posthoc-meta with
  `PYTHONPATH=.:scripts python scripts/posthoc_meta.py`.
- Idea-legs (column `cell`, 16): A:favorite, B:signal, I4:favorite, I4:placebo, I7:signal, I7:placebo, I8:fade,
  I8:placebo, I9:signal, I9:placebo, I10:fade, I10:placebo, I12:signal, I12:placebo, I13:signal, I13:placebo.
  Same settings and same Kalshi direct net P&L (`pnl`, dollars per 10-contract trade, costs x1) and ROC (`roc`)
  definitions as posthoc-meta. Excluded as invalid or not training: Idea 3, Idea 6 winner leg, Ideas 1, 2, 11.
- Net c/contract of a candidate = pnl / 10 x 100.

## Contexts (18, all known at the candidate's own decision time)

league (CFB, NFL) x phase x entry price band:
- phase from `min_from_ko` (minutes from ESPN kickoff to decision t): pre-game < 0; early in-game 0 to 90
  (0 <= m <= 90); late in-game > 90;
- band from the candidate's own fill price `fill`: < 0.35; 0.35 to 0.65 (inclusive); > 0.65.

Only columns used: cell, game_id, week, date, league, min_from_ko, fill, pnl, roc, y, breakeven. Nothing else.

## Map, walk-forward by ET week

- Weeks: posthoc-meta's `week` column (ET Monday); evaluation weeks = all weeks after the first 6 (same weeks as
  posthoc-meta).
- For evaluation week w and context x, each idea-leg's score = mean net c/contract over its candidates in x from
  weeks strictly before w. Eligible if it has >= N such past trades and score > 0.
- In week w, context x: trade only the candidates of the single best eligible idea-leg (highest score; tie ->
  more past trades; then alphabetical cell name). None eligible: no trade in x that week.
- One position per game per idea-leg (as the base strategies already are; duplicates, if any, keep the earliest t).
- N in {20, 50}: 2 variants. Nothing else tuned.

## Benchmarks (same weeks)

Take every candidate; best single idea-leg overall walk-forward (highest past mean net c/contract with >= 20 past
trades, re-chosen each week); no trade.

## Metrics per book

trades; ROC mean with game-bootstrap 95% CI (2,000 reps, seed 20261004; game-level resample, ratio of sums as in
posthoc-meta); net c/contract; win rate vs mean break-even on hold-to-settlement legs only (excludes B and Idea 10
round trips); daily P&L on game days, daily Sharpe and x365; max DD; worst day; ROC and P&L excluding the top 5
games; share of evaluation weeks with any trade; breakdown by context and idea-leg chosen; stability = number of
(context, consecutive week pair) where the chosen idea-leg changes, out of pairs where a choice existed in both.

## Descriptive only

Full-training context map (best idea-leg per context on ALL training weeks, with trades and c/contract). In-sample;
not a result.

## Holdout

Not run. A holdout version needs every base idea run on holdout and the exact phrase "run ctxmap holdout".

## Caveat fixed in advance

The base settings in the pool were chosen on all of training, so the pool is mildly fitted in the map's favour.

## Records

Variants: 2 (N = 20, 50). No experiments/variants.csv write here.
