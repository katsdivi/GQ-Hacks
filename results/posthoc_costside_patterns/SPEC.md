# Post-hoc cost-side price-pattern search (helper branch posthoc-costside-patterns)

Status: EXPLORATORY, TRAINING DATA ONLY (kickoff < 2026-08-01 is the rule; the 1,267-game training file
data/raw/kalshi_only_games.csv is used, nothing from holdout_raw, live, vultr or results/holdout).
This spec is committed and pushed before any trade file is read.

## Common rules
- Universe: games from strategy_a.load_games(kalshi_only_games.csv, kalshi_market_meta.csv, ticks_dir=kalshi_only).
  Skip games with .exclude set or result NaN. Leagues present: CFB, NFL (NFL preseason included, not separated).
- A team price is the last trade on that team's own market (strategy_a.own_market_trades, own YES price) with
  ts <= t and ts >= t - max_age. Max age: 3 h for the P1 kickoff-6h reference, 30 min for the P1 kickoff-30min price,
  10 min for every other decision. A missing price on either team's market skips the game.
- Decision at t uses only rows with ts <= t. Fill = first trade on the bought team's own market with
  ts >= t + 1.0 s and ts <= t + 5 min, at trade price + 0.01 capped at 0.99. None found: skip.
- 10 contracts. Cost: strategy_a.fee_kalshi_direct(fill_price, 10). Hold to settlement; payout = team result
  (home result for the home team, 1 - result for the away team). PnL = (payout - fill) * 10 - fee.
- ET weeks (Monday start). The first 6 ET weeks present (2025-07-28 to 2025-09-01) are history only; the 19 test
  weeks are 2025-09-08 to 2026-01-12. Every reported metric uses test-week trades only.
- Metrics per trial: trades, ROC = net PnL / sum(fill*10 + fee) with a game bootstrap 95% CI (2,000 reps,
  numpy default_rng(20261004) re-seeded per trial, resampling the games that traded), net c/contract,
  win rate vs mean fill, Sharpe x365 on game days (daily PnL mean/std*sqrt(365), days with trades only),
  max drawdown ($, on cumulative daily PnL), ROC and c/contract excluding the 5 best games.
- No thresholds are tuned. Every grid point is its own trial. Walk-forward-select trials (W) choose the cell
  from past weeks only: at each test week, the cell with the highest cumulative net PnL over all earlier
  weeks (history weeks included), requiring >= 30 earlier trades; else no trade that week.
- Total trials counted in the multiplicity note: every trial below. With 57 trials, about 2.9 are expected to show
  a 95% CI excluding 0 by chance.

## P1 pre-game drift (12 trials)
Reference price at kickoff-6h and decision price at kickoff-30min (t). change_team = p(t) - p(ref), per team.
riser = team with the larger change (ties skip). If change_riser >= d (d in {3, 5} cents):
momentum = buy riser; reversal = buy the other team (the faller).
Trials: d {3,5} x mode {mom, rev} x league {ALL, NFL, CFB}. IDs P1-01..P1-12 in that nested order (d outermost,
then mode, then league ALL/NFL/CFB).

## P2 closing-line value (0 trials)
Skipped. The stated signal (price at kickoff-2h below price at kickoff-30min) uses the future by definition.
A lookahead-free predictor of the kickoff price from earlier data would be a different mechanism (a forecast
model), and the only candidate is the P1 drift extrapolation, which is already P1. No P2 trials run.

## P3 longshot bias by league and phase (27 trials)
At t in {kickoff-5min, kickoff+60min, kickoff+120min}, favourite = the team with the higher own price.
Buy the favourite if its price p satisfies lo <= p < hi, with band in {[0.70,0.80), [0.80,0.90), [0.90,0.95)}.
Trials: time {3} x band {3} x league {ALL, NFL, CFB}. IDs P3-01..P3-27 (time outermost, then band, then league).

## P4 slate correlation (6 trials)
ET dates with >= 5 games in the training file. A game is "settled" for decision purposes only at kickoff + 5 h
(a fixed conservative assumption, the data has no settlement timestamp). Upset = a game whose favourite at its
kickoff-5min price was >= 0.70 and lost (a tie cannot occur; none present). For a later game on the same ET date,
at its kickoff-5min, count k = upsets among games with kickoff + 5 h <= t. If k >= K (K in {1,2}) buy its favourite
when the favourite price is in a P3 band. Trials: K {1,2} x band {3}. IDs P4-01..P4-06. A game with no earlier
game on the day is never traded. Control comparison is P3 at kickoff-5min, same bands.

## P5 time-slot liquidity (9 trials)
Slot = (ET weekday, ET kickoff hour). Slot volume for a past game = trades on both its markets in the 60 min
before that game's own decision time t (same t as the trial). For a current game in week w, slot trailing volume =
mean of that quantity over games of the same slot in weeks < w (needs >= 3 such games, else skip). The game is
low volume if its slot's trailing volume is in the bottom tercile of all slots' trailing volumes computed from
weeks < w. P3 rules (same 3 times x 3 bands, league ALL only) restricted to low-volume games. IDs P5-01..P5-09.

## Walk-forward select trials (3)
W-P1 (over P1-01..12), W-P3 (over P3-01..27), W-P5 (over P5-01..09). IDs W-P1, W-P3, W-P5.

## Count
P1 12 + P3 27 + P4 6 + P5 9 + W 3 = 57 trials. P2 = 0 (skipped, reason above).

## Outputs
results/posthoc_costside_patterns/{SPEC.md, RESULTS.md, trials_log.csv, daily_pnl.csv}. Per-trade files gitignored.
Code: scripts/posthoc_costside_patterns.py. Tests: tests/test_posthoc_costside_patterns.py.
