# Hypothesis v2: Kalshi vs polymarket.com lead-lag

Replaces the retired CME vs Kalshi hypothesis in `HYPOTHESIS.md`. Committed before any Polymarket price is loaded for analysis and before any backtest on these venues. The commit timestamp is the proof.

**Question.** For the same NFL or college football game, does one of Kalshi and polymarket.com systematically reprice before the other after a large move? This is a two-sided test: we do not assume which venue leads.

**Venues.** Kalshi (KXNFLGAME and KXNCAAFGAME game-winner markets) and the international Polymarket order book at polymarket.com (moneyline markets in its NFL and college football game series). Polymarket US, the CFTC-regulated app, is a separate order book whose trade history is not public, so it is not part of this test.

**Why a lead could exist.** The two venues have different users and plumbing. Kalshi is a CFTC exchange reached through retail apps such as Webull; polymarket.com is an offshore, on-chain venue with different market makers and settlement. Few participants watch and trade both in real time, so information may reach one book first.

**One clock.** Both venues are compared on a common 1-second grid. Kalshi timestamps (microseconds) are floored to whole seconds, the same resolution as polymarket.com, so neither venue gets an artificial head start from rounding. Lags are reported in whole seconds; anything under 1 second cannot be measured on historical games.

**Timestamp source.** polymarket.com historical trade timestamps are the on-chain block time, not the off-chain match time. Checked on 2026-10-03: 20 of 20 sampled trades from two training games had an API timestamp exactly equal to their Polygon block timestamp. Matching happens off-chain before the trade is included in a block, so every polymarket.com trade is stamped late by the match-to-block delay. This biases the test toward Polymarket looking like the slower venue. The size of that delay is not yet measured; it will be measured on live non-football polymarket.com markets before any game is analysed and reported next to the result.

**Block-time bias: correction fixed in advance.** Because polymarket.com historical timestamps are block times, every polymarket.com trade is stamped late by the match-to-block delay D. Before any game is analysed, D is measured on live polymarket.com markets (block timestamp minus our websocket receipt time) over at least 200 trades, and its median and 90th percentile are reported. If D cannot be measured, any "Kalshi leads" result is reported as inconclusive.
1. Lead rule: if polymarket.com appears to lead, the fixed rule applies unchanged (the bias works against it). If Kalshi appears to lead, its median per-game lead must be at least 1 s plus the median of D.
2. Backtests that trade on polymarket.com shift every polymarket.com timestamp earlier by the 90th percentile of D, so the strategy never acts on a price that had already moved. Backtests that trade on Kalshi with polymarket.com as the signal use unshifted timestamps (conservative: the signal arrives late).
3. Holdout games recorded live carry both block time and receipt time. The final test uses block time, the same source as training. Receipt-time results are reported as a secondary check only.

**Who leads: fixed rule.**

1. A game qualifies if it has at least 5 matched jumps (a large move on one venue paired with the other venue's response).
2. At least 30 qualifying training games are required. With fewer, the result is "inconclusive".
3. A venue is the leader only if all three hold across qualifying training games: it moves first in a majority of games; a two-sided sign test across games gives p < 0.05; and the median per-game lead is at least 1 second.

Direction is measured on training games only (kickoff before 2026-08-01), with the same jump detection, response time and cross-correlation methods in both directions.

**A trading rule exists only if a leader is found.** If one venue meets the rule above, we define one rule: trade only on the lagging venue, after the leading venue moves.

**If neither venue leads consistently, that is the result.** We report it as the finding and do not build or test a trading rule.

**Who could trade it.** If polymarket.com is the lagging venue, a US resident cannot legally trade it, so the edge is reported as a measurement only and no US-executable strategy is claimed. If Kalshi is the lagging venue, execution is via Webull or Kalshi directly. All trading in this project is paper trading.

**If true, we should see:**

1. The lagging venue close most of a leading-venue jump within seconds.
2. A net edge on the lagging venue that shrinks as assumed reaction time grows.
3. No edge in either placebo below.

**Placebos.**

1. Swap: the lagging venue is treated as the leader.
2. Unrelated games: Kalshi from game A against polymarket.com from a different game B played in the same time window. Any "lead" between unrelated games measures the method's false-positive rate.

**It fails if:**

1. The lag is shorter than a realistic reaction time.
2. The edge disappears after the lagging venue's fees and spread.
3. The profit comes from a handful of games.

**Edge category (track list):** structural or institutional constraint.

**Holdout:** measure direction and tune on games before August 1, 2026. Test once on August 1 to October 2026. Holdout data is recorded but not analysed, plotted or summarised until the final test run.

**Disclosure.** Before this hypothesis was written:

1. One game, LAR at CHI on 2026-01-18, was examined on CME and Kalshi only (data check, overlay chart, and a rough cross-correlation that suggested Kalshi moved before CME).
2. polymarket.com trade records were downloaded for three NFL training games picked by date (nfl-atl-min-2025-09-14, nfl-atl-no-2025-11-23, nfl-atl-ari-2025-12-21) to count trades per minute and to check timestamps against block times. The records include a price field; prices were not examined, plotted or compared.
3. No Kalshi vs polymarket.com price comparison has been made.

## Amendment 1 (2026-10-03 00:41 ET)

Rule 2 of "Block-time bias: correction fixed in advance" is replaced by the following lower/upper bound fill rule, because the p90 shift allowed fills to see trades matched after the decision:

- Decisions and gap checks: never shifted; raw polymarket.com block time only.
- polymarket.com entry fills: timestamps shifted earlier by the 90th percentile of D (worse for us).
- polymarket.com exit fills: unshifted (worse for us).
- The same backtest is also run with no shift at all and reported as the upper bound. Both results are reported, labelled "lower bound" (the rule above) and "upper bound" (no shift).
- Backtests that trade on Kalshi with polymarket.com as the signal are unchanged (unshifted).

Written after one training game (nfl_20251116_was_mia) was run under the old rule. The lead rule is unchanged.
