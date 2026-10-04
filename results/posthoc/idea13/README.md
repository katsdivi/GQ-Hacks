# posthoc_idea13

Post-hoc, exploratory; sportsbook closing line used as a signal only; selected on training only. Spec: SPEC.md.

## Per-trade files (not in git)

`training_trades.csv` and `training_games.csv` (per-trade and per-game Kalshi prices) are kept on disk but untracked (no vendor data in git). Regenerate (cwd = repo root, pinned .venv-run; nflverse file at data/nflverse_raw/games.csv from https://github.com/nflverse/nfldata/raw/master/data/games.csv):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea13.py
```
