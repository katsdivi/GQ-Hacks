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

## Round 2 (committed before any full-history data is read): multi-hour pre-game lead-lag

Motivation, disclosed: Round 1's descriptive pre-game result (polymarket.com information share 0.668 in the last 2 h)
was seen before this section was written. That is why the pre-game window is tested; nothing else from R1 is tuned.

Data: full-history Kalshi and polymarket.com training trades from market listing (data/raw/fullhist/, produced by
branch data-fullhist; used only after its marker file fullhist_ready exists), same games and orientation as the
Strategy B training set (B set minus EXCLUDED_A1), prices in P(home). If the full-history data is not ready by 08:30
ET, Round 2 runs on the existing files (data/raw/kalshi_only and data/ticks/*_polymarket, which start about 2 h before
kickoff) with the 30 min lookback only (16 trials instead of 32), and the results say so.

Rule: decision grid every 60 s from the first time both venues have traded to kickoff - 10 min.
- Leader move: polymarket.com last P(home) minus its value W minutes earlier (both backward as-of); Kalshi move over
  the same W. Both venues' last trades within 10 min of t.
- pm-leads signal: |pm move| >= d and |Kalshi move| < d / 2: buy Kalshi YES in the polymarket.com direction.
- Placebo / alternative (Kalshi leads): |Kalshi move| >= d and |pm move| < d / 2: buy Kalshi YES in Kalshi's own
  direction.
- First signal only, one position per game.
- Execution: taker (first own trade at or after t + 1 s within 60 s, + 1 c) or maker (limit = last own trade at t,
  trade-through within 300 s, pre-game being thinner).
- Exit: taker sell at the first own trade at or after kickoff - 5 min (price - 1 c, within 10 min, else held), or
  hold to settlement.
- Grid: direction {pm-leads, Kalshi-leads} x W {30, 120} min x d {0.02, 0.04} x execution {taker, maker} x exit
  {kickoff - 5 min, settlement} = 32 trials. Walk-forward: no parameter is chosen; every grid point is a trial,
  scored on the 19 test weeks only.

## Round 3 (committed before any new CME training data is read): CME leads Kalshi in-game

Data: training games newly mapped to CME by branch data-cme-train (results/data_cme/ there; data under
data/raw/cme_train_v2 or as its README says), used only after that branch commits its map. CME price = mid of the
CME top of book (bid and ask both present, 1 s grid, backward as-of), oriented to P(home) by the mapping file.
Kalshi = last trade P(home). Window [kickoff + 20 min, kickoff + 4 h].

Coverage first: count mapped games in the test weeks with >= 50 CME mid changes in the window. If fewer than 30
games, Round 3 is descriptive only (no trading trials).

Descriptive: per game, 1 s grid cross-correlation of CME mid changes vs Kalshi price changes at lags -15..+15 s
(argmax lag, positive = CME leads); leadlag.detect_jumps on CME (3 c, 10 s) and the Kalshi response time to cover
80% of each jump within 60 s (leadlag.py PROVISIONAL defaults); VECM information share of CME on a 1 s grid as in R1.

Trading (only if >= 30 games): at each CME jump (leadlag.detect_jumps, jump J within a trailing 10 s), if the gap
CME mid - Kalshi last P(home), in the jump direction, is >= 3 c at the jump second t (both last updates within 30 s),
buy Kalshi YES in the jump direction: taker, first own trade at or after t + L, + 1 c, cap 0.99; one open position
at a time; exit by taker sell at the first own trade at or after fill + 60 s (- 1 c), or hold to settlement.
- Grid: J {3, 4} c x L {1, 5} s x exit {60 s, settlement} = 8 trials.
- Placebo: the same events traded in the opposite direction, exit 60 s: J x L = 4 trials.

## Round 4 (committed before any news or line-move data is read): news and sportsbook line moves

Data: timestamped news items (branch data-news, data/raw/news/) and sportsbook moneyline snapshots with timestamps
(branch data-lines, data/raw/lines/), training games only, used only after each branch commits its README. An event's
time is the source's publication or snapshot time; if a source's time resolution is coarser than 1 min, the event is
treated as known at the end of its resolution interval.

Events:
- Line move: a no-vig moneyline probability change for a team of >= 2 pp between consecutive snapshots of the same
  book, before kickoff; event time = the later snapshot's time.
- News: items that name a team in a training game and are classified (by keywords fixed here: "out", "inactive",
  "ruled out", "will not play", "doubtful", "injured reserve", "suspended", "questionable") as negative availability
  news for that team, published before kickoff.

Event study (descriptive): for each event, Kalshi and polymarket.com P(team) from event - 30 min to event + 60 min;
the time each venue first moves >= 1 c in the event direction (line move direction; for negative news, against the
named team); which venue moves first; the mean price path.

Trading (only for an event type with >= 100 events in the test weeks): at t = event time + delta, if Kalshi's P(team)
move since the event time is < half of the event's implied move (line moves: half the no-vig change; news: < 1 c),
buy Kalshi YES in the event direction (line move: the team the line moved toward; negative news: the opponent).
Taker, first own trade at or after t + 1 s within 60 s, + 1 c; first eligible event per game; exit by taker at
kickoff - 5 min or hold to settlement.
- Grid per event type: delta {60, 300} s x exit {kickoff - 5 min, settlement} = 4 trials (lines) + 4 trials (news).

### Round 2 amendment (committed before any Round 2 data is read)

The coordinator moved this agent's hard stop to 08:00 ET, and the data-fullhist marker (fullhist_ready) did not exist
at 07:18 ET. So the spec's fallback is applied now instead of at 08:30: Round 2 runs on the existing files
(data/raw/kalshi_only and data/ticks/*_polymarket, about 2 h before kickoff) with W = 30 min only: 16 trials
(direction x d x execution x exit). No full-history data is read in this round. Nothing else changes.
