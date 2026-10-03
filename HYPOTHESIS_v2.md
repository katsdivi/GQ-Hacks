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

## Amendment 3 (2026-10-03 18:14 ET): Alden's review of Amendment 2, venue rules, runner choices

Committed to main before the Amendment 2 holdout run and before the evening (7 PM ET and later) kickoffs of 2026-10-03. It changes the window start, adds Holm across the two venues, counts Kalshi REST-fallback time as outage, adds the polymarket.com venue rules (book wipe at game start, per-market taker delay), states the power, the placebo design and the 60% rule's role, and fixes the implementation choices Amendment 2 left open. Code: lead-test runner holdout_mid.py and xcorr_lead.py (branch t13-strategy-a, 04d3bdd); trade-the-laggard evaluator laggard.py (branch t14-laggard, cd5eea2); delay fetch ingest/seconds_delay.py (04d3bdd). No holdout prices, plots or statistics have been examined.

### Changes to Amendment 2

1. Window start: kickoff - 90 min (was kickoff - 30 min). Reason: availability and inactive news arrives about 90 min before kickoff. Kickoff - 120 min was rejected because it excludes every noon kickoff under the outage rule (Vultr started 10:08 ET; the Mac had a 116 s Kalshi outage at 10:13 ET). This was decided from recorder logs only (GAPS tables and heartbeats, no prices): of the 17 games kicking off at 12:00 ET, a clean machine exists for 0 under kickoff - 120 and for 17 under kickoff - 90. At 13:43 ET, of the games already past their window start, 39 of 44 had a clean machine under kickoff - 90 and 36 of 40 under kickoff - 30 (all clean games on Vultr; the games with no clean machine are Friday-night games). The window end is unchanged.
2. Kalshi REST fallback counts as outage time for the lead test: REST polling degrades timing and biases Kalshi late. Every kalshi_ws gap is a Kalshi outage, and so is any span where the REST fallback reported connected (heartbeat kalshi_rest; each connected heartbeat covers 15 s).
3. Holm across the two venue tests: the smaller Mann-Whitney p is judged at 0.025; only if it passes is the larger p judged at 0.05. If the smaller p fails, neither venue can be called a lead. All other criteria are unchanged.
4. Mann-Whitney is computed with scipy.stats.mannwhitneyu (two-sided). This is an implementation change, not a method change: on lag arrays with ties (lags are whole seconds) it equals the earlier hand-written normal approximation with tie and continuity correction to 1e-9 (tests/test_mw_holm.py).

### Venue rules

13. polymarket.com rules (sources quoted). Polymarket help center, "Limit Orders" (help.polymarket.com/en/articles/13364444-limit-orders): "Specifically for sports markets, any outstanding limit orders are automatically cancelled once the game begins, clearing the entire order book at the official start time." and "Additionally, sports markets include a 3-second delay on the placement of marketable orders." docs.polymarket.com (order lifecycle): "Sports/game delay: enabled on configured sports markets around live game conditions. The order waits for the market's configured delay window before matching", with order status `delayed` and the per-market setting `market.trading.secondsDelay`. The help center's 3-second figure is not used: the delay is set per market (item 13a), and Polymarket says it is testing a 1-second taker delay on NBA and MLB markets (docs/market_structure.pdf, Andrew, sha256 prefix 0e31fa562701d1f0).
13a. Per-market delay, frozen. For the 112 frozen holdout polymarket.com markets, the delay was read from the public CLOB market object (GET clob.polymarket.com/markets/<condition_id>, field `seconds_delay`; the Gamma market object carries no delay field) on 2026-10-03 at 20:22 UTC (16:22 ET). Only the condition id and seconds_delay were kept; every other field of the response (prices, outcome prices, volume, resolution) was dropped in memory before anything was written, printed or hashed. File: data/live/holdout_seconds_delay.csv (market_id = condition id, seconds_delay, fetched_at_utc; gitignored), sha256 prefix 24a5d41af0ba7f34. Values: 1 s for all 112 markets; 0 at 3 s, 0 other, 0 missing. So the help center's 3-second figure does not describe these markets. The value was read once, now, not as of each game's kickoff: if Polymarket changed a market's delay during the day, the file does not show it. The file is frozen and used as is.
13b. Polymarket US rules. The Polymarket US Rulebook (Rules 5.4 to 5.5) and the Athletic Outcome Contract terms document no sports taker delay and no game-start book wipe (docs/market_structure.pdf). No taker delay is applied to Polymarket US fills. The kickoff cut of item 14 is still applied to the Polymarket US test, as a precaution: we cannot see in these recordings whether its book clears at kickoff (item 15), and the same cut on both tests keeps them symmetric.
14. Book-wipe exclusion for the lead test. For each game and each venue test, on that test's other venue (polymarket.com or Polymarket US): find the first second at or after ESPN kickoff - 30 min where that venue's book has neither side (full clear). Exclude, for BOTH venues of the test, from 2 min before that second until 5 min after the book is two-sided again (to the window end if it never is). If no clear is found, exclude [T - 2 min, T + 20 min], where T is the earlier of the ESPN scheduled kickoff and the polymarket.com market's gameStartTime. The frozen polymarket.com map records gameStartTime (field `game_start`, copied from Gamma) for all 112 mapped markets; it equals the ESPN kickoff for 111 and is 1 min later for 1, so T is the ESPN kickoff for every game in this holdout. The same T and the same interval apply to both venue tests, including the Polymarket US test (item 13b). The window was widened from + 10 min to + 20 min because the length of the post-kickoff re-quote period is not observable in these recordings (item 15); in a synthetic test (tests/test_book_wipe.py) where the other venue copies Kalshi 5 s late for 15 min after kickoff, a + 10 min cut leaves a false 5 s Kalshi lead in 15 of 20 games and a + 20 min cut leaves it in 0 of 20. Mid changes never span an excluded interval (the first defined mid after it has no previous mid), and the 50 mid-change qualification count is taken outside it. A placebo pair uses game A's exclusion. The runner reports the excluded seconds and the source (clear or fallback) per game; the per-game numbers are printed at the pre-registered run, not before.
15. Observability of a clear (recorder logs and row counts only, no prices). The collector writes no row when both sides of a book are empty, so a full clear is not visible in the 2026-10-03 recordings; the fallback interval is therefore the operative rule for every game in this holdout, on both tests. The same applies to Polymarket US (both-empty polls write no row). In the four 15:00 ET kickoffs recorded on the Mac with no polymarket.com gap, there were 0 one-sided snapshots on either venue within kickoff - 10 to + 20 min, so we cannot tell whether the Polymarket US book clears at kickoff.
15a. Limitation (disclosed, not corrected). Because the collector writes no row when both sides of a book are empty, an empty period anywhere outside the excluded interval is invisible in these recordings: the last two-sided quote before it is also the last row, and the as-of mid carries across the empty period until the next two-sided quote. This is contrary to Amendment 2's mid rule ("a mid is never forward-filled across a missing side"), which assumed an empty book would be visible. The collector is not changed mid-recording: a code change and restart during the holdout would itself create outages, would make the recordings before and after the change follow different rules, and would be a change made while holdout games are being recorded. The effect is therefore disclosed rather than corrected. Expected direction (not measured): a carried mid is stale, so it should mainly add apparent lag to the venue whose book was empty, for the length of the empty period.

### Trade-the-laggard (exploratory evaluator, not the lead test)

16. Fill timing. A taker fill happens at decision + venue delay + latency. polymarket.com: the venue delay is the market's own seconds_delay from data/live/holdout_seconds_delay.csv (item 13a: all 112 holdout markets at 1 s, read 16:22 ET); a market missing from the file would get 3 s and be counted (0 such markets). Polymarket US: 0 s (item 13b). latency_s in the output is the total time from decision to fill, so each market's latency curve starts at its own delay (the per-market value from holdout_seconds_delay.csv, 1 s for all 112 polymarket.com markets; 0 s on Polymarket US).
16a. No carry across breaks. Breaks are the excluded interval of item 14 and every outage of either venue (GAPS rows, as in item 10, here including those of 60 s or less, which do not exclude a game). Inside a break neither venue has a mid; after it, a venue's mid stays undefined until that venue's first snapshot received after the break ends; no mid is carried past the window end. A fill is skipped, never filled from an older quote, when its time falls inside a break, when a break lies between the last snapshot and the fill time, when it is at or after the window end, or when the needed side is empty; skips are counted by reason. A round trip whose exit is skipped is skipped as a whole. This applies to the laggard evaluator only; the lead test is unchanged (item 15a).
16b. Capacity. polymarket.com: the collector records the size at the best level only. A taker fill at the best quote can take at most that level (deeper levels are at worse prices), so capacity per trade = best-level size at the fill time (after the delay), in contracts and in dollars at the fill cost (P for a buy, 1 - P for a sell, home terms). Reported: median per trade and total per game. Polymarket US: sizes are not recorded (the 1 s batch poll returns no sizes, and the size endpoint answers HTTP 429), so Polymarket US capacity is not measurable and is reported as such.
17. Interpretation: "A measured polymarket.com lag near 1 s may reflect its 1 s taker delay (a venue rule), not slower information."

### Diagnostic (reported, NOT a decision rule)

18. Receipt delay. At the run, per machine and per venue, the median and p90 of (receipt time minus venue-side timestamp), over the rows of the instruments and windows of the games run on that machine (holdout_mid.receipt_diagnostic). Only rows that carry a venue-side timestamp count: Kalshi websocket orderbook_delta rows (ts_ms, ms resolution; orderbook snapshot and REST rows carry none) and polymarket.com book rows (message timestamp, ms) and trade rows. Polymarket US rows carry no venue-side timestamp (the public batch poll returns none), so its value is reported as not available. Nothing is decided from it.

### Statements

5. Power: "Power results from sim run (a), seed 20261003, started 15:57 ET, will be appended in a note that changes no rule."
5a. Placebo design: "The placebo pairs each qualifying game A with the next qualifying game B (Design 1, about n - 1 pairs), under the same window, machine and kickoff-proximity rules as item 12." Design 1 is the pre-registered default, and it is used for both venue tests. The rule fixed before the simulation reads jointly over both venues: adopt Design 2 (each game paired with the next K = 5, about 5n pairs) only if its full-rule false-positive Wilson 95% upper bound is <= 6% at n = 30, 40 and 60 under both the zero-lag null and a shared-shift null (real and placebo lags from the same distribution, centered at +2 s). Choosing per venue after seeing that Polymarket US alone passes would be choosing the rule after the result, so it is not done. Design 2 results (full-rule rate [Wilson 95% CI], 500 reps, seed 20261003, docs/results/sim/README.md): zero-lag null 0.000 [0.000, 0.008] at every n, both venues; shared-shift null, polymarket.com 0.046 [0.031, 0.068] at n = 30, 0.036 [0.023, 0.056] at n = 40, 0.058 [0.041, 0.082] at n = 60; Polymarket US 0.014 [0.007, 0.029], 0.038 [0.024, 0.059], 0.032 [0.020, 0.051]. The rule was strict by construction: a test sized exactly at 5% has an expected Wilson upper bound of about 7.3% at 500 reps, so it can fail a correctly sized design by chance, and Design 2's point estimates are no worse than Design 1's (polymarket.com shared-shift, Design 1: 0.052, 0.058, 0.048). Under the zero-lag null, Mann-Whitney alone rejects 8 to 12% of the time with Design 1 (0.082 to 0.120): when every real lag is 0, the small Design 1 placebo sample often sits off 0. The median >= 1 s gate is what controls false positives there (full-rule rate 0.000 at every n).
6. The 60% rule (>= 60% of qualifying games with lag > 0) is a consistency guard, not the significance test. Under no lead, P(>= 60% positive) is 0.18 at n = 30 and 0.08 at n = 60; the significance test is Mann-Whitney against the placebo.

### Implementation choices (left open by Amendment 2)

7. Instrument per venue: one instrument per venue per game, never merged: Kalshi home-team market (`<event>-<HOME>`), polymarket.com home-team token (the token the collector recorded as home), Polymarket US moneyline slug. Away instruments are not used.
8. Frozen maps in `data/live/holdout_maps/`: polymarket_com_map.json sha256 prefix 202f819d1bd885dd, polymarket_us_map.json 4225d018acb3024e. All 112 polymarket.com markets matched, with outcome order [away, home] confirmed against the Kalshi teams for all 112. A mapped instrument with no recorded rows is excluded as "no rows" (3 Friday-night games have no polymarket.com rows on either machine).
9. Window end: when a pinned run (mid >= 0.98 or <= 0.02 for 60 s) occurs, the window ends at the start of that run.
10. Outage length: a single logged gap overlapping the window by more than 60 s; GAPS rows with venue "all" (restarts) apply to every feed.
11. Feed start: the first heartbeat of that feed with a delivered message (last_ok set). Heartbeats began 09:52 UTC on the Mac and 14:08 UTC on Vultr; earlier recording on the Mac (Kalshi from 03:09 UTC) therefore counts as not started, which only affects Friday-night games, already excluded. A machine with no heartbeat log would fall back to its first recorded file.
12. Placebo window: a placebo pair (Kalshi from game A, other venue from game B) uses A's window for both series; B is the next qualifying game in kickoff order on the same machine, with kickoff within 30 min after A.

### Disclosure

Reviewed by Alden 11:55 ET Oct 3. No holdout prices, plots, or statistics were examined; only row counts, ids, and heartbeat logs (GAPS tables, heartbeat files, market ids present in the recordings, Gamma listings). For item 15, only the ts and kind columns of polymarket.com and Polymarket US rows near kickoff were read (counts of snapshots, one-sided snapshots and trades per minute, Mac recordings, 15:00 ET kickoffs), on 2026-10-03 about 15:25 ET. For item 13a, one probe on one market printed only the key paths containing "delay" (Gamma: none; CLOB: seconds_delay), then the fetch kept only condition id and seconds_delay (16:22 ET). For item 18, only the column names of one recorded file per venue were read; no timestamp values.

### Note to Amendment 3: power

Appended 19:30 ET 2026-10-03; changes no rule. Simulation run (a), seed 20261003, 500 studies per cell, started 15:57 ET and finished 19:03 ET (docs/results/sim/README.md, part (a), and docs/results/sim/a/, branch t13-strategy-a at 3825678). If Kalshi truly leads by 5 s with per-game jitter N(0, 2 s), the full rule calls "Kalshi leads" in 47% to 80% of studies with 30 to 60 qualifying games at alpha 0.025 (the Holm level for the smaller p), and in 59% to 86% at alpha 0.05; with 80 games, 85% to 89% at alpha 0.025. With no link it called a lead in at most 1.2% of studies per cell (Wilson upper bound 2.6%), with zero lag in 0 of 500 per cell, and it never called the reverse direction. Power was simulated only for a true 5 s lead; it was not measured for smaller leads and will be lower for them, so an inconclusive result does not mean there is no lead. The simulated placebo has n pairs; the pre-registered Design 1 has about n - 1.
