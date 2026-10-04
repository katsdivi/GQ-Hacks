# posthoc_costside

Per-trade files are not in git (data/costside_cache/, gitignored). Regenerate (cwd = repo root, .venv-run):

```
PYTHONPATH=.:scripts python scripts/costside_round1.py
PYTHONPATH=.:scripts python scripts/costside_round2.py   # and later rounds
PYTHONPATH=.:scripts python scripts/costside_log.py      # trials_log.csv, daily_pnl.csv, correction.json
```
