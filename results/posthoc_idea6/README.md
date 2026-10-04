# posthoc_idea6

## Per-trade files (not in git)

2026-10-04: per-trade files with Kalshi prices or timestamps are kept on disk but untracked (no vendor data in git): training_trades.csv training_games.csv . Regenerate them (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea6_ids.py   # ESPN ids + summary cache (data/espn_raw/)
PYTHONPATH=.:scripts python scripts/posthoc_idea6.py
```
