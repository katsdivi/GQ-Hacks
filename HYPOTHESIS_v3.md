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
