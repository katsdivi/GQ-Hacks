# posthoc_idea7

Post-hoc, exploratory; selected on training only. See SPEC.md and TRAINING.md.

## Per-trade files (not in git)

training_trades.csv (per-game rows with Kalshi and polymarket.com prices and fill timestamps) is kept on disk and
gitignored (no vendor data in git). Regenerate (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea7.py
```
