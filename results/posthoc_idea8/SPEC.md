# Post-hoc Idea 8: taker-flow fade

**Label: post-hoc, exploratory; selected on training only.**

Committed before any Idea 8 strategy code touches real data. Real-data work so far: Step 0 only (columns and
`side` value counts of 5 training Kalshi trade files; no signal, fill or P&L computed). Holdout run once, only on
the exact phrase "run idea8 holdout".

## Spec (as given by Divi, verbatim)

- Universe: Strategy A training set (kickoff < 2026-08-01) and v3 A4 holdout set, same exclusions as A.
- Window W = [kickoff - 35 min, kickoff - 5 min). Decision t = kickoff - 5 min. Only trades in W are used for the signal.
- Pressure on home team P_h = (taker YES contracts on home market - taker NO contracts on home market) + (taker NO contracts on away market - taker YES contracts on away market). Total V = all taker contracts on both markets in W. Imbalance I = P_h / V. Skip if V < 500 contracts.
- Signal: if I >= x buy 10 YES of the AWAY team; if I <= -x buy 10 YES of the HOME team (fade the pressure). One trade per game.
- x in {0.2, 0.4, 0.6}: 3 variants.
- Fill = first Kalshi trade on that market at or after t + 1.0 s, plus 1 cent, capped 0.99; skip if none within 5 min or fill is 0.99. Hold to settlement. Ties 0.5, voids excluded and counted.
- Fees: Kalshi direct 0.07 x C x P(1-P) rounded up per order (primary); Webull $0.02/contract (secondary); costs x2.
- Placebo: FOLLOW the pressure (buy the pressured team) with the same rules; hypothesis says it loses.
- Selection on training only: highest ROC (Kalshi direct) among x with >= 100 trades; tie -> larger x.
- Metrics, training and holdout separately: trades, ROC with game-bootstrap 95% CI (2,000 reps, seed 20261004), P&L per contract, win rate vs mean fill, mean I at entry, daily P&L on game days with Sharpe annualized x365 and daily Sharpe, max DD, skew, worst day, excluding top 5 games, correlation of daily P&L with Strategy A training daily P&L.
- Label: "post-hoc, exploratory; selected on training only".

## Implementation notes

- Taker side recovered from the stored side column via ingest/kalshi.py:152-155 (home: buy = taker YES, sell = taker NO; away: buy = taker NO, sell = taker YES). P_h = sum over both markets in W of size x (+1 if side = buy, -1 if side = sell), which equals the spec formula term by term.
- Verification on raw data: no raw Kalshi REST trades with a taker_side field are cached for training games (searched ../staleline/data and ../staleline/out; data/live/kalshi is October 2026 recorder data in the holdout period and was not opened). The only evidence for the mapping is the code at ingest/kalshi.py:152-155.
- Rows with side = unknown (none seen in Step 0) count in V but not in P_h. V = sum of size over both markets in W.
- Games and exclusions: strategy_a.load_games on data/raw/kalshi_only_games.csv and kalshi_market_meta.csv; skip and count "kickoff not from ESPN", the game's load-time exclusion, and "missing market", exactly as strategy_a.evaluate_game. Holdout set built as Post-hoc Idea 4 (scripts/final_test_run.real_ctx construction, ESPN kickoff at or before 2026-10-03 20:00 ET).
- Signal uses only trades with kickoff - 35 min <= ts < kickoff - 5 min. I exactly equal to +-x triggers. I = 0 or |I| < x: no trade ("below x").
- Fill: first trade on the bought team's market with t + 1.0 s <= ts <= t + 1.0 s + 300 s, own YES price + 1 cent, capped 0.99; skip "no post-decision trade" if none, "fill at 0.99" if the fill is 0.99. Payout = Kalshi settlement of that team's market (strategy_a Game.result, tie 0.5); NaN = void/unsettled, excluded and counted. Money in Decimal, as Idea 4.
- Costs x2: fill + 1 more cent (same cap) and fees x2. ROC = net / (fill x 10 + fee).
- Daily P&L: by US Eastern date of t. Sharpe x365 on the season calendar zero-filled (as Idea 4: training 2025-07-31 to 2026-01-25); daily Sharpe on game days only.
- Correlation with Strategy A: Pearson correlation of daily P&L (Kalshi direct, costs x1) with Strategy A's training daily P&L at its selected theta 0.80, favorite leg, Kalshi direct line, summed by its ET kickoff date (`date` column), from out/strategy_a/rows.parquet (written by run_strategy_a.py); over the union of both books' game days, zero-filled.
- No experiments/variants.csv rows in this branch (post-hoc rows are added in one later commit).
