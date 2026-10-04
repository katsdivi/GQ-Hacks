# posthoc_latency

## Per-trade files (not in git)

2026-10-04: per-trade files with Kalshi prices or timestamps are kept on disk but untracked (no vendor data in git): idea1_trades.csv idea2_trades.csv idea3_trades.csv . Regenerate them (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea1.py   # idea1_trades.csv
PYTHONPATH=.:scripts python scripts/posthoc_idea2.py   # idea2_trades.csv
PYTHONPATH=.:scripts python scripts/posthoc_idea3.py   # idea3_trades.csv (Idea 3 outputs are INVALID, lookahead)
```
