# posthoc_unsup

Post-hoc, exploratory; clusters fit on past weeks only; training only; holdout not run.

Committed: SPEC.md, RESULTS.md, trials_log.csv, daily_pnl.csv (trial_id, et_date, pnl), correction.json,
atlas_in_sample.csv, rank_performance.csv, rank_performance_pooled.csv.

Not in git (gitignored, data/unsup_cache/): snapshots.parquet (per-snapshot Kalshi prices), trades.parquet
(per-trade fills), build_stats.json. Regenerate (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts nice -n 19 python scripts/posthoc_unsup.py build
PYTHONPATH=.:scripts nice -n 19 python scripts/posthoc_unsup.py run
PYTHONPATH=.:scripts nice -n 19 python scripts/posthoc_unsup.py ranks
```

Inputs read (read-only): staleline/data/raw (Kalshi training trades, settlements), staleline/data/ticks
(polymarket.com training trades), staleline/out/strategy_b/b_games_espn.csv, ../wt-idea6/data/espn_raw (ESPN cache,
orientation code posthoc-idea6 0f57732), ../wt-idea13 training_games.csv (nflverse no-vig), ../wt-costside
(cumulative trials, costside_common.py 652c5e9).
