# Post-hoc unsupervised regime mining (walk-forward, training only)

**Label: post-hoc, exploratory; clusters fit on past weeks only; training only (kickoff before 2026-08-01); holdout not run.**

Written and committed before any code touches real data. Divi asked for an unsupervised search over all our
training data for regimes where Kalshi is miscalibrated by more than costs. Every earlier search (303 cumulative
trials on branches posthoc-costside, posthoc-costside-maker, posthoc-costside-patterns, posthoc-search) found
no edge; this test's trials are added to that count for the multiple-testing correction.

## Snapshot dataset

- Games: every Strategy A training game (data/raw/kalshi_only_games.csv, 1,267), kickoff before 2026-08-01
  (asserted). Kalshi trades from data/raw/kalshi_only/<game_id>.parquet (ts, market_id, kind, price as P(home),
  size, side). Settlement: data/raw/kalshi_market_meta.csv settlement_value_dollars per side (finalized or settled;
  else NaN = void, excluded).
- Decision times per game: kickoff - 30 min, kickoff - 5 min, and kickoff + 20, 30, ..., 180 min (19 times).
  One row per team per decision time.
- A row exists only if the team's own Kalshi market has a trade at or before t no older than 10 min (else stale,
  skipped and counted).
- Features, all computed from rows with timestamp <= t:
  1. own last price p; own price change over the last 1, 5, 15 min (last price minus as-of price at t - x);
  2. trade count and contract volume over the last 5 and 15 min (both team markets);
  3. aggressor imbalance over the last 5 min, oriented to the team: (buy - sell)/(buy + sell) contracts in P(home)
     terms, sign flipped for the away team;
  4. log seconds since the team's last own trade;
  5. the other team's own last price, and the sum of the two prices;
  6. polymarket.com gap: polymarket.com last P(home) oriented to the team minus p, and log age of that trade
     (Strategy B training set only, data/ticks/<game_id>_polymarket.parquet; missing flag otherwise);
  7. ESPN state at t from ../wt-idea6/data/espn_raw/ (read-only cache; ids ids_training.csv; orientation by
     posthoc_idea6.orient, Kalshi team names): score difference (team minus opponent), period, game seconds
     elapsed, possession (+1 team, -1 opponent, 0 unknown), ESPN win probability oriented to the team (the
     winprobability entry of the last play with wallclock <= t). Only plays with wallclock <= t are used. Games
     failing the wallclock defect rule (any play wallclock outside [kickoff - 30 min, kickoff + 6 h], or any play
     more than 5 min earlier than the previous play) get the ESPN features set to missing, flag = 1. Never imputed
     from later plays.
  8. league (NFL flag), NFL preseason flag (strategy_a.is_preseason), ET weekday (Saturday, Sunday flags) and ET
     hour, minutes from kickoff to t;
  9. NFL only: nflverse no-vig home probability from ../wt-idea13/results/posthoc_idea13/training_games.csv
     (p_home, oriented to the Kalshi home team), as a gap p_line - p for the team; missing flag otherwise.
     Limitation: nflverse does not publish line timestamps (lookahead risk, as stated in Idea 13).
  Missing values: a missing flag column plus 0 after standardization.
- Target: net residual r = payout - p - cost(p), cost(p) = 0.01 + fee_taker(p)/10 for the taker line and
  fee_maker175(p)/10 for the maker line (fee formulas as posthoc-costside: 0.07 and 0.0175 x C x P x (1 - P),
  rounded up to the cent per 10-contract order).

## Walk-forward

- ET weeks (Monday start) of kickoff, as posthoc-costside; weeks 0 to 5 are history only; test weeks 6 onward.
- For test week w: fit standardization, PCA (components to 90 percent variance, at most 10) and the clusterer on
  rows of games in weeks < w only. Clusterers: k-means (k-means++ init, seed 20261004, 3 restarts, 60 iterations)
  and GMM-lite (diagonal covariance EM, 60 iterations, initialized from the k-means fit). k in {8, 16}.
- Each cluster's past mean net residual (on the trial's cost line) and past row count, from weeks < w only.
- A week-w row is eligible if its cluster's past mean net residual > margin and past count >= n_min.
  margin in {0, 0.01}; n_min in {100, 300}.
- Execution (10 contracts, hold to settlement):
  - taker: first own trade at or after t + 1 s within 5 min, fill = trade + 1 c, cap 0.99, skip at 0.99;
  - maker: resting buy at limit = p (own last price at t), filled at the limit only if an own trade prints at
    <= limit - 0.01 with timestamp in (t + 1 s, t + 5 min]; maker fee 0.0175 line primary, 0 line reported.
- Trade selection:
  - PRIMARY: at most one trade per game: the first eligible decision time; if both teams are eligible at that
    time, the team whose cluster has the higher past mean net residual.
  - SECONDARY: one trade per game per decision time (same team rule), all eligible snapshots.

## Trials

2 clusterers x 2 k x 2 margins x 2 n_min x 2 executions x 2 selection rules = **64 trials**. All count in the
multiple-testing correction.

## Metrics and correction

Per trial: trades, ROC = sum P&L / sum capital with a game-bootstrap 95% CI (2,000 reps, seed 20261004), net
c/contract, win rate vs mean break-even (fill + fee/10), daily Sharpe and x365 on game days (ET date of t), max
DD, ROC and P&L excluding the top 5 games. Metric and bootstrap code: posthoc-costside costside_common.py
(commit 652c5e9), copied.

Correction over the CUMULATIVE trials: posthoc-costside's 156 own trials (its daily_pnl.csv) plus the external
trials it reads (broad search 54, maker helper 36, patterns helper 57) plus these 64: studentized White Reality
Check (stationary bootstrap), Holm, and DSR of the best (costside_common.multiple_testing, unchanged).

Candidate edge = walk-forward ROC CI lower bound > 0 AND Reality Check p < 0.05 over the cumulative trials AND
>= 100 trades AND excl. top 5 P&L > 0. If found: recommended for ONE holdout test on Divi's exact phrase
"run unsup holdout" (not run here).

## Descriptive only (in-sample, not a result)

A cluster atlas: k-means k = 8 fit on all training rows; each cluster's feature means in plain words, row count,
mean net residual (taker line). Also, walk-forward: performance of trades by the rank (1 to 5) of their cluster's
past mean net residual in that week, for the k-means k = 8, margin 0, n_min 100, taker, primary trial.

## Tests (synthetic, before real data)

No feature uses data after t (planted future trades and plays change nothing); clustering and cluster stats use
only past weeks; ESPN features only from plays with wallclock <= t; fee and cost correctness.

No experiments/variants.csv rows are written (64 trials reported for a later combined commit).
