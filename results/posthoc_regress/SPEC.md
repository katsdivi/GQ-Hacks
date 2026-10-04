# Post-hoc: supervised residual regression (where is Kalshi wrong?)

**Label: post-hoc, exploratory; supervised residual model over all data sources; walk-forward on training only; holdout not run.**

Written and committed before any code touches real data (2026-10-04, ET). Branch posthoc-regress from origin/main a7b59cc.
Training only: games with ESPN kickoff before 2026-08-01. No holdout, live, Vultr data, results/holdout/ or key files.

## Data (read-only)

- Games, Kalshi trades (ts, market_id, kind, price as P(home), size, side), settlements: data/raw/kalshi_only_games.csv,
  data/raw/kalshi_only/<game_id>.parquet, data/raw/kalshi_market_meta.csv (settlement_value_dollars, finalized/settled
  only; void -> row dropped). Execution, fee and metric helpers copied from branch posthoc-costside
  (scripts/costside_common.py at 652c5e9), unchanged except paths.
- polymarket.com: data/ticks/<game_id>_polymarket.parquet for Strategy B training games (977 minus the 14 EXCLUDED_A1),
  P(home), as in costside_common.load_games.
- ESPN summaries: ../wt-idea6/data/espn_raw/<league>_<espn_id>.json with ids_training.csv (read-only cache).
  Orientation (ESPN home vs Kalshi home) by posthoc-idea6 orient() (commit 0f57732), using Kalshi names from
  ids_training.csv. A game's ESPN features are used only if orientation is defined AND the game passes the Idea 10
  defect rule (posthoc-idea10 scripts/posthoc_idea10_defects.py, 92ee688): no scoring event with wallclock outside
  [kickoff, kickoff + 6 h] or out of order with neighbouring plays. Otherwise ESPN features = 0 and espn_ok = 0
  (the game is kept; only its ESPN features are dropped).
- nflverse no-vig line (NFL only): p_home from ../wt-idea13/results/posthoc_idea13/training_games.csv (on disk,
  gitignored; built by posthoc-idea13 f4fa3f6 from nflverse games.csv). Used only at the pre-game snapshots.

## Snapshots

Decision times per game: kickoff - 30 min, kickoff - 5 min, and kickoff + 20, 30, ..., 180 min (19 times). One row
per team per time, kept only if the team's own market has a trade at or before t and within 30 min of t.

Features (all from rows with ts <= t; ESPN only from plays with wallclock <= t):
1. p = own last trade price; dp1, dp5, dp15 = p - own as-of price at t - 1/5/15 min (0 if none).
2. n5, n15 = own trade count in (t - 5 min, t], (t - 15 min, t]; v5, v15 = own contracts, log1p.
3. imb5 = (taker YES - taker NO contracts) / total, own market, last 5 min (home market buy = taker YES; away market
   sell in P(home) terms = taker YES); 0 if no trades.
4. age = seconds since own last trade (log1p).
5. q = other team's last price (NaN -> 1 - p), s = p + q.
6. pm_gap = polymarket.com as-of price oriented to the team minus p, pm_age (log1p s); pm_ok flag; 0 if absent or
   older than 30 min.
7. ESPN: score_diff (own - other), period, sec_left (game clock seconds remaining in regulation, 0 pre-game),
   own_poss (1/0), wp (ESPN win probability for the team, latest entry whose play wallclock <= t), wp_gap = wp - p;
   espn_ok flag.
8. nv_gap = nflverse no-vig probability for the team minus p (NFL pre-game snapshots only, else 0); nv_ok flag.
9. nfl, preseason (strategy_a.is_preseason), pregame (t < kickoff), mins_from_ko, ET weekday (0 to 6, as numeric),
   ET kickoff hour.
10. Fixed interactions: p^2, p x score_diff, p x sec_left/3600, p x mins_from_ko/60, wp_gap x espn_ok,
    pm_gap x pm_ok, (s - 1).

Targets: r = payout - p (regression); y = 1[r > c] for classification, c = 0.01 + fee_taker(min(p + 0.01, 0.99))/10.

## Models (fixed grid, no tuning)

- RIDGE1, RIDGE10: ridge on r, alpha 1 and 10, standardized features (past-only mean/sd), intercept unpenalized.
- LOGIT01, LOGIT1: L2 logistic on y, C = 0.1 and 1 (penalty 1/C on standardized coefficients), L-BFGS.
  Predicted r = P(y) - c_breakeven-adjusted: trade rule uses P(y) directly (below).
- BOOST: gradient-boosted depth-2 regression trees on r, 100 rounds, learning rate 0.05, splits on 16 past-only
  quantile bins per feature, min 50 rows per leaf, seed 20261004 (deterministic; no subsampling).
- ISO: isotonic regression (pool-adjacent-violators) of payout on p, fit on past weeks; predicted r = iso(p) - p.

Walk-forward by ET week (Monday start), same week indexing as posthoc-costside (costside_common.week_index): test
weeks 6 to 24 (19 weeks); week w uses a model fit on all snapshot rows from weeks < w only.

## Trade rule

Predicted edge e:
- RIDGE*, BOOST, ISO: e = predicted r.
- LOGIT*: e = P(y = 1) - p (expected payout minus price, since y = 1 iff the team wins for p < 1 - c).

Execution (10 contracts, hold to settlement):
- TAKER: trade if e > 0.01 + fee_taker(p + 0.01)/10 + m. Fill = first own trade at or after t + 1 s within 5 min,
  + 1 cent, cap 0.99, skip at 0.99 (costside_common.taker_entry with win_s = 300).
- MAKER: trade if e > -0.01 + fee_maker175(p - 0.01)/10 + m. Resting buy at p - 0.01, filled only on a strict
  trade-through within (t + 1 s, t + 5 min] (costside_common.maker_entry, W = 300 s). Fee line 0.0175 primary,
  0 maker fee as alternative.
- m (margin) in {0, 0.01}.

Primary book: at most ONE trade per game: the first snapshot time (both teams considered; higher e wins a tie in
time) at which the rule fires AND the order fills; unfilled maker orders do not consume the game. Secondary book:
every firing snapshot-team that fills (all-snapshot).

Trials: 6 models x 2 executions x 2 margins x 2 books (primary, all-snapshot) = **48 trials**.

## Metrics and correction

Per trial (costside_common.metrics): trades, ROC with game-bootstrap 95% CI (2,000, seed 20261004), net c/contract,
win rate vs break-even, Sharpe x365 and daily on game days, max DD, excl. top 5 games.

Key diagnostic: out-of-sample R^2 of predicted r vs realised r on all test-week snapshot rows (baseline: r = 0, i.e.
Kalshi price is the forecast), and Pearson correlation of predicted vs realised r. Also by phase (pre-game, in-game).
Descriptive: permutation importance (drop in OOS correlation when one feature is shuffled across test rows, seed
20261004) for RIDGE10 and BOOST.

Cumulative multiple-testing correction (costside_common.multiple_testing): all 303 trials of posthoc-costside,
posthoc-search, posthoc-costside-maker, posthoc-costside-patterns (their committed or on-disk daily P&L, read-only),
plus posthoc-unsup's trials if committed by the time of the run, plus these 48. Reported: studentized Reality Check p
of the best, DSR, Holm survivors.

Candidate edge = walk-forward ROC CI lower bound > 0 AND cumulative Reality Check p < 0.05 AND >= 100 trades AND
excl. top 5 ROC > 0. If found: recommend ONE holdout test on the exact phrase "run regress holdout"; not run here.

## Tests (synthetic, before the real run)

no future feature (planted column must not change predictions); walk-forward boundary (fit rows all from weeks < w);
ESPN plays only with wallclock <= t; isotonic fit uses past weeks only; fee / cost thresholds.

## Records

No experiments/variants.csv writes (48 trials reported for a later combined commit). Per-snapshot and per-trade files
gitignored under data/regress_cache/.
