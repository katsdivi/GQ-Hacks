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
