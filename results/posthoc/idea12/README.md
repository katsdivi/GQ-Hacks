# posthoc_idea12

Post-hoc, exploratory; selected on training only. Spec: SPEC.md (ca72fb9). Script and tests: de62d46.

## Per-trade files (not in git)

`training_trades.csv` (per-game rows with Kalshi fill prices and timestamps) is kept on disk but gitignored (no vendor data in git). Regenerate (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea12.py
```
