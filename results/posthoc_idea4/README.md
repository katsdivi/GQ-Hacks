# Post-hoc Idea 4: decision log

- 2026-10-04 03:59 ET: Holdout not run. Training showed no edge at any theta (all ROC point estimates negative, win rate below break-even at every theta); decision made on training results only, before any Idea 4 holdout data was touched. The 4 variants still count.

## Per-trade files (not in git)

2026-10-04: per-trade files with Kalshi prices or timestamps are kept on disk but untracked (no vendor data in git): training_trades.csv . Regenerate them (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea4.py
```
