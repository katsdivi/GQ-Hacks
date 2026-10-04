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

## Amendment 1 (2026-10-03 11:42 ET)

Committed BEFORE any Strategy A or Strategy B code runs on data (training or holdout). Items marked PROPOSED need Alden's confirmation; if he changes them, that is a dated amendment made before any A or B result exists.

### 1. Combined Kalshi book (Strategy A + Strategy B)

- **Components.** Strategy A at the theta selected on training by v3's rule ("Best mean return on capital on train among thetas with at least 50 trades"). Strategy B at the setting selected on training by v3's rule, which v3 already fixes: "Selection, costs, fail conditions. As docs/stats_plan.md: best mean net edge per trade (Webull line) among settings with at least 30 trades". B's selection rule is not changed to return on capital.
- **Size.** Fixed and equal: 10 contracts per trade for A and for B (as in v3). Never optimized, never scaled by signal, price or past P&L.
- **Combined P&L.** Sum of A P&L and B P&L by calendar day (ET). A books P&L on the settlement date (v3 "Daily P&L by settlement date"); B books each trade's P&L on its exit date. Days with no trade on either strategy are 0 and stay in the series.
- **Capital base (PROPOSED).** Returns are daily P&L divided by a fixed capital base: the maximum, over training calendar days, of capital committed at once by the combined book (entry price plus entry fee of all open positions). The base is fixed from training and reused unchanged on the test set.
- **Metrics, in-sample (training) and out-of-sample (test) reported separately.** Annualized return (mean daily return x 365, PROPOSED), annualized volatility (daily std x sqrt(365), PROPOSED), Sharpe (ratio of those two), max drawdown, turnover (contracts traded and dollar notional per day), skew of daily returns, worst calendar month, equity curve, and the correlation of A and B daily P&L (all calendar days in the combined series, zeros included). The same metrics are reported for A alone and B alone.
- **Execution route.** Kalshi via Webull. Primary costs: Webull $0.02 per contract per fill (A: entry only, settlement is not a fill; B: entry and exit). Comparison: Kalshi direct taker fee 0.07 x C x P x (1 - P), rounded up to the cent per order. Both lines are reported.

### 2. Track-rule reporting

- **Costs x2.** Every strategy (A, B) and the combined book is also reported with costs doubled: fees x2 and the assumed half-spread x2 (1 cent becomes 2 cents for A entries and B trade fills). Latency is unchanged. Selection is never redone under doubled costs.
- **Factor regression.** Daily returns of A, B and the combined book are regressed on the Ken French daily factors Mkt-RF, HML and UMD (Fama/French 3-factor daily file and Momentum daily file, public data library), with an intercept and Newey-West standard errors (5 lags, PROPOSED). P&L on a day that is not in the French files (weekends and market holidays, which includes most Saturday college games) is assigned to the next day in the files. Reported: intercept (daily alpha), betas, t-stats, R-squared, in-sample and out-of-sample. If the French files do not yet cover the test period when the test is run, the out-of-sample regression is reported as "not available" with the last covered date; it is not estimated on partial data.

### 3. Kickoffs for Strategy B

- v3 says kickoffs come from ESPN only under Strategy A; Strategy B did not specify. This amendment extends the rule to B: B uses ESPN scoreboard kickoffs only.
- B game window: [ESPN kickoff - 30 min, ESPN kickoff + 4.5 h].
- A training game whose T8 polymarket.com data does not cover that window is excluded from B and listed with the reason. Coverage is judged from the T8 download window ([T8 kickoff - 2 h, T8 kickoff + 5 h], ingest/download_all.py). No T8 file is re-windowed or re-downloaded by hand.
- Known now (docs/results/t8_kickoff_check.md, metadata only): 14 of 977 T8 games have a T8 kickoff more than 15 min from ESPN, and all 14 fail coverage, so they are excluded from B: cfb_20251129_ore_wash, cfb_20251129_cin_tcu, cfb_20251129_hou_bay, cfb_20251129_colo_ksu, nfl_20251208_phi_lac, nfl_20251225_det_min, nfl_20251225_den_kc, cfb_20250913_usc_pur, cfb_20251129_ucla_usc, cfb_20250913_fau_fiu, cfb_20251018_txam_ark, cfb_20250920_tem_gt, cfb_20251018_utsa_unt, cfb_20250913_ull_mizz.
- Strategy A is unaffected: it uses its own Kalshi download (ingest/kalshi_only_train.py), windowed on the ESPN kickoff (docs/strategy_a_rules.md).

### 4. Strategy A entry fill (correction)

- **Decision, unchanged, backward as-of only.** Favorite, theta check and the 10-minute staleness check use Kalshi data at or before t = ESPN kickoff - 5 min (v3's trailing 3 s median of trade prices, as-of t).
- **Fill.** The first Kalshi trade on the favorite's own market at or after t + 1.0 s (the docs/spec_provisional.md default latency), plus 1 cent half-spread. If there is no such trade within 5 minutes after t, the game is skipped and listed.
- **Reason.** v3 lines 13 and 15 fill at the as-of price at t ("buy ... at the as-of price + 1 cent"), which violates CLAUDE.md rule 1 (fills happen at t + latency, never at t). Corrected before any Strategy A code or result existed.
- **Reported.** The count of games skipped for no post-decision trade, per theta.

### 5. Strategy B fill (correction)

- v3 B fills at "Kalshi as-of t + latency (1 s)". As written, if there is no Kalshi trade in (t, t + 1 s], the as-of value is a pre-decision price.
- **Fill.** B's fill is the first Kalshi trade at or after t + 1.0 s (plus the v3 half-spread); if none within 60 s, the trade is skipped and counted. This applies to entries and exits.
- **Reason.** Same as section 4: a fill must not use a price from before t + latency (CLAUDE.md rule 1). Corrected before any Strategy B code or result existed.

### 6. Multiple testing

The combined book is one more trial. Updated table (replaces the v3 table; includes HYPOTHESIS_v2.md Amendment 2, which removed the 81-setting grids):

| Family | Variants |
|---|---|
| v2 exploratory (experiments/variants.csv, nfl_20251116_was_mia only) | 7 |
| v2 Amendment 2 trade-the-laggard (one fixed setting each: polymarket.com, Polymarket US) | 2 |
| v3 A: theta grid | 3 (+3 underdog placebo) |
| v3 B: k x m x T grid | 8 (+8 unrelated-game placebo) |
| v3 Amendment 1: combined A + B book | 1 |
| Total trading variants | 21 (+11 placebo runs) |

Deflated Sharpe (Bailey and Lopez de Prado, 2014) on daily returns, with the number of trials set to (1) the strategy's own count (A: 3, B: 8, combined: 1) and (2) the total, 21.

### 7. Disclosure

Drafted 11:31 ET Oct 3; fill corrections (sections 4 and 5) added on Divi's approval before commit. No Strategy A or B code or result, on training or holdout, existed when this was written or committed. T8 kickoff errors found during a coverage check (no prices or results examined).

Also seen before this amendment (incidental, no Strategy A or B computation): the Albany at Iowa 2025-08-30 settlement (Iowa won) and the ids of 3 blank-result NFL preseason games (docs/strategy_a_rules.md); per-game Kalshi trade counts in out/kalshi_only_train.log; the v2 who-leads summary (docs/results/v2_who_leads.md).

## Amendment 2 (2026-10-03 13:57 ET)

Committed before Strategy A is run on training data. Both are choices v3 and v3 Amendment 1 leave open; strategy_a.py implements them. No Strategy A result exists.

1. No favorite: if the two teams' own-market as-of prices at t (trailing 3 s median, as-of t) are equal, the game has no favorite and is skipped and listed ("no favorite (equal prices)"). It is not traded on either side.
2. Underdog placebo fill: the underdog placebo (v3 "buy the underdog ... at its own as-of price + 1 cent") uses the corrected fill of v3 Amendment 1 section 4 on the underdog's own market: the first underdog-market trade at or after t + 1.0 s, plus 1 cent; skipped and counted if there is none within 5 minutes after t. The placebo decision (favorite >= theta, staleness on the favorite's market) is the favorite leg's decision.

Disclosure: committed 13:57 ET Oct 3. No Strategy A or B code has run on real data; strategy_a.py has run only on fake games in tests/test_strategy_a.py.

## Amendment 3 (2026-10-03 19:40 ET)

Six Strategy A choices that v3 and v3 Amendments 1 and 2 leave open, fixed before any Strategy A result exists. Committed before Strategy A is run on training data. strategy_a.py implements all six (branch t13-strategy-a, a3e4a55). No Strategy A trade, fill, return or win rate has been computed; the only computation on real data is the orientation check in the Disclosure (no P&L).

### 1. Ties and Kalshi scalar settlements

A game settles at Kalshi's own recorded settlement value. When Kalshi marks a market result "scalar", the home-team market's `settlement_value_dollars` is the payout per contract (1 minus the away market's value if only the away market is found). This applies docs/strategy_a_rules.md section 1 ("Before a blank is treated as a tie, the Kalshi market metadata must show the scalar settlement at 0.5").

Checked 2026-10-03 from Kalshi market metadata (`/historical/markets/<ticker>`: fields status, result, settlement_value_dollars only; no price fields read):

| game | Kalshi event | home market | away market | settled at |
|---|---|---|---|---|
| nfl_20250929_gb_dal (GB at DAL, 2025-09-28, 40-40 tie) | KXNFLGAME-25SEP28GBDAL | DAL: finalized, scalar, 0.5000 | GB: finalized, scalar, 0.5000 | 0.5 |
| nfl_20250808_lv_sea (preseason) | KXNFLGAME-25AUG07LVSEA | SEA: finalized, scalar, 0.5000 | LV: finalized, scalar, 0.5000 | 0.5 |
| nfl_20250810_mia_chi (preseason) | KXNFLGAME-25AUG10MIACHI | CHI: finalized, scalar, 0.5000 | MIA: not found (404) | 0.5 |
| nfl_20250817_jac_no (preseason) | KXNFLGAME-25AUG17JACNO | NO: finalized, scalar, 0.5000 | JAC: finalized, scalar, 0.5000 | 0.5 |

GB at DAL: Kalshi's recorded value is 0.5, which matches the v3 tie rule. The other three blank-settlement games (all NFL preseason) also have a populated Kalshi result field (scalar, 0.5); the downloader maps only yes/no. These four stay in the sample (v3: tied games are never dropped).

How it is applied (a code step; the games file is never edited): ingest/kalshi_market_meta.py records, for both team markets of every training game, Kalshi's status, result and settlement_value_dollars (plus the tick and liquidity fields of sections 3 and the report; no price fields) in data/raw/kalshi_market_meta.csv. strategy_a.load_games reads the games file as downloaded and applies strategy_a.apply_scalar_settlements: where settlement_result is blank and the home market's result is "scalar", the result is its settlement_value_dollars; else, if the away market's is, 1 minus that value; a blank with no scalar record stays blank (and the game is skipped as "unsettled"). Each game carries settlement_source ("yes/no" or "kalshi scalar (home market)"). Test: tests/test_strategy_a.py::test_scalar_settlement_step_on_the_four_blank_games (the four games above, MIA at CHI with the away market not found). Result on the training file: 1,263 games settled yes/no in the file, 4 settled by the scalar step (exactly the four above, 0.5 each, from the home market); 777 home wins, 486 home losses, 4 at 0.5; 0 still blank.

### 2. NFL preseason

NFL preseason = NFL games whose ESPN kickoff (US Eastern date) is before that season's regular-season opener: Thursday Sep 4, 2025 for the 2025 season (training), Wednesday Sep 9, 2026 (Patriots at Seahawks) for the 2026 season (test set). This is the Hall of Fame game and the rest of the preseason. strategy_a.load_games asserts the count is 49 on the training file. A season with no opener date set raises an error instead of guessing. Tests: Sep 3, 2025 ET is preseason and Sep 4 is not; Sep 8, 2026 ET is preseason and Sep 9 is not. These games stay in the primary run. A robustness run without them is reported side by side with the primary run (same theta grid, same costs). It is a robustness report, not a trading variant: theta is selected on the primary run only, and the robustness run never changes the selected theta or the test-set rule.

### 3. Fill price cap

Fill = min(first post-decision trade + 1 cent, 1 - tick), where tick is the price step of that market's top price range in Kalshi's metadata (`price_ranges`, field step; `price_level_structure`), 0.01 if the market's metadata was not found. A trade at the top valid price would otherwise give a fill above it, which is not a valid Kalshi price. Training markets (metadata only, both team markets of all 1,267 games, which covers every favorite market without identifying favorites, since that needs prices): 2,534 markets, all found, all price_level_structure linear_cent with one range 0 to 1 at step 0.01 (count at 0.01: 2,534; other: 0). So the cap is 0.99 for every training market, the same as the earlier fixed cap. The number of capped fills is reported per theta (favorite leg and underdog placebo leg) in the Strategy A output (column n_capped_fills). A capped fill is kept, not skipped.

### 4. Conference championships and Super Bowl

Excluded. Reason, from Kalshi series and market metadata (searched 2026-10-03, about 5 min, no prices):
- The 2026-01-25 conference championships: series KXNFLGAME has only KXNFLGAME-26JAN25LASEA (LA at SEA), a duplicate with zero volume on both markets, and no event for NE at DEN. Series KXAFC and KXNFC have no 2026 event (KXAFC has only the 2025 event); KXNFLAFCCHAMP and KXNFLNFCCHAMP have no settled 2026 event with markets.
- Super Bowl LX (2026-02-08, SEA vs NE): only in KXSB-26, a 32-market season futures event ("Will <team> win the 2026 Pro Football Championship?"), not a two-market game event. Using it would need a different game definition (two of 32 markets, prices not complementary by construction), so it is not added under the same pipeline.
- NFL training games therefore end with the divisional round (last kickoff 2026-01-18). Training: 1,267 games (CFB 936, NFL 331); the seal check (kickoff < 2026-08-01) is unchanged.

### 5. Team markets and games with a missing market

Each game's two team markets are taken from the market ids in its downloaded trade file (strategy_a.team_markets): home = the games file's kalshi_ticker; away = the event's other market. Team codes are everything after "<event>-" in the ticker. Reason: the downloader cut team codes at the last hyphen, so Miami (OH), Kalshi code "M-OH", appears as "OH" in the games file; built from that code, its market id does not exist and those games would have been skipped. 13 training games involve Miami (OH) (7 away, 6 home); all 13 have trade rows on both markets and are kept. The games file is not edited; the downloader is not changed (its codes also feed ESPN and Polymarket matching and game ids), and a comment marks the issue there.

A game whose trade file does not hold both team markets is excluded, never traded from one side (the favorite needs both own-market prices). Skip reason "missing market (<ticker>: no rows in the trade file)". Training: 1 game, cfb_20250831_lam_unt (LAM at UNT, KXNCAAFGAME-25AUG30LAMUNT). The UNT market exists under its expected ticker (KXNCAAFGAME-25AUG30LAMUNT-UNT, finalized, result yes; not the hyphen issue), but all 33 of its trades are from 2025-08-18 to 2025-08-30 21:47 UTC, the last one 2 h 12 min before the ESPN kickoff (2025-08-31 00:00 UTC), so it has 0 trades in the standard download window [kickoff - 2 h, kickoff + 5 h] used for every game, and its trade file holds only the LAM market (6 trades). Including it would need a different window for one game, so it stays excluded. (Checked from trade timestamps only.) Test: tests/test_strategy_a.py::test_game_with_one_missing_market_is_excluded_not_traded.

### 6. Staleness on both markets (added 2026-10-03 18:20 ET, before any Strategy A run)

At t = kickoff - 5 min, each team's own market must have at least one trade in (t - 10 min, t]. If either market has none, the game is skipped (reason "stale (no trade in the 10 min before t: <ticker>)") for every theta and both legs, and counted per theta (n_skipped_stale). The favorite is chosen only when both prices are fresh. This replaces the favorite-only check (v3 Amendment 2 item 2: "staleness on the favorite's market"; the placebo leg uses the same both-markets decision): an old underdog price can decide which team is the favorite (with a fresh favorite at 0.72 and an underdog last traded at 0.20 fifteen minutes earlier, the favorite-only rule would enter). Fake-game tests: tests/test_strategy_a.py::test_staleness_on_both_markets (underdog stale skipped; both fresh unchanged; a stale underdog that would decide the favorite skipped, where the previous rule entered). Rule only; no Strategy A result exists.

### Disclosure

Drafted 15:50 to 18:20 ET Oct 3, reviewed by Divi (walkthrough docs/review/strategy_a_walkthrough.md approved before this commit). Seen while preparing this amendment (incidental, no Strategy A computation): the Kalshi settlement fields above for the four blank-settlement games, the market lists and volume totals of the Kalshi series named in section 4, the count of NFL preseason games, and the key names of one Kalshi market object plus the counts of price_level_structure and tick step over the 2,534 training markets (no price field was kept). For section 5, only the market_id column of each game's trade file was read (market ids and row counts per market). Excluded game: cfb_20250831_lam_unt, reason above. No entry prices, fills, returns or win rates have been computed or looked at.

Orientation check (run after the walkthrough was approved, before this commit; Divi's pre-run gate, training only, no fills or P&L): for every training game that reaches the favorite decision (ESPN kickoff, both markets present, both fresh, both priced at t), home own-market price + away own-market price at t (the as-of medians decide() uses): 1,135 games, median 1.0100, p5 1.0000, p95 1.0200, 0 outside [0.90, 1.10]. Gate: median in [0.97, 1.05] and under 2% outside: PASS. Before the decision, 122 games were skipped as stale and 9 for no pre-decision price.

## Amendment 4 (2026-10-03 23:20 ET): holdout scope for Strategies A and B, and complete holdout files

Committed before the holdout run of Strategies A and B and before any holdout price, plot or statistic is examined.

### 1. Holdout games

The holdout games for Strategies A and B are the Kalshi game events (KXNFLGAME, KXNCAAFGAME) with an ESPN kickoff from 2026-08-01 through 2026-10-03 20:00 ET, the same cutoff as HYPOTHESIS_v2.md Amendment 4. Games ESPN does not have are dropped and listed (v3, unchanged). Strategy B's holdout games are those of them matched to a polymarket.com moneyline (current series 12185 NFL, 12756 CFB) by the same matcher as training (ingest/download_all.match_games).

- Kalshi game events dated 2026-08-01 to 2026-10-03 with two team markets: 780.
- No ESPN kickoff found (dropped, listed by v3): 7 (KXNCAAFGAME-26AUG27LAFGTWN, -26AUG28UNHALBY, -26OCT03DSUALBY, -26SEP03ALBYBUFF, -26SEP12ALBYLIU, -26SEP19MONMALBY, -26SEP26ALBYPRIN).
- Kept for Strategy A: 768 (98 NFL, 670 CFB), ESPN kickoffs 2026-08-06 20:00 ET to 2026-10-03 20:00 ET.
- Dropped by the 20:00 ET cutoff: 5, all CFB on Saturday 2026-10-03: cfb_20261004_fres_wsu (21:30 ET), cfb_20261004_bay_asu (22:30), cfb_20261004_ewu_ucd (22:30), cfb_20261004_txst_sdsu (22:30), cfb_20261004_cin_ariz (23:00).
- Strategy B: the kept games matched to a polymarket.com moneyline; the matched and unmatched counts are reported in the holdout run disclosure (the polymarket.com download was still running when this was committed).

### 2. Complete files only

A game's holdout file must be written after its window has ended: kickoff + 5 h for the downloaded trades (Strategy A uses [kickoff - 2 h, kickoff + 5 h]); kickoff + 4.5 h is Strategy B's window end and is inside it. Any game whose file was written before its window ended is refetched (scripts/stop_and_sync.sh, after the recorders stop, starting no earlier than the last included window end, 01:00 ET 2026-10-04). The run's checklist verifies that every A and B holdout file was written after its game's window end. Games still unsettled at the run stay excluded under the existing rule (strategy_a: "unsettled").

### Disclosure

No holdout prices, plots or statistics were examined. The issue was found by the downloader's completeness check at 22:48 ET on 2026-10-03: 38 games of 2026-10-03 had been downloaded while their [kickoff - 2 h, kickoff + 5 h] window was still open (row counts and file timestamps only). The counts above come from game ids, ESPN kickoff times and file listings only.

## Amendment 5 (2026-10-03 23:45 ET): Strategy A-maker, one new pre-registered variant

Committed before the holdout run of any strategy and before any holdout price, plot or statistic is examined.

### Rule

Strategy A-maker uses Strategy A's decision unchanged (v3 with Amendments 1 to 4): t = ESPN kickoff - 5 min; each team's own-market price is the trailing 3 s median of trades as-of t; both markets must have traded in (t - 10 min, t]; the favorite is the higher price; enter iff the favorite's price >= theta, with theta = 0.80 fixed (no grid). Same seal, ESPN-kickoff, missing-market and exclusion rules.

- Order: a limit buy of 10 contracts on the favorite's own market at L = (the as-of price at t) - 0.01, rounded to the market's tick.
- Fill (conservative, queue-agnostic): filled at L only if a trade on that market prints at or below L - 0.01 in (t + 1 s, kickoff]. Otherwise the order is unfilled: no trade, counted ("unfilled").
- Hold to settlement, settled as Strategy A (Kalshi's recorded result; ties and scalar settlements at Kalshi's value).
- Costs: Webull $0.02 per contract, entry only (primary). Comparison line: Kalshi's maker fee was not confirmed first-party (kalshi.com/docs/kalshi-fee-schedule.pdf returned HTTP 429 on 2026-10-03; secondary sources state 0.0175 x C x P x (1 - P) rounded up, charged on some markets only; docs/research/fees.md has no Kalshi maker entry), so the comparison line uses the taker formula 0.07 x C x P x (1 - P) rounded up to the cent as an upper bound, labelled as such.
- Costs x2: fees x2 and the fill 1 cent worse (the maker analog of the taker's doubled half-spread), same fill set.
- Placebo: the underdog's own market with the same maker rule (L = the underdog's as-of price - 0.01), whenever the favorite passes theta.
- Reported, training and test: attempts, fills, fill rate, unfilled count, skips by reason, mean fill, win rate minus fill price, return on capital on both lines with a game-level bootstrap 95% CI (2,000 resamples, seed 20261003), total P&L, costs x2, and the placebo.
- Code: strategy_a_maker.py (fake-game tests: fill only on a trade-through, no fill from a trade at or before t + 1 s or after kickoff, unfilled counted), run_strategy_a_maker.py, walkthrough docs/review/strategy_a_maker_walkthrough.md.

### Multiple testing

One more trading variant (favorite leg; the underdog leg is its placebo): 21 -> 22. The deflated Sharpe "total" count becomes 22.

### Disclosure

Designed on training after seeing taker-A training results (v3 Strategy A, theta 0.80: win rate 0.911 vs mean fill 0.898; the $0.02 Webull fee more than cancels the gap); the holdout was not examined. The rule above was set by Divi at about 23:20 ET on 2026-10-03, before any A-maker number existed, and was then run once on training (no parameter changed afterwards): favorite 25 fills of 357 attempts (7.0%), mean fill 0.856, win rate 0.920, ROC Webull +0.048 [-0.087, 0.151]; underdog placebo 23 fills of 351, every one a loss. These two training rows are in experiments/variants.csv.

## Orientation mismatches vs ESPN (decided before any holdout result)
Pre-run orientation check found 4 holdout A/B games where a venue's home/away label differs from ESPN's nominal home team: Alabama A&M vs Howard (2026-08-29), Southern vs Alabama St (2026-08-29), Grambling vs Prairie View (2026-09-26, State Fair Classic), all neutral-site; and Dallas at Seattle (2026-08-15, NFL preseason), where polymarket.com lists the teams in reverse order and the matcher set flipped = True. In all 4, Kalshi and polymarket.com refer to the same team for each price. Strategy A and A-maker trade each team's own Kalshi market and settle on it; Strategy B compares the same team across venues; ESPN supplies kickoff time only, which matched. Decision: all 4 games kept, listed in the run disclosure. None is in the lead-test holdout.
