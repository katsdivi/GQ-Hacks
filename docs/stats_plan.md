# Stats plan (frozen 2026-10-03, PROVISIONAL until Alden signs)

Implements HYPOTHESIS_v2.md (with Amendment 1) using the parameters in docs/spec_provisional.md. Written before the who-leads test is run on any game other than nfl_20251116_was_mia (the one Made It game). Changes after this commit are dated amendments, never in-place edits.

## Data

- Training set: every game on both Kalshi and polymarket.com with kickoff before 2026-08-01, from the T8 download (`data/raw/t8_game_plan.csv`, 977 games matched: 283 NFL, 694 CFB; the Super Bowl and CFB title game are not in Kalshi's game series and are excluded).
- Window per game: kickoff - 2 h to kickoff + 5 h.
- A game is dropped (and counted in the report) if polymarket.com history is truncated by the API cap (`polymarket_truncated` in out/download_manifest.csv) or either venue has fewer than 50 trades in the window.
- Holdout (kickoff on or after 2026-08-01): not loaded, plotted or summarised until Divi says "final test run".

## Who leads (the primary test)

Per game:

1. Build both venues' 1 s grids (trailing 3 s median, raw timestamps).
2. Detect jumps on Kalshi and measure polymarket.com's response; detect jumps on polymarket.com and measure Kalshi's response (leadlag.py, both directions).
3. A matched jump is a covered jump in either direction.
4. Signed lead of each matched jump, positive = Kalshi first: +response_s for a Kalshi jump covered by polymarket.com; -response_s for a polymarket.com jump covered by Kalshi.
5. Per-game lead L = median signed lead over all matched jumps in that game. L > 0: Kalshi first in that game; L < 0: polymarket.com first; L = 0: tie.
6. The game qualifies if it has at least 5 matched jumps.

Across games:

7. If fewer than 30 games qualify, the result is "inconclusive".
8. Two-sided sign test on the qualifying games, ties excluded (exact binomial, p = 0.5).
9. A venue is the leader only if all hold: it is first in a majority of qualifying games; sign test p < 0.05; and the median of per-game L across qualifying games is at least 1 s in its favour.
10. Block-time correction (v2): if Kalshi appears to lead, its median per-game lead must be at least 1 s + median D = 1 + 2.119 = 3.119 s. If polymarket.com appears to lead, the 1 s threshold is unchanged.
11. If no venue meets the rule: "neither venue leads consistently", reported as the finding; no trading rule is built.

Reported regardless of outcome: number of games, qualifying games, first-counts per venue, ties, p-value, median L with a 95% block bootstrap CI (resample whole games, 2000 draws, seed 20261003), per-league breakdown (NFL, CFB; descriptive only), cross-correlation lag per game (secondary).

## Placebos

- Swap: the trading backtest with leader and follower swapped (lagging venue treated as leader); expected no edge.
- Unrelated games: for each game, Kalshi from that game against polymarket.com from a different game whose kickoff is within 30 minutes (the next such game in kickoff order, cyclic within each slot; games with no partner are skipped). Run steps 1 to 11 on these pairs. The share of pairs with |L| >= 1 s and the placebo sign test are the method's false-positive rate, reported next to the main result.

## Trading (only if a leader is found)

- Trade only on the lagging venue, after the leading venue moves.
- Costs: costs.py as if traded today; Kalshi via Webull is the primary line, Kalshi direct the comparison line; polymarket.com 0.05 x C x P x (1 - P) rounded up per order. Order size 10 contracts per signal.
- polymarket.com traded: report lower and upper bound (Amendment 1).
- Tuning grid (training only, every combination logged to experiments/variants.csv): jump 3/4/6 cents x window 5/10/20 s x entry gap 2/3/4 cents x timeout 30/60/120 s = 81 settings, at latency 1 s, lower-bound fills.
- Selection rule: best mean net edge per trade (lower bound, Webull line) among settings with at least 30 trades; ties broken by more trades, then the smaller jump threshold.
- Then ONE run on the holdout with the chosen setting, when Divi says "final test run".

## Latency curve and robustness (report.py)

- Latency 0, 0.25, 0.5, 1, 2, 5, 10 s; axis label "0 s = decision within 1 s of the move".
- CIs: block bootstrap by game (2000 draws, seed 20261003).
- Robustness: NFL vs CFB; close vs lopsided (pre-kickoff P(home) within 0.35 to 0.65 vs outside); swap placebo; without the top 5 trades; costs doubled.
- Required metrics in and out of sample: annualized return, volatility, Sharpe, max drawdown, turnover, equity curve, skew, worst month.

## Failure conditions (unchanged from v2)

1. The lag is shorter than a realistic reaction time (here: under about 3 s total, see spec_provisional.md).
2. The edge disappears after the lagging venue's fees and spread.
3. The profit comes from a handful of games.
