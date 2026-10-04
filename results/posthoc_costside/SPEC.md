# Post-hoc cost-side and lead-lag pattern search

**Label: post-hoc, exploratory; search over ideas already seen to fail on training; training only (kickoff before
2026-08-01); every trial counted; holdout not run (only on the exact phrase "run costside holdout").**

Written 2026-10-04 05:36 ET, committed before any real-data run. Every idea so far failed on costs (win rate about
equal to fill price). This search asks whether cheaper execution, cheap-fee price bands, or finer lead-lag
patterns change the sign. Fixed trial list below: **79 trials** (C2 skipped, see C2).

## Data (training only; never holdout, Vultr or data/live)

- Kalshi training ticks: `data/raw/kalshi_only/<game_id>.parquet` (Strategy A set, 1,267 games) and
  `data/ticks/<game_id>_kalshi.parquet` / `_polymarket.parquet` (Strategy B set, 977 games minus the 14
  `run_strategy_b.EXCLUDED_A1` games = 963). Prices are P(home); own-market YES price of the away team = 1 - price.
- Settlement: `data/raw/kalshi_market_meta.csv` (Kalshi's recorded result per team market; ties 0.5; voids / not
  finalized excluded and counted).
- Existing signals (A): per-trade training files of each idea (gitignored, on disk; sha256 in RESULTS.md):
  Strategy A theta 0.80 favorite (`out/strategy_a/rows.parquet`), Idea 7 k 0.02 signal, Idea 8 x 0.2 fade,
  Idea 9 k 0.10 delay 60 signal, Idea 12 k 0.03 signal, Idea 13 e 0.02 signal: signal time t, team.

## Fees (cost lines, not trials)

- Taker: 0.07 x C x P(1-P), rounded up to the cent per order (`strategy_a.fee_kalshi_direct`).
- Maker: Kalshi's maker fee is not documented first-party in the repo (strategy_a_maker.py docstring: fee schedule
  PDF returned HTTP 429; secondary sources state 0.0175 x C x P(1-P) rounded up). Two maker lines:
  **maker0** = 0, **maker175** = 0.0175 x C x P(1-P) rounded up per order. Exits are always taker (taker fee).
- C = 10 contracts per order.

## Execution rules

- Taker entry: first own-market trade at or after t + 1.0 s and within 60 s; fill = trade + 1 cent, capped 0.99;
  skip if none or fill 0.99.
- Maker entry: limit L posted at t (see each block); filled at L only if an own-market trade prints at <= L - 0.01
  (strict trade-through) with ts in (t + 1 s, t + W]; else no position (counted "unfilled"). L below 0.01 or
  above 0.98: skip.
- Exit (C blocks): either hold to settlement, or sell at the first own-market trade at or after fill_ts + H,
  price = trade - 1 cent (floor 0.01), taker fee; if no trade within 120 s after fill_ts + H, hold to settlement
  (counted).
- One open position per game per trial; signals while a position is open are ignored. Hold-to-settlement trials:
  one trade per game.
- In-game window (C1, C3): kickoff + 20 min to kickoff + 4 h (ESPN kickoff).

## Trials

**A) Maker execution of existing signals (24 trials).** 6 signals x L in {last own-market trade at or before t
(A1), last trade - 1 cent (A2)} x W in {60 s, 300 s}. Hold to settlement. Diagnostics: fill rate; adverse
selection = win rate of filled vs unfilled signals (unfilled signals' outcome from settlement).

**B) Fee-band selection (2 trials).** Pool of the 6 signals' candidates. Bands: low = entry P <= 0.10, high = entry
P >= 0.90. Walk-forward by ET week (start after 6 weeks of history): in week w, trade a signal in a band only if
its past (weeks < w) mean net c/contract in that band is > 0 with >= 10 past trades. B1 = taker execution (as
originally filled, taker fee); B2 = maker execution A2 with W 300 s (both maker lines).

**C1) polymarket.com leads Kalshi (36 trials), B set.** At each polymarket.com trade time t in the window: move
m = PM(t) - PM_asof(t - 30 s) in P(home) (as-of last trade, venue time). Kalshi P(home) = last Kalshi trade on
either market (away flipped) at or before t. Signal if |m| >= d AND Kalshi as-of P(home) at t equals Kalshi as-of
P(home) at t - s (Kalshi has not moved in s seconds) AND Kalshi had a trade within 120 s before t. Direction:
m > 0 buys home YES, m < 0 buys away YES. Grid: d in {0.02, 0.03, 0.05} x s in {5, 15} x execution {taker,
maker with L = own last trade, W 60 s} x exit {H 60 s, H 300 s, settlement} = 36.

**C2) CME leads Kalshi: SKIPPED.** Coverage check before the spec: `data/raw/fg_cg_games.csv` lists 32 CME games
expiring before 2026-08-01, but only 1 is mapped to Kalshi training ticks (`data/ticks/nfl_20260118_lar_chi*`).
Under 30 games: skipped, 0 trials.

**C3) Kalshi own large moves (12 trials), A set.** Kalshi P(home) as above. At each Kalshi trade time t in the
window: move = P(t) - P_asof(t - 30 s). Signal if |move| >= 0.05. Momentum buys in the move's direction, reversal
against it. Grid: {momentum, reversal} x {taker, maker L = own last trade, W 60 s} x exit {H 60 s, H 300 s,
settlement} = 12.

**C4) In-game price-band drift (5 trials), A set.** At t = kickoff + 20 min, each team's own-market as-of last
trade (within 10 min before t, else skip). Band trials: buy every team whose price is in band b, taker, hold to
settlement: b in {[0.01, 0.20), [0.20, 0.40), [0.40, 0.60), [0.60, 0.80), [0.80, 0.99)} = 5. Descriptive: mean
drift (settlement - price) per band.

Total: 24 + 2 + 36 + 0 + 12 + 5 = **79 trials**. Cost lines: taker-entry trials report the taker line; maker-entry
trials report maker0 and maker175 (both counted as one trial each; ranking uses maker175, the conservative line).

## Metrics per trial

trades; games; ROC = sum net P&L / sum capital (capital = entry price x 10 + entry fee) with a game-bootstrap 95%
CI (2,000 reps, seed 20261004); net c/contract; win rate vs mean break-even (hold-to-settlement); fill rate
(maker); daily P&L on ET game days: Sharpe x365 (game days) and daily Sharpe; max drawdown; excluding the top 5
games.

## Multiple testing (across all 79 trials)

- White Reality Check (stationary bootstrap, mean block 5 days, 2,000 reps, seed 20261004) on daily net P&L series
  (union of game days, zero-filled), statistic = max over trials of the studentized mean; p for the best trial.
- Deflated Sharpe of the best trial (Bailey and Lopez de Prado) with N = 79 and the variance of trial Sharpes.
- Holm across per-trial one-sided p (daily mean > 0, t-test).
- **Candidate edge** only if the best trial's ROC CI lower bound > 0 AND Reality Check p < 0.05. Then recommend a
  single holdout test on "run costside holdout"; never run it here.
- The best trial by ROC is also shown labeled "IN-SAMPLE BEST, after 79 trials, not expected to persist".

## Implementation notes (2026-10-04 05:42 ET, before any real-data run)

- Rounds: Divi changed the brief before the first run. The search runs in ROUNDS; this spec above is **Round 1**
  (79 trials). Each later round is appended here as "Round k" (methods, trial count, why) and committed before it
  touches data. `results/posthoc_costside/trials_log.csv` holds every trial ever tried; the correction (Reality
  Check, DSR at the cumulative count, Holm) is recomputed over ALL trials after every round.
- Evaluation window for every trial (fixed-rule and walk-forward alike): the walk-forward test weeks, i.e. games
  whose ET kickoff week is the 7th training week or later (first 6 weeks = history only), so all trials share
  one window.
- Each maker trial is one trial; maker175 is the primary line, maker0 reported alongside. B1 taker entry uses the
  5-minute window of the source ideas; C blocks use 60 s.
- Signals for block A: Strategy A rows with a favorite >= 0.80 (entered or "no post-decision trade"); Ideas 7,
  12, 13 rows with a signal (team and t present); Ideas 8 and 9 files list entered signals only, so their
  never-filled signals are missing (small, stated).
- Stop condition (Divi): walk-forward ROC CI lower bound > 0 on the primary line, Reality Check p < 0.05 over the
  cumulative trials, >= 100 trades, excluding the top 5 games still > 0.

## Round 2 (16 trials; written 2026-10-04 05:58 ET, before Round 2 touches data)

What Round 1 taught: (1) maker execution cuts cost but is adversely selected: for Idea 12 the UNFILLED signals win
0.55 to 0.61 vs 0.45 to 0.48 for filled ones; (2) the only positive in-game lead-lag cell is polymarket.com
leading with maker entry held to settlement; fast exits (60 s, 300 s) always lose; (3) Kalshi own 5 c moves have
no momentum or reversal edge; (4) in-game longshots below 0.20 are badly overpriced. Helpers own spread capture,
drift, longshot-by-phase, slate correlation and time-slot liquidity; the broad search owns consensus and online
weighting. Round 2 therefore tries four mechanisms none of those cover:

- **R2.ARB, Kalshi two-market complement arbitrage (2 trials), A set, whole trade window.** At each Kalshi trade
  time t: last trade of each team's own market, each within 10 s before t. If last_home + last_away <= S, buy 10
  YES of both (taker, each leg its own first trade at or after t + 1 s within 60 s, + 1 c, cap 0.99, taker fee);
  if only one leg fills it is naked, held to settlement. One arbitrage per game. S in {0.95, 0.97}.
- **R2.CONS, broad-search 2-leg pre-game consensus signal with maker entry (4 trials).** Signal = the trades of
  posthoc-search trial a_consensus_m2_pre_hyp (results/posthoc_search/trades.csv at 1e12415; per game the latest
  t_ns among its rows, its team). Maker limit {A1 = last own trade, A2 = last - 1 c} x W {60 s, 300 s}; hold to
  settlement; maker175 primary.
- **R2.VOL, polymarket.com lead conditioned on Kalshi volatility regime (4 trials), B set.** C1 signals at d 0.05,
  s 15 (Round 1 definition). Regime of a signal = Kalshi P(home) realized volatility over the 10 min before t (sum
  of absolute trade-to-trade changes). Threshold = median of that statistic over all C1 signals in weeks before the
  signal's week (walk-forward). Trials: {low, high} x {taker, maker} entry, hold to settlement.
- **R2.TP, take-profit exits (6 trials).** Entries: I12 maker A1 W300, I9 maker A2 W300, C1 d 0.05 s 15 maker
  (Round 1 definitions). Exit: sell at the first own-market trade at or after the fill with price >= entry + tp
  (sell at that trade - 1 c, taker fee); if none within 60 min of the fill, hold to settlement. tp in {0.03, 0.06}.

Cumulative after Round 2: own 79 + 16 = 95, plus external trials.

## Round 3 (11 trials; written 2026-10-04 05:40 ET, before Round 3 touches data)

What Round 2 taught: the only near-miss is maker entry in CALM Kalshi markets (VOL low maker +0.050, CI just
spans 0); arbitrage on last trades is an artifact; take-profit exits hurt. The maker helper reports that passive
both-side pairs make money when both legs fill (+$51.93 on 1,034 pairs, mean pair cost 0.981) but orphan legs
lose more; the patterns helper's best is favourites 0.80 to 0.90 at kickoff - 5 min (+0.032, CI spans 0). Round 3:

- **R3.PAIR, passive pairs with orphan handling (3 trials), A set, in-game.** Decision slots t every 15 min from
  kickoff + 20 min to kickoff + 4 h. At each slot post maker bids on BOTH teams' YES at (own last trade - 0.02),
  valid in (t + 1 s, t + 900 s], filled on a strict trade-through. Both filled: pair held to settlement. One
  filled (orphan): (a) HEDGENOW: taker buy of the other team's YES at its first trade at or after the orphan's fill
  + 1 s, + 1 c; (b) HEDGEDL: the same taker hedge at the first trade at or after t + 900 s; (c) CUT: sell the orphan
  at its first trade at or after t + 900 s, trade - 1 c, taker fee. A hedge or cut with no trade within 60 s: hold
  the orphan to settlement. Maker legs maker175 (alt maker0), taker legs taker fee. One row per slot (sum of legs).
  Orphan adverse selection reported (orphan win rate vs its fill).
- **R3.FEE, order-size fee rounding (3 trials).** Same fills as R2.VOL.low.maker, R1.A.A.A1.W300 and
  R1.C1.d0.05.s15.maker.settle, but each order is 100 contracts (fee rounded up per 100-contract order), P&L scaled
  to 10 contracts. Capacity (displayed or traded size) is NOT checked; stated as a limitation.
- **R3.FAV, favourites 0.80 to 0.90 at kickoff - 5 min with maker entry (1 trial).** Team whose own last trade
  (within 10 min before t) is in [0.80, 0.90) at t = kickoff - 5 min; maker limit = that last trade, W 300 s; hold to
  settlement.
- **R3.VOLX, the calm-market filter on other maker signals (4 trials).** I12 maker A1 W300 and I9 maker A2 W300
  (Round 1 definitions), split by the Round 2 volatility statistic with a walk-forward median of that signal's own
  values in earlier weeks: {low, high} x 2 signals.

Cumulative own trials after Round 3: 95 + 11 = 106.
