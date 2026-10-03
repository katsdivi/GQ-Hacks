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


## Amendment 2 (2026-10-03 11:15 ET)

Written before any Polymarket US price, and before any polymarket.com holdout price, has been examined.

### Status of the pre-registered v2 test

The v2 primary statistic (L, per-game jump response) failed its pre-registered unrelated-games placebo: median L +7.0 s on unrelated pairs, 95.7% of pairs |L| >= 1 s. The pre-registered v2 who-leads result is therefore INCONCLUSIVE. The secondary statistic (xcorr) on training games gave median +7 s on real games vs +1 s on the placebo. That observation motivated this amendment; it is exploratory and is tested confirmatorily only (a) on the sealed holdout for polymarket.com and (b) on Polymarket US training games, whose prices had not been examined, and then its holdout.

### Methods finding: trade-based lags are biased by activity; book midpoints are not

Full write-up: docs/results/activity_bias.md (simulation code: tests/test_activity_bias.py). Summary:

| Price series | Kalshi vs | Linked, zero lag (no real lead) | True 5 s lead |
|---|---|---|---|
| Trades (3 s median) | 5 trades/min | median +1.0 s; rule false "Kalshi leads" 3/10 studies | median +6.0 s; found 10/10 |
| Trades (3 s median) | 1 trade/min | median +5.0 s; rule false "Kalshi leads" 10/10 | median +8.0 s; found 10/10 |
| Book midpoints | polymarket.com-like streamed quotes | 0 s in 100% of games; false 0/10 | 5 s in 100% of games; found 5/10 at 40 games, 10/10 at 80 |
| Book midpoints | Polymarket-US-like 1 s polled quotes | 0 s in 100% of games; false 0/10 | 5 s in 100% of games; found 5/10 at 40 games, 10/10 at 80 |

No-link (unrelated games) false-positive rate is 0/10 in every case: the unrelated-games placebo cannot detect activity bias, because unrelated games have no link at all. A thin venue's trade-based price only moves when it trades, so it looks late even when it is not; quotes move on information without a trade, so book midpoints do not have this bias. The rule's power for a true 5 s lead is about 60 to 70% at 30 to 60 games and 100% at 80 games.

Consequence: all trade-based lag results are EXPLORATORY ONLY and are reported with this table. Polymarket US on trade data is "not testable at ~1 trade/min (simulated false-positive rate 100%)"; Part B Step 1 on trade data is not run as a confirmatory test.

### Confirmatory test: recorded book midpoints on holdout games

- Games: holdout games recorded live on Friday night 2026-10-02 and Saturday 2026-10-03 (the live recordings). The candidate game set is fixed by data/live/holdout_candidates.csv (every game with a Kalshi KXNFLGAME or KXNCAAFGAME market and kickoff from 2026-10-02 18:00 ET to 2026-10-04 06:00 ET; kickoff from the ESPN scoreboard), committed with this amendment. No game is added later; games leave the set only through the qualification and exclusion rules below.
- Friday-night games: only the Mac recorded them, and only partly (Kalshi from 2026-10-03 03:09 UTC, polymarket.com from 04:11 UTC, Polymarket US from 08:30 UTC). Most Friday-night games are therefore excluded by the outage rule below (a feed that had not yet started recording counts as an outage for the whole uncovered span, so any game window starting more than 60 s before a feed's first recorded row is excluded), so the holdout is effectively Saturday's games. Every excluded game is listed with its reason.
- Mid: mid(t) = (best bid + best ask) / 2 at the last quote at or before t on the 1 s grid, defined only when both sides exist. Every recorded top-of-book change writes the bid row and the ask row with the same receipt timestamp, and an empty side writes no row, so a side exists at a recorded timestamp only if its row carries that timestamp. Seconds where either side is missing have no mid and are excluded from the xcorr; a mid is never forward-filled across a missing side. Clock (proposed answer, Alden to confirm): our receipt time is the primary clock for every venue (one clock). Venue server times (src_ts_ns: polymarket.com book and trade messages, Kalshi orderbook deltas; recorded from 2026-10-03 09:07:50 UTC) are a robustness check only, reported next to the primary result. A subscription snapshot's server time is the time of that book's last change, so it can be minutes before receipt. Polymarket US mid = the 1 s polled best bid/ask.
- Statistic: per-game xcorr peak lag of 1 s mid changes, max lag 15 s, positive = Kalshi first (xcorr_lead.game_lag_mid). The mid and mid-change definitions in this amendment govern: the current game_lag_mid forward-fills each side separately and is changed to follow them before the run. No D correction (book times are not block times).
- Game window: kickoff - 30 min to the window end. Window end (proposed answer, Alden to confirm): the earlier of kickoff + 4.5 h, or the first time either venue's mid stays >= 0.98 or <= 0.02 for 60 s.
- Mid change: a grid second whose mid differs from the previous defined mid. Duplicate rows never count.
- Qualifying game: >= 50 mid changes (as defined above) on each venue inside the game window.
- Two recorders (rule fixed now): Divi's Mac (from 2026-10-02 23:09 ET) and a Vultr server in Atlanta (from 2026-10-03 10:08 ET, local parquet only, NTP via chrony). Per game, one machine's recording is used for the whole game window, never spliced. Primary = Vultr if it has no outage in the window, else the Mac if it has none, else the game is excluded. The other machine is used only as a whole-game substitute. Each machine logs its own outages (Mac: GAPS.md; Vultr: GAPS_vultr.md).
- Recorder outages (rule fixed now): each venue feed writes a heartbeat every 10 s (data/live/heartbeat/; Kalshi websocket: any message or a pong to our 10 s ping; polymarket.com websocket: any message or its PONG; Polymarket US: each successful poll). An outage is a disconnect event, or no heartbeat from a feed for more than 60 s; every outage is logged automatically to GAPS.md (venue, start, end, duration, cause), including Kalshi websocket drops shorter than the 30 s REST fallback and Polymarket US poll failures, and every recorder restart. A game is excluded if either venue has an outage longer than 60 s inside its game window. For Kalshi, an outage counts only while neither the websocket nor the REST fallback is delivering books. Row silence alone does NOT exclude a game (quiet books are not outages). Excluded games are listed with the reason.
- Null: the unrelated-games placebo (Kalshi from game A vs the other venue from a different game B within 30 minutes of kickoff, next in kickoff order), same construction. Unrelated-game pairs are drawn only from games whose windows were both recorded on the same machine (both Vultr or both Mac), so the placebo never mixes clocks or recorders.
- Decision, separately for polymarket.com and for Polymarket US: Kalshi leads iff median lag >= 1 s (polymarket.com) or >= 1.5 s (Polymarket US, 1 s polling allowance), AND two-sided Mann-Whitney real vs placebo p < 0.05, AND >= 60% of qualifying games have lag > 0, with >= 30 qualifying games (else "inconclusive"). The symmetric rule for the other venue leading. Otherwise "neither venue leads consistently".
- Power (proposed statement, Alden to confirm): "An inconclusive result is not evidence of no lead. At the expected 30-80 qualifying games, simulated power for a true 5 s lead is about 60-100%. No games will be added and no thresholds changed after the result is seen."
- Run once, after Saturday's last game. Nothing in the holdout recordings is analysed before then.

### Exploratory, trade-based (reported with the bias table, never confirmatory)

- polymarket.com training xcorr on trades (median +7 s real vs +1 s placebo): exploratory; consistent with a lead OR with activity bias at about 5 trades/min.
- Polymarket US training trades (Time & Sales; 215 games matched to Kalshi, median 1.0 trades/min in game): not testable at ~1 trade/min (simulated false-positive rate 100%). Not run as confirmatory.

### Trade-the-laggard: one pre-registered setting, evaluated on recorded books only

- No tuning on trade data: stale last-trade fills are not valid fills. The 81-setting grids for Part A and Part B are removed.
- One setting, fixed now: jump 4 cents, window 10 s, entry gap 3 cents, timeout 60 s (the middle of the stats-plan grid); exit gap 1 cent; 10 contracts; signals from the same book-midpoint series on the 1 s grid.
- Venues traded: polymarket.com and Polymarket US, each after Kalshi moves (Kalshi as the leader).
- Fills: the recorded live best bid (sell) / best ask (buy) at decision + latency, backward as-of; no half-spread assumption.
- Latency curve: 0, 0.25, 0.5, 1, 2, 5, 10 s ("0 s = decision within 1 s of the move").
- Costs: polymarket.com 0.05 x C x P x (1 - P) rounded up per order (fee rule 2026-10-03); Polymarket US taker theta 0.0695 x C x P x (1 - P) (docs.polymarket.us/fees, effective 2026-10-01; Andrew to confirm).
- Capacity: from recorded top-of-book size at each fill on polymarket.com (the websocket book has sizes). Polymarket US has no sizes in our recording (the 1 s poll returns prices only), so no capacity estimate is possible there; this is stated in the result.
- Holdout only (the recorded books exist only from 2026-10-03), run once with the lead test.
- Labels: polymarket.com "paper only; polymarket.com not available to US residents"; Polymarket US "US-executable version (Polymarket US); state eligibility as above".

### Polymarket US: state availability

No first-party state list was found: docs.polymarket.us has none, the polymarket.us pages are a JavaScript app with no state list in the page source, and polymarketexchange.com has none (checked 2026-10-03). Eligibility is screened in the app at sign-up (KYC), so Florida availability is to be confirmed in the Polymarket US app by a Florida-based team member, with a screenshot. Arizona: third-party guides list Arizona as unavailable ([pm.wiki](https://pm.wiki/nl/learn/is-polymarket-legal-in-the-us), [OddsAssist](https://oddsassist.com/prediction-markets/polymarket-us-states/)); no primary source naming Polymarket was found (the Arizona Department of Gaming's July 2026 cease-and-desist orders name other operators, [KOLD](https://www.kold.com/2026/07/10/arizona-issues-cease-and-desist-orders-five-online-gambling-sites/), [ADG release](https://gaming.az.gov/sites/default/files/C%26D%28s%29%20Press%20Release%20Final.pdf)). Earlier STATUS notes saying Arizona issued a cease-and-desist to Polymarket are unverified.

### Note for v3 Strategy B (not changed)

Strategy B stays as pre-registered. Stale polymarket.com trade prices can create fake Kalshi vs polymarket.com disagreements (a thin venue's last trade lags the true price; see the bias table); the 60 s staleness guard in v3 partly mitigates this. Strategy A is unaffected (single venue, settlement outcome).

### Multiple testing (changes to the v3 table)

| Family | Variants |
|---|---|
| Amendment 2 trade-the-laggard, polymarket.com (one fixed setting, books) | 1 |
| Amendment 2 trade-the-laggard, Polymarket US (one fixed setting, books) | 1 |

The 81-setting Part A and Part B grids are removed. Deflated Sharpe is reported with the number of trials set to the strategy's own count and to the total across v2, v3 and Amendment 2.

### Disclosure

Before this amendment: Time & Sales file structure, timestamp format, per-file row counts and per-game NFL/CFB trade counts (training period only) were checked; the synthetic activity-bias tests (trade-based and quote-based) were run on simulated data only; recorder row counts were checked for health. No Polymarket US price and no holdout price of any venue has been examined. Holdout Time & Sales files have not been downloaded. Recorder health checks on 2026-10-03 (counts only, no prices printed): on Polymarket US, 14:15 to 14:25 UTC, per-market counts of bid rows, ask rows, polls with one side missing, and crossed quotes (0); 5 of 10 updating markets had no ask on the home side because the gateway returned no bid on the long (away) instrument. The Polymarket US recorder writes exact-repeat rows when one side of the book is empty (in that window 1,500 of 1,517 Polymarket US rows were exact repeats, counted by equality only). The bug is fixed in commit 9c9b7b6 and will be deployed after Saturday's last game. Repeats are removed at read time and cannot affect results under the mid-change definition above; no row is dropped or changed by the bug.

Committed at 11:15 ET on 2026-10-03. No holdout prices, plots, or statistics were examined before this commit; only row counts and heartbeat health.

Committed before Alden's review; any change from his review will be a dated amendment made before any holdout data is examined.
