# posthoc_idea9

## Per-trade files (not in git)

2026-10-04: per-trade files with Kalshi prices or timestamps are kept on disk but untracked (no vendor data in git): training_trades.csv . Regenerate them (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea9.py   # needs ../wt-idea6/data/espn_raw/ or its own data/espn_raw/
```
