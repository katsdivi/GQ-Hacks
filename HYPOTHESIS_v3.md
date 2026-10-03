# Hypothesis v3: two additional Kalshi strategies

Pre-registered alongside HYPOTHESIS_v2.md (Kalshi vs polymarket.com lead-lag), before the v2 who-leads result is computed and before any analysis of A or B. The commit timestamp is the proof. Both strategies are run regardless of the v2 result, and every result is reported.

## Strategy A: Kalshi favorite-longshot, hold to settlement

**Hypothesis.** On Kalshi NFL and college football game-winner markets, heavy favorites are underpriced relative to their win rate (the favorite-longshot bias), so buying the favorite shortly before kickoff and holding to settlement earns a positive net return.

**Motivation.** Burgi, Deng and Whelan, "Makers and Takers: The Economics of the Kalshi Prediction Market" (CESifo Working Paper 12122).

- **Universe.** Every KXNFLGAME and KXNCAAFGAME game on Kalshi (not only games also on polymarket.com). Train: kickoff before 2026-08-01. Test: kickoff on or after 2026-08-01, run once when Divi says "final test run".
- **Kickoff times.** From the ESPN public scoreboard API (site.api.espn.com) only, for NFL and CFB; not inferred from trading. Games ESPN does not have are dropped and listed.
- **Price.** Each team's own Kalshi market (KXNFLGAME / KXNCAAFGAME ticker for that team), trailing 3 s median of trade prices, as-of 5 minutes before kickoff (last value at or before that instant).
- **Staleness.** A game is skipped if the favorite's market has no trade in the 10 minutes before the entry instant. Skipped games are counted and listed.
- **Entry.** The favorite is the team whose own market price is higher. If that price >= theta, buy 10 contracts of the favorite's YES at the as-of price + 1 cent (half-spread). Hold to settlement.
- **Settlement.** Payout $1 per contract if the favorite wins, $0 otherwise, from the market's settled result.
- **Grid.** theta in {0.70, 0.80, 0.90}.
- **Return.** Return on capital per trade = net P&L / (entry price + entry fee), per contract. Net cents per contract is also reported.
- **Selection.** Best mean return on capital on train among thetas with at least 50 trades.
- **Costs.** Primary: Webull $0.02 per contract per fill (entry only; settlement is not a fill). Comparison: Kalshi direct 0.07 x C x P x (1 - P) rounded up to the cent per order. Settlement fee: 0, flagged "Andrew to confirm" (not in docs/research/fees.md).
- **Order size.** 10 contracts per game.
- **Placebo.** Buy the underdog (the other team's market) at the same thresholds, i.e. when the favorite >= theta, buy the underdog at its own as-of price + 1 cent.
- **Metrics.** Daily P&L by settlement date, Sharpe, max drawdown, equity curve; NFL vs CFB separately.
- **Robustness.** The selected theta is rerun excluding the incidentally seen games (Disclosure items 1 to 3) and reported next to the main result.
- **It fails if:**
  1. The test-set game-bootstrap 95% CI of return on capital per trade includes 0.
  2. The profit comes from a handful of games (the result without the top 5 games by P&L has a CI including 0).
  3. One league carries it all (the other league's return on capital is not positive).

## Strategy B: cross-venue disagreement, trading Kalshi only

**Hypothesis.** When Kalshi and polymarket.com disagree by several cents for a sustained period on the same game, Kalshi moves toward polymarket.com, so trading Kalshi toward polymarket.com earns a positive net return.

- **Universe.** The 977 T8 training games on both venues (kickoff before 2026-08-01); test: games on both venues from 2026-08-01, once.
- **Signal.** d(t) = Kalshi P(home) minus polymarket.com P(home), both as trailing 3 s medians of trade prices on the common 1 s grid (docs/spec_provisional.md). polymarket.com uses raw block time, never shifted (its information is stale by D, which works against the strategy).
- **Staleness.** d(t) is valid only if BOTH venues have a trade within the previous 60 s. No entry while d is invalid; an open position exits at T if d stays invalid. The share of game-seconds with a valid d is reported.
- **Entry.** When d is valid and |d| >= k for at least m consecutive seconds, trade Kalshi toward polymarket.com (buy Kalshi P(home) if d < 0, sell if d > 0), 10 contracts. Decision stamped at the end of the m-th second (grid convention).
- **Exit.** When d is valid and |d| < 1 cent, or after T seconds.
- **Fill.** Kalshi as-of t + latency (1 s). [DATA LIMIT: historical Kalshi data is trades only, no book. Training fills are as-of trade price +/- 0.5 cent half-spread, the stats-plan fill model. Holdout games recorded live have the Kalshi book (websocket); the test reports both the book fill and the trade +/- half-spread fill, and the trade +/- half-spread fill is primary so train and test use the same model.]
- **Grid.** k in {3, 5} cents x m in {10, 30} s x T in {60, 300} s = 8 settings.
- **Selection, costs, fail conditions.** As docs/stats_plan.md: best mean net edge per trade (Webull line) among settings with at least 30 trades; Kalshi via Webull primary, Kalshi direct comparison; the three v2 fail conditions.
- **Placebo.** Kalshi from game A vs polymarket.com from a different game B in the same time window (stats-plan pairing: kickoff within 30 minutes, next in kickoff order).

## Multiple testing

Every setting run is logged to experiments/variants.csv.

| Family | Variants |
|---|---|
| v2 exploratory (logged so far, nfl_20251116_was_mia only) | 7 |
| v2 tuning grid (only if a leader is found) | up to 81 |
| v3 A: theta grid | 3 (+3 underdog placebo) |
| v3 B: k x m x T grid | 8 (+8 unrelated-game placebo) |
| Total trading variants | up to 99 (+11 placebo runs) |

For each strategy, the deflated Sharpe ratio (Bailey and Lopez de Prado, 2014) is reported on daily P&L, with the number of trials set to (1) that strategy's own grid size and (2) the total across v2 and v3, so the reader sees both.

## Holdout

Train on games with kickoff before 2026-08-01; test once on games from 2026-08-01, when Divi says "final test run". Holdout data stays write-only until then.

## Disclosure

The data was downloaded under v2. No computation of strategy A or B (entries, returns, win rates by price) has been run. The v2 who-leads result has not been computed (the first attempt crashed on a no-jump game before producing any result). Prices or outcomes already seen, all incidental:

1. LAR at CHI, 2026-01-18: CME and Kalshi prices (overlay chart) and both Kalshi market results.
2. Kalshi KXNFLGAME markets for Jan 4 to Jan 25, 2026 (about 29 games): market results and volumes were printed in a market listing during T3.
3. Jan 17 and Jan 18, 2026 Kalshi markets: results printed by `ingest.kalshi find`.
4. nfl_20251116_was_mia: Kalshi and polymarket.com prices (run chart, pre-kickoff level near 0.57 and the final level).
5. Three polymarket.com games (nfl-atl-min-2025-09-14, nfl-atl-no-2025-11-23, nfl-atl-ari-2025-12-21): trade records downloaded (prices not examined).
