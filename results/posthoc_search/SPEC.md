# Post-hoc broad search with multiple-testing correction

**Label: post-hoc, exploratory; broad search over strategies already seen to fail on training; walk-forward on
training only; every grid point is a trial; holdout not run.**

Written 2026-10-04 (ET) and committed before any method in this spec touches real data. The only real-data look
before this commit: column names, per-cell counts, fee ranges and decision-time ranges of the candidate pool
(no P&L of any method below was computed).

## Input

- Candidate pool: `../wt-meta/results/posthoc_meta/candidates.csv` (gitignored on posthoc-meta; produced by
  `scripts/posthoc_meta.py`, script commit 3da957a, outputs 07738c9), sha256
  a9ff5574a0457f79a557ea834a51e3821f991ba78e247dfa613216a64d108c33, 18,565 rows, 16 cells (strategy:leg):
  A:favorite (theta 0.80), B:signal, I4 favorite/placebo (theta 0.90), I7 signal/placebo (k 0.02), I8
  fade/placebo (x 0.2), I9 signal/placebo (k 0.10, delay 60), I10 fade/placebo (s 0.10), I12 signal/placebo
  (k 0.03), I13 signal/placebo (e 0.02). Training games only (kickoff before 2026-08-01).
- Excluded as invalid or non-training: Idea 3, the Idea 6 winner leg, Ideas 1, 2 and 11.
- Per candidate: decision time t_ns, team, entry fill, signal strength, net P&L per 10 contracts (Kalshi direct,
  costs x1; B and I10 are round trips), fee, capital, ROC = pnl / capital, y = 1{pnl > 0}, ET date, ET week,
  minutes from kickoff to t.
- Finer thresholds (family e) use the pool's `signal` column. The pool only holds candidates that passed each
  idea's base threshold, so finer cuts can only tighten the base threshold.

## Evaluation

Walk-forward by ET week on TRAINING only. Evaluation weeks = all pool weeks after the first 6 (19 weeks,
2025-09-08 to 2026-01-12), same as posthoc-meta. Every choice for week w uses only candidates of weeks < w
(families c, d, e) or only candidates settled on ET dates before the candidate's date (family b). Family a is a
fixed rule (no fitting). Trades are counted only in evaluation weeks.

"Pre-game" = minutes from kickoff to t <= 0. "Idea" = strategy (A, B, I4, I7, I8, I9, I10, I12, I13).
"Hypothesis legs" = A:favorite, B:signal, I4:favorite, I7:signal, I8:fade, I9:signal, I10:fade, I12:signal,
I13:signal. "All legs" = all 16 cells.

## Method grid (every grid point is one trial)

**a) Consensus (8 trials).** For each game and team, order candidates by t. A candidate is "agreeing" when, counting
it, at least m DISTINCT ideas have a candidate for the same game and team with t at or before its t. Trade the
first candidate at which the count reaches m (one trade per game and team), at that candidate's own fill and P&L.
Grid: m in {2, 3} x scope {all phases, pre-game only} x legs {hypothesis legs, all legs} = 8.

**b) Online weighting (3 trials).** Over the 16 cells. Reward of a cell on an ET date = mean ROC of its candidates
that date, clipped to [-1, 1]. Weights at the start of date d use only rewards of dates < d.
- Hedge, learning rate eta in {0.1, 0.5}: w_k <- w_k exp(eta r_k), renormalized; trade every candidate of cells
  with w_k > 1/16 at the start of the date (2 trials).
- Thompson sampling: Beta(1 + wins, 1 + losses) per cell on y, updated with dates < d; at each date draw one
  sample per cell (numpy default_rng seed 20261004); trade the cell's candidates that date if the draw exceeds the
  cell's past mean breakeven (0.5 if no history) (1 trial).

**c) Price filters (3 trials).** Bands on the candidate's own fill: >= 0.80, <= 0.20, 0.40 to 0.60. For week w and
band, trade the candidates (in that band) of every cell whose past (weeks < w) in-band mean net c/contract > 0
with at least 20 past in-band trades.

**d) Context x consensus (2 trials).** Context = league (CFB, NFL) x phase (pre-game; kickoff to +90 min; after
+90 min) x fill band (< 0.35, 0.35 to 0.65, > 0.65), as posthoc-ctxmap (spec 7f9599e). Only candidates with at
least one OTHER distinct idea agreeing (same game and team, t at or before) enter, both as history and as trades.
For week w and context, trade only the candidates of the single best eligible cell (past mean net c/contract > 0,
at least N past trades in that context; tie -> more trades, then cell name). N in {20, 50}.

**e) Finer thresholds (11 trials).** For each of the 10 cells I7, I8, I9, I12, I13 x {signal or fade, placebo}:
at week w, from the cell's past candidates, cut points = quantiles {0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9} of
|signal|; pick the cut with the highest past mean net c/contract among cuts with at least 20 past trades above
it; if that mean is <= 0, no trade that week; else trade week-w candidates with |signal| >= cut (10 trials).
Plus the union of those 10 books (1 trial).

**f) Sizing (27 trials).** For each of the 27 books above, a sized version: at week w, rank the 16 cells by past
(weeks < w) mean net c/contract into terciles (5, 5, 6 cells; bottom, middle, top) and size each trade 5, 10 or
20 contracts. P&L at size s: hold-to-settlement cells: (pnl + fee) x s / 10 minus the Kalshi direct fee at size s
(0.07 x s x P(1 - P) rounded up to the cent, P = fill); round-trip cells (B, I10): pnl x s / 10 (fees scaled
linearly; approximation stated).

**Total: 8 + 3 + 3 + 2 + 11 + 27 = 54 trials.**

## Metrics per trial

trades, contracts, games; mean ROC weighted by contracts with a game-bootstrap 95% CI (2,000 reps, seed 20261004);
one-sided bootstrap p-value P(mean ROC <= 0); net c/contract; total P&L; daily P&L on game days with Sharpe
(daily and x365); max drawdown; worst day; ROC and P&L excluding the top 5 games by P&L.

## Multiple-testing correction

Daily P&L of every trial is aligned on the same calendar: every ET date in the evaluation weeks with at least one
pool candidate (zero on dates a trial does not trade).
- White's Reality Check: statistic max_k sqrt(n) mean_k over the 54 trials vs a zero benchmark; stationary
  bootstrap (Politis and Romano), mean block 5 dates, 2,000 reps, seed 20261004; p-value of the best trial.
- Hansen SPA (consistent version, studentized, with the usual recentring of poor trials): p-value.
- Romano-Wolf stepdown adjusted p-values for every trial (same bootstrap).
- Holm on the 54 one-sided game-bootstrap ROC p-values, alpha 0.05.
- Deflated Sharpe (report_book.deflated_sharpe, the method of scripts/posthoc_dsr.py) of the best trial by daily
  Sharpe, with trial Sharpes = the 54 trials' daily Sharpes, n_trials = 54; also with n_trials = 77 + 54 = 131.

## Decision rule (fixed now)

A trial is a CANDIDATE EDGE only if its walk-forward ROC 95% CI lower bound is > 0 AND its Reality Check p-value
(Romano-Wolf adjusted; equals the Reality Check p for the best trial) is < 0.05. If one exists, it is recommended
for a single holdout test that runs only on Divi's exact phrase "run search holdout" (not run here). If none,
that is the result.

## In-sample best (reported separately, labeled)

"IN-SAMPLE BEST, after N trials, not expected to persist": over all 16 cells x 8 |signal| quantile cuts (computed
on the evaluation weeks) x 4 fill bands (all, >= 0.80, <= 0.20, 0.40 to 0.60), chosen and evaluated on the same
evaluation weeks (no walk-forward), the highest mean ROC with at least 30 trades. N = 512. Reported next to the
walk-forward and corrected figures, never as a result.

## Records

No experiments/variants.csv writes here; 54 trials reported for a later combined commit. Per-candidate outputs
gitignored, summary CSVs committed.
