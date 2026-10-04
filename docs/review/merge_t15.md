# Merge prep: t15-final vs main (do not merge until Divi says "merge t15")

Generated 2026-10-03 20:54 ET at f17f79b. main = f6aa3b5. The real run launches from main at the merge commit.

- Commits on t15-final not on main: 74 (3 merges: t9-costs into t14, t14-laggard into t15, t13 into t15).
- Diff:  82 files changed, 57654 insertions(+), 44 deletions(-).

## Rule-7 files

| file | commits vs main | last change | line-by-line review |
|---|---|---|---|
| strategy_a.py | 6 | a3e4a55 10-03 18:16 | REVIEWED: walkthrough approved by Divi after a3e4a55 (docs/review/strategy_a_walkthrough.md); no change since |
| strategy_b.py | 1 | ac2ffad 10-03 19:49 | PENDING: walkthrough docs/review/strategy_b_walkthrough.md written, not yet reviewed |
| costs.py | 4 | ba36a6a 10-03 15:49 | NOT RECORDED: fee schedules from Andrew's fees.md, hand-tested (tests/test_costs.py); no line-by-line review on record |
| laggard.py | 3 | cd5eea2 10-03 17:07 | PENDING: not reviewed (synthetic tests only) |
| xcorr_lead.py | 3 | 2c23dec 10-03 15:27 | NOT RECORDED: behavior described in committed v2 Amendments 2 to 4; no line-by-line review on record |
| holdout_mid.py | 6 | a132047 10-03 20:26 | NOT RECORDED: behavior described in committed v2 Amendments 2 to 4; no line-by-line review on record |
| strategy.py | 1 | 19a1001 10-03 01:15 | NOT RECORDED: placeholder fee replaced by Andrew's schedules (19a1001) |
| backtest.py | 1 | 19a1001 10-03 01:15 | NOT RECORDED: placeholder fee replaced by Andrew's schedules (19a1001) |
| leadlag.py | 0 | none | unchanged |

## Commits

```
f17f79b Add holdout home/away check (ids only), the 00:30 stop-and-sync sequence (prepared, VULTR_HOST from env), and --checklist-only
99509ca Final run: orientation gate first (aborts A and B on FAIL, lead test still runs, reason in RUN_LOG); dry run covers PASS and a forced FAIL
68bf935 Holdout download: pause only on real HTTP 429 lines in the collector log; parse away/home from the event sub_title
7a25ae7 Update STATUS: Amendment 4, holdout download running, final-run script and dry run on t15
e117058 Add scripts/final_test_run.py (one-run guard, pre-run checklist, lead test, laggard, A, B, combined book, OOS numbers) and its synthetic dry-run fixtures; report_book.build reusable for OOS
48cdf17 Book report: B per contract and Sharpe only, DSR note; numpy OLS + Newey-West tested against a hand example; holdout downloader (save only)
a132047 Runner: v2 Amendment 4 cutoff (kickoff <= 20:00 ET Oct 3) applied on the holdout run
d36aafc Update STATUS after the 60-min queue (B, A exploratory, book report, Amendment 4 draft)
65b31af Book report on training (A theta 0.80, B selected, combined): metrics, costs x2, French regression, deflated Sharpe; results/numbers.json and equity curve
ee29f9b Strategy B training run: 8 settings + 8 placebo rows in variants.csv; B walkthrough
ac2ffad Strategy B (v3 + Amendment 1): strategy_b.py, fake-game tests, training runner with orientation check
aaf2eac Strategy A training run: 6 variants rows; STATUS
a164987 Add run_strategy_a.py: Strategy A training runner and report (bootstrap CIs, costs x2, side by side, v3 extras)
a18e4dc Update STATUS after the power note
3825678 Power note: sentence on smaller leads per Divi's edit
e5d0e07 Sim (a) power results (seed 20261003, 500 studies): power table with Wilson CIs and draft note text
bff960e Update STATUS after A3 commit, both-market staleness and fetch_game fix
8bd117a fetch_game: away market from the Kalshi event's market list, not rebuilt from codes (10 Miami (OH) games match the bulk download); known-limitations doc
a3e4a55 Strategy A: staleness on both markets before the favorite is chosen (n_skipped_stale per theta); tests a/b/c; walkthrough updated
c510374 Fix STATUS timestamp
7667521 Update STATUS after the hyphen audit and review packet
63bb03e Add Strategy A Rule-7 walkthrough (docs/review); Kalshi training liquidity, volume only
f26bfe1 Update STATUS after the 4:55 review list
04d3bdd Strategy A: 2026 opener Sep 9; team markets from trade files (keeps M-OH), exclude games missing a market; meta fetch resolves tickers
cd5eea2 Laggard: tests use the 1 s per-market delay (holdout value); 3 s only as the counted missing-market fallback
ea9a691 Update STATUS after the 4:05 decisions list
e918921 Strategy A: scalar settlements as a load step from Kalshi metadata (games file untouched), fill cap 1 - market tick, preseason = before the 2025 opener (assert 49); README read-only venue data line
64f6151 Laggard: per-market polymarket.com seconds_delay (missing -> 3 s, counted), no mid carry across outages, cuts or window end, best-level capacity; tests
d2614ae Runner: receipt minus venue-timestamp diagnostic (reported only); fetch per-market polymarket.com seconds_delay (sealed)
575077a Add sim_wilson.py (Wilson CIs and preset design rule from per-rep rows); STATUS flags
e1d6487 Update STATUS after the 3:35 PM list
7e2f760 Add trade-the-laggard evaluator on recorded books (Amendment 2 setting, 3 s polymarket.com taker delay, costs.fee); synthetic tests
8b2071d Sim results part (b): placebo Design 1 vs 2 with reverse and shared-shift nulls, Wilson CIs; preset rule gives Design 1
d34b762 Add requirements-exec.txt (Webull SDK 3.0.2 pinned) for a separate .venv-exec; ignore .venv-exec
a1b24c9 Strategy A: fill capped at 0.99 with per-theta count, NFL preseason flag and side-by-side summary; settle Kalshi scalar results at the recorded value
a0ea17d Book-wipe fallback [T - 2, T + 20 min], T = min(ESPN kickoff, polymarket.com gameStartTime); 15-min copy test
7528eab fees.md: polymarket.com 5-decimal rounding; add Polymarket US row
ba36a6a Fees: polymarket.com 5-decimal rounding (no cent ceiling); add Polymarket US schedule with half-even cents and 2026-10-01 14:00 UTC gate
fa5b19f Placebo design sim: reverse lead and shared-shift nulls, per-rep MW p; sim box driver for (b) then (a)
d5498d1 Update STATUS after fee, wipe-exclusion and Webull work
41f12a6 Add Webull sandbox paper-order client with dry run, rate limit and mocked tests
2c23dec Add book-wipe exclusion to the book-mid runner (Amendment 3 draft)
735eae2 Fees: exact Decimal arithmetic, ROUND_CEILING to the cent
ae90e8a strategy_a: Kalshi direct fee in exact Decimal; fee tests re-derived with Decimal
b15330c Placebo design sim results (seed 20261003, M 3000 ring per venue, 500 reps per cell, nproc 8, wall 453 s on sim box)
e3ec36b Power sim: procs and out_dir args, lag-jitter case, reverse rate, per-cell counts for CIs
c4eada4 Add quote-based power re-run script (2 processes; run niced, not during games on battery)
96c72b9 STATUS and GAPS: CPU starvation incident from simulation, battery warning
c783023 Add placebo design simulation (Design 1 n-1 pairs vs Design 2 K=5 pairs, ring with exact reuse)
7633adc Test strategy_a fees equal t9-costs costs.fee on a P x C grid (vendored values)
12309ea STATUS: MW check, Holm, runner per Alden, log-only window counts
03ec0b9 Runner: window kickoff - 90 min, REST fallback counts as Kalshi outage, heartbeat feed start, Holm via run_all
9275c0a Mann-Whitney via scipy (custom kept as cross-check), alpha and Holm across venues, fixed-verdict tests
ce56f1a STATUS: v3 Amendment 1 on main, Strategy A code, Amendment 2 runner
43ad682 Add Amendment 2 book-mid runner (synthetic-tested) and frozen holdout venue maps
49100b9 Add Strategy A (v3 + Amendment 1 fill at first trade >= t + 1 s, plus 1c) with fake-game tests
3a95a3c STATUS: GitHub push, mid rule fix, T8 kickoff scan, v3 amendment draft
2f79319 Mid rule per Amendment 2 in game_lag_mid (no fill across an empty side) with tests; T8 kickoff check; v2 result record
6c0b004 STATUS: Amendment 2 pre-registered on main, T8 coverage check, ALBY at IOWA rule
221363a Strategy A rules: include ALBY at IOWA via hand-checked ESPN event 401752799; downloader override
8bfc29c Add Strategy A data rules (ties, ALBY at IOWA, ESPN kickoffs) before any Strategy A code; update STATUS
e0ef83a Supervisor: caffeinate -dims for future starts
82b143f Add Kalshi-only training download for Strategy A (seal on kickoff before any request)
51473cf STATUS: ops checks, dedup fix, watchdog, holdout candidate list
ee13616 Add holdout candidate list builder (schedule metadata only, ESPN kickoffs, hand-checked overrides)
2ff9863 Watchdog: alert when heartbeat ages are missing; LOG overridable
2695fe0 Add read-only Vultr watchdog (unit state and feed heartbeat age, macOS alert)
9c9b7b6 Polymarket US: NaN-aware snapshot dedup so a missing side does not write a row every poll
6213f5d Record polymarket.com fee rule; add per-market rate override for the comparison line
79a0750 Record fee sources and live polymarket.com fee check (not a flat 0.05)
19a1001 Replace placeholder fee with Andrew's schedules, order size 10, Kalshi route parameter
```

## Files changed

```
M	.gitignore
M	GAPS.md
M	README.md
M	STATUS.md
M	backtest.py
M	collector/run.py
M	collector/supervise.sh
A	collector/watch_vultr.sh
M	costs.py
A	data/live/holdout_maps/polymarket_com_map.json
A	data/live/holdout_maps/polymarket_us_map.json
A	docs/known_limitations.md
A	docs/research/fees.md
A	docs/results/sim/README.md
A	docs/results/sim/a/power_sim_quotes.csv
A	docs/results/sim/a/power_sim_quotes_studies.csv
A	docs/results/sim/a/run.log
A	docs/results/sim/b/placebo_design_reps.csv
A	docs/results/sim/b/placebo_design_table.csv
A	docs/results/sim/b/placebo_design_wilson.csv
A	docs/results/sim/b/ring_0.csv
A	docs/results/sim/b/ring_1.csv
A	docs/results/sim/b/run.log
A	docs/results/sim/driver.log
A	docs/results/t8_kickoff_check.md
A	docs/results/v2_who_leads.md
A	docs/review/strategy_a_walkthrough.md
A	docs/review/strategy_b_walkthrough.md
A	docs/strategy_a_rules.md
M	execution/webull.py
A	experiments/sims/placebo_design/mw_size_check.txt
A	experiments/sims/placebo_design/placebo_design_table.csv
A	experiments/sims/placebo_design/ring_0.csv
A	experiments/sims/placebo_design/ring_1.csv
A	experiments/sims/placebo_design/run.log
A	experiments/sims/placebo_design/table_with_ci.txt
M	experiments/variants.csv
A	holdout_mid.py
M	ingest/download_all.py
A	ingest/french_factors.py
A	ingest/holdout_candidates.py
A	ingest/holdout_download.py
A	ingest/holdout_maps.py
A	ingest/kalshi_market_meta.py
A	ingest/kalshi_only_train.py
A	ingest/seconds_delay.py
A	laggard.py
M	report.py
A	report_book.py
A	requirements-exec.txt
M	requirements.txt
A	results/equity_training.png
A	results/numbers.json
M	run.py
A	run_strategy_a.py
A	run_strategy_b.py
A	scripts/final_test_fixtures.py
A	scripts/final_test_run.py
A	scripts/holdout_home_away_check.py
A	scripts/stop_and_sync.sh
M	strategy.py
A	strategy_a.py
A	strategy_b.py
A	tests/data_moh_events.json
A	tests/placebo_design_sim.py
A	tests/power_sim_quotes.py
A	tests/sim_box_run.sh
A	tests/sim_wilson.py
A	tests/test_book_wipe.py
A	tests/test_costs.py
A	tests/test_fetch_game_away.py
A	tests/test_holdout_mid.py
A	tests/test_laggard.py
A	tests/test_mid_rule.py
A	tests/test_mw_holm.py
A	tests/test_ols_nw.py
A	tests/test_pmus_dedup.py
A	tests/test_strategy_a.py
A	tests/test_strategy_a_fees.py
A	tests/test_strategy_b.py
A	tests/test_webull.py
M	xcorr_lead.py
```
