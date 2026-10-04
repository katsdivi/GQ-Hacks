# Post-hoc lead-lag search 2 (posthoc-leadlag2)

Label: post-hoc, exploratory; training only (kickoff < 2026-08-01); walk-forward on the same 19 test weeks as
posthoc-meta and posthoc-costside (ET weeks, first 6 weeks history only). Holdout never run here; a candidate edge is
recommended for one holdout test on Divi's exact phrase "run leadlag2 holdout".

Common rules (all rounds):
- No lookahead: a decision at t uses only rows with ts <= t (backward as-of). Fills strictly after t.
- Taker: first own-market Kalshi trade at or after t + 1 s within 60 s, price + 1 c, cap 0.99, skip at 0.99;
  fee 0.07 x C x P(1-P) rounded up per order (10 contracts). Maker: limit = last own trade at t, filled only if an
  own trade prints at or below limit - 1 c in (t + 1 s, t + 60 s] (trade-through); fee 0.0175 x C x P(1-P) rounded
  up (alt line 0). Exits: taker sell at first own trade at or after fill + H, price - 1 c, taker fee; if none within
  120 s, held to settlement. Settlement = Kalshi settlement value (kalshi_market_meta.csv).
- Code reused from posthoc-costside 8fb0a15 (scripts/costside_common.py, copied with paths changed) and its cached
  game pool data/costside_cache/games.pkl (read-only).
- Metrics per trial: trades, games, ROC with game bootstrap 95% CI (2,000, seed 20261004), net c/contract, win rate vs
  break-even (held legs), Sharpe daily and x365 on game days, max DD, excl. top 5 games.
- Cumulative multiple-testing correction over ALL trials so far: posthoc-costside own trials plus everything its
  costside_log.py already includes (search 54, maker 36, patterns 57, unsup 64, regress 48), read from
  ../wt-costside and the other worktrees (no double counting), plus this branch's trials. Studentized Reality Check
  (stationary bootstrap), Holm, DSR (project formula and normal-returns version).
- Stop condition (candidate edge): ROC CI lower bound > 0 AND Reality Check p < 0.05 cumulative AND >= 100 trades AND
  excl. top 5 P&L > 0.
- No experiments/variants.csv writes.

## Round 1 (committed before any R1 data is read): information share on existing training data

Data: the Strategy B training games with polymarket.com ticks (data/ticks/<game_id>_polymarket.parquet, the B set
minus the 14 EXCLUDED_A1 games, as costside) and Kalshi trades (data/raw/kalshi_only). Prices in P(home).

Descriptive (not trials):
- D1. 5 s grid, last-trade P(home) on each venue (backward as-of), in-game window [kickoff + 20 min, kickoff + 4 h]
  and pre-game window [kickoff - 2 h, kickoff - 5 min]. Cross-correlation of 5 s price changes at lags -60..+60 s;
  per-game argmax lag (positive = polymarket.com leads); median, share > 0, share < 0.
- D2. Signed trade flow (buy +size, sell -size, P(home) terms) per 5 s bin; correlation of one venue's flow at t - k
  with the other venue's price change at t, k = 0..60 s, both directions.
- D3. Per game (>= 50 price changes on each venue in the window): bivariate VECM on the 5 s grid, cointegrating vector
  (1, -1) imposed, 3 lags. Hasbrouck information share of polymarket.com (both Cholesky orderings, midpoint reported)
  and Gonzalo-Granger component share of polymarket.com. Medians and distribution by league.
- D4. Predictability: (a) within game, Spearman of IS from [kickoff + 20, kickoff + 80 min] vs IS from
  [kickoff + 80 min, kickoff + 4 h]; (b) across games, walk-forward: league mean IS over past weeks vs the game's IS.

Trading trials (24): decision grid every 5 s in [kickoff + 80 min, kickoff + 4 h]. Gap = polymarket.com last P(home)
- Kalshi last P(home), both last trades within 30 s of t. If |gap| >= g, buy Kalshi YES of the team polymarket.com
says is underpriced on Kalshi (gap > 0 -> home, gap < 0 -> away). One open position at a time per game; exit at
H = 300 s (taker) or hold to settlement (then one trade per game).
- Gate E (within game): polymarket.com IS (midpoint) estimated only from [kickoff + 20, kickoff + 80 min] >= 0.6.
- Gate W (walk-forward): mean polymarket.com IS of the same league's games in past weeks >= 0.6.
- Grid: gate {E, W} x g {0.02, 0.04} x execution {taker, maker} x exit {300 s, settlement} = 16 trials.
- Placebo gate P (Kalshi leads): early-window IS <= 0.4, same signal: g {0.02, 0.04} x execution x exit = 8 trials.
- This differs from costside R1.C1 (polymarket.com move >= d within 30 s while Kalshi unchanged): the signal here is
  the price gap (error-correction term) gated by an estimated information share.

## Rounds 2 to 4

Each round gets its own section here, committed and pushed before that round's data is read: R2 multi-hour pre-game
lead-lag on full-history trades (when data-fullhist is ready), R3 CME leads Kalshi on newly mapped training games
(when data-cme-train is ready; descriptive only if < 30 games), R4 news and sportsbook line-move event studies (when
data-news / data-lines are ready; trading trials only with >= 100 events).
