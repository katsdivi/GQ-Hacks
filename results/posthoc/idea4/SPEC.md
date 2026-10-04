# Post-hoc Idea 4: late-game near-certainty favorite, hold to settlement. post-hoc, exploratory; designed and selected on training only; holdout run once

Label: post-hoc, exploratory; designed and selected on training only; holdout run once.

This rule was written after the pre-registered holdout run. It is not part of the pre-registered study.

## RULE

- Universe: Kalshi game markets in the existing training set (kickoff < 2026-08-01, same files as Strategy A training) and, separately, the v3 A4 holdout A/B set (768 games, kickoff Aug 1 to Oct 3 20:00 ET). Same exclusions as Strategy A.
- Signal: for each game, walk Kalshi trades in time order. Decision time t = time of the first trade with kickoff + 20 min <= t <= kickoff + 4 h whose price for either team's YES is >= theta, and where that team's previous trade was within 60 s before t. Only data at or before t is used. One decision per game at most.
- Entry: buy 10 YES contracts of that team. Fill = price of first trade on that market at or after t + 1.0 s, plus 1 cent, capped at 0.99. Skip if no trade within 5 min, or if the fill price is 0.99 (no upside). Hold to settlement. Ties pay 0.5 per contract (Kalshi scalar), voids excluded and counted.
- Fees: primary Kalshi direct taker fee 0.07 x C x P x (1-P) rounded up to the cent per order. Secondary Webull $0.02 per contract (entry only). Costs x2 reported for both.
- Grid: theta in {0.90, 0.93, 0.95, 0.97}. That is 4 variants.
- Selection rule (training only): among thetas with >= 100 training trades, pick the highest mean return on capital (net, Kalshi direct). Ties: the higher theta.
- Placebo: at the same t, buy the OTHER team's YES with identical fill rules. Must be clearly negative on training; if the placebo is not negative, report it as a failed sanity check.
- Holdout: run the selected theta ONCE on the holdout. Report all 4 thetas on holdout too, labeled plateau, not selection.
- Metrics, training and holdout separately: trades, wins, losses, mean fill, win rate, ROC with game-bootstrap 95% CI (2,000 reps, seed 20261004), mean P&L per contract in cents, daily P&L series on game days only with Sharpe annualized x365 on season days AND daily Sharpe, max drawdown, skew, worst trade, worst day, P&L excluding top 5 games, and break-even win rate vs actual win rate.
- Label everywhere: "post-hoc, exploratory; designed and selected on training only; holdout run once".

## Implementation notes (not part of the rule; fixed before running)

All of the following were decided before any real-data run.

Data and universe
1. Training games: strategy_a.load_games(kalshi_only_games.csv, kalshi_market_meta.csv, ticks_dir=kalshi_only/) with the default expect_preseason (49), read from the staleline data directory by absolute path (read only). Scalar settlements applied by load_games as in Strategy A.
2. Holdout games: built the same way scripts/final_test_run.real_ctx builds the Strategy A games (data/holdout_raw/events.csv with an ESPN kickoff <= AB_CUTOFF 2026-10-03 20:00 ET, settlement_result from the home side of settlements.csv, yes 1.0 / no 0.0, meta = settlements.csv with price_ranges empty), the two input CSVs written to a scratch directory (never results/holdout/), loaded with strategy_a.load_games(..., expect_preseason=None), final_test=True. The script refuses holdout games unless --holdout is passed; the default run asserts every kickoff < 2026-08-01.
3. Exclusions, mirroring strategy_a.evaluate_game: kickoff_source not ESPN ("espn", "espn_event_id"); g.exclude non-empty (missing team market in the trade file); either team's own market has no trade rows; kickoff >= 2026-08-01 without final_test. Strategy A's 10-minute pre-kickoff staleness check does NOT apply (this rule has its own 60 s freshness test). NFL preseason is not a filter here.
4. Kickoff = ESPN kickoff (Game.kickoff), as in strategy_a.

Signal
5. Each team's own YES price series = strategy_a.own_market_trades(trades, g, team) (kind == "trade" rows on market f"{event}-{team}", away market flipped to 1 - price). Prices are rounded to 4 decimals before any comparison (the away flip creates float noise, e.g. 1 - 0.07).
6. Window kickoff + 20 min <= ts <= kickoff + 4 h, both ends inclusive.
7. "That team's previous trade" = the most recent trade on that team's own market with ts strictly less than t (in ns). Eligible iff t - prev_ts <= 60 s (inclusive). No previous trade = not eligible. A trade at the same ns as t is not a previous trade.
8. Both teams' trades are scanned in one merged time order; ties at the same ns are broken home first, then by row order within a market. The first eligible trade (price >= theta, in window, fresh) gives t and the team.
9. Each theta has its own t (a lower theta can fire earlier). The placebo uses the same t as the favorite leg of that theta.
10. One decision per game: the first eligible trade is the decision. If its fill is skipped (no trade in 5 min, fill = 0.99, unsettled) the game is skipped and counted; scanning does not continue.

Fill and settlement
11. Fill trade = first trade on the chosen team's own market with t + 1.0 s <= ts <= t + 5 min (window measured from t, as strategy_a.first_fill). No such trade: skip "no post-decision trade".
12. Fill price = min(round(trade + 0.01, 4), 0.99), a fixed 0.99 cap (not strategy_a's tick-based cap). A fill equal to 0.99 after the cap is skipped ("fill at 0.99"). Consequence: any fill trade at 0.98 or above is a skip.
13. Skip order: no post-decision trade, then fill at 0.99, then unsettled. Voids/unsettled = g.result NaN, excluded and counted.
14. Payout per contract: g.result for the home team, 1 - g.result for the away team (tie 0.5, Kalshi scalar as recorded in the metadata).

Costs and money
15. Fills, fees, gross and net P&L are computed in Decimal; floats only for statistics. Kalshi direct fee = 0.07 x 10 x P x (1 - P), rounded up to the cent per order (strategy_a.fee_kalshi_direct, Decimal). Webull fee = 0.02 x 10 = $0.20 per order, entry only. No settlement fee.
16. Net P&L = (payout - fill) x 10 - fee. ROC = net P&L / (fill x 10 + entry fee) per trade, as strategy_a; reported ROC = mean over trades.
17. Costs x2 (as run_strategy_a.costs_x2): same trade set as the 1x run; fill2 = min(fill + 0.01, 0.99) (the 1 cent half-spread doubled, same cap); fee2 = 2 x fee(fill2). If fill2 reaches 0.99 the trade is kept at 0.99 (not dropped).

Placebo
18. Placebo is evaluated at every game that has a decision t for that theta, whether or not the favorite's fill was skipped. It buys the other team's YES on the other team's own market with identical fill, cap, skip and settlement rules.
19. Sanity check, per theta: pass iff the placebo's mean ROC (Kalshi direct, 1x) is < 0 and its bootstrap 95% CI upper bound is < 0 ("clearly negative"). The headline check is the one at the selected theta; all four are reported. Also reported: mean ROC < 0 alone.

Selection
20. Among thetas with >= 100 training trades (favorite leg), highest mean ROC net Kalshi direct 1x; tie goes to the higher theta. If no theta qualifies, "no theta selected" (the threshold is not relaxed).

Metrics
21. Wins = payout 1.0, losses = payout 0.0, ties counted separately. Win rate = mean payout (ties 0.5).
22. Game-bootstrap CI: the per-trade ROC vector (one trade per game) resampled with replacement 2,000 times, a fresh numpy.random.default_rng(20261004) per CI, percentiles 2.5 and 97.5 of the resampled means.
23. Mean P&L per contract in cents = total net P&L / (10 x trades) x 100.
24. Day = US Eastern date of the decision time t.
25. Season window for the x365 Sharpe: training 2025-07-31 to 2026-01-25 (results/numbers.json training.season_first_day/last_day), holdout 2026-08-06 to 2026-10-04 (numbers.json OOS.season_first_day/last_day). If any trade day falls outside the window, the window is extended to include it (report_book's min/max behavior); this is reported.
26. Sharpe x365 = daily net P&L (dollars) reindexed to every calendar day of the season window with zeros, mean / sd(ddof=1) x sqrt(365). Daily Sharpe = mean / sd(ddof=1) of daily net P&L on game days only (days with at least one trade), not annualized. Both are computed for each fee line and cost level.
27. Max drawdown = max of (running max - cumulative daily net P&L), in dollars, starting from 0. Skew = scipy.stats.skew(daily net P&L on game days, bias=False). Worst trade = min per-trade net P&L. Worst day = min daily net P&L on game days.
28. P&L excluding top 5 games: drop the 5 trades with the largest net P&L on the line being reported; report trades left, mean ROC and total net P&L.
29. Break-even win rate = mean over trades of (fill + fee / 10) per contract, on each line; compared to the actual win rate (mean payout).
30. Outputs: training_results.csv (4 thetas x {favorite, placebo} x {Kalshi direct, Webull} x {1x, 2x}), training_trades.csv (our simulated trades only: game id, league, theta, leg, team, decision and fill times, fill, fees, payout, P&L; no raw tick rows), TRAINING.md. The holdout writes the same files with the holdout prefix, once.
