# posthoc_regress

Post-hoc, exploratory; supervised residual model over all data sources; walk-forward on training only; holdout not run.

- SPEC.md: rules, committed before any real data (4b318d6).
- RESULTS.md: out-of-sample fit, top trials, feature importance, cumulative correction.
- trials_log.csv (48 trials), daily_pnl.csv, oos_fit.csv, feature_importance.csv, correction.json, run.log.

Per-snapshot and per-trade files are not in git (data/regress_cache/, gitignored). Regenerate (cwd = repo root, pinned
.venv-run; needs ../wt-idea6/data/espn_raw/ and ../wt-idea13/results/posthoc_idea13/training_games.csv on disk, and the
other search branches' worktrees for the cumulative correction):

```
PYTHONPATH=.:scripts nice -n 19 .venv-run/bin/python scripts/posthoc_regress.py
```
