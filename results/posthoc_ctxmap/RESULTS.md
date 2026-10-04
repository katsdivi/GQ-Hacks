# Post-hoc context map: results (training, walk-forward)

**Label: post-hoc, exploratory; context map over strategies already seen; walk-forward on training only; holdout not run.**

Run 2026-10-04 05:26 ET, scripts/posthoc_ctxmap.py, spec SPEC.md (7f9599e), tests 04740c7 (6 passed). Pool: posthoc-meta
candidates.csv (sha256 a9ff5574...8c33), 18,565 candidates, 16 idea-legs; 19 evaluation weeks (2025-09-08 to
2026-01-12), 17,216 evaluation candidates. Kalshi direct, costs x1.

## Walk-forward result

| book | trades | ROC [95% CI] | net c/contract | P&L | win rate vs break-even (hold legs) | Sharpe x365 | max DD | ROC excl top 5 | weeks traded |
|---|---|---|---|---|---|---|---|---|---|
| context map N=20 | 974 | -0.148 [-0.223, -0.065] | -3.52 | -$343.00 | 0.452 vs 0.487 | -4.68 | $392.62 | -0.184 | 100% |
| context map N=50 | 646 | -0.167 [-0.265, -0.060] | -4.03 | -$260.32 | 0.444 vs 0.485 | -4.72 | $278.99 | -0.218 | 89% |
| take every candidate | 17,216 | -0.095 [-0.110, -0.080] | -3.27 | -$5,625.86 | 0.510 vs 0.536 | -12.25 | $5,625.86 | -0.098 | 100% |
| best single idea-leg, walk-forward | 452 | -0.069 [-0.175, +0.042] | -2.30 | -$103.75 | 0.524 vs 0.547 | -2.11 | $143.62 | -0.136 | 95% |
| no trade | 0 | 0 | | $0 | | | | | 0% |

**Verdict: negative.** Both context-map variants lose, with ROC CIs entirely below zero, and do worse than both
"no trade" and the simpler "best single idea-leg" benchmark. The win rate of the chosen trades is below their
break-even in both variants.

## What the map chose, and stability

- N=20: 16 of 18 contexts traded at some point; the choice changed in 13 of 151 consecutive week pairs.
  N=50: 15 contexts; 5 changes in 82 pairs. The map is fairly stable, so the losses are not churn: the idea-leg
  that looked best in a context on past weeks simply did not keep winning there.
- Contexts that made money in the walk-forward (N=20): CFB early in-game high price (I12 signal +$28.65, I9
  signal +$14.53), CFB late low price (I9 signal +$24.19), NFL early high (I9 placebo +$11.31), NFL pre-game
  mid price (I7 placebo +$23.21, 8 trades). All small samples; every other chosen pair lost. B was never chosen.
- Full breakdown: breakdown_by_context.csv; week-by-week choices: weekly_choices.csv; stability.csv.

## Descriptive only: full-training map (in-sample, NOT a result)

descriptive_full_training_map.csv lists the best idea-leg per context on all training weeks. Most "best" cells
rest on 1 to 8 trades (e.g. CFB pre-game mid price, I7 signal, +42.68 c on 5 trades); the only best cells with
50+ trades are NFL late high price I4 favorite (+0.31 c, 205 trades), CFB pre-game low price I7 placebo (+0.37 c,
56), NFL early low I12 placebo (+2.29 c, 59), NFL pre-game low I8 placebo (+3.55 c, 58), and two negative ones
(CFB early low I9 signal -0.41 c, 159; NFL late mid I10 fade -2.68 c, 70). In-sample maxima over 16 idea-legs
in small cells; not evidence of an edge.

## Disclosure: first run had a de-duplication bug (fixed before any output was committed)

The first run dropped every candidate after the first per (idea-leg, game), which removed legitimate sequential
trades of B and Idea 10 (762, 139, 139 games with several trades) and left 9,737 candidates instead of 18,565.
The spec says "one position per game per idea-leg, as the base strategies already are; duplicates, if any, keep
the earliest t": the base strategies already enforce one position at a time, so only exact duplicates (same
idea-leg, game and t; there are 0) should be dropped. Code fixed, tests rerun (6 passed), run repeated once. The
first run's log is kept as run_first_bugged.log (N=20: -0.150 ROC, N=50: -0.167; same sign and verdict).

## Caveats

- Mild bias in the map's favour: each base setting in the pool was chosen on all of training.
- B and Idea 10 are round trips; their ROC uses entry price x 10 + fee as capital (posthoc-meta's convention),
  and they are excluded from win rate vs break-even.
- Holdout not run; a holdout version needs every base idea run on holdout and the exact phrase "run ctxmap holdout".
- Variants: 2 (N = 20, 50); not written to experiments/variants.csv here.
