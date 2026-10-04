# posthoc_meta

Post-hoc, exploratory; meta-model over strategies already seen to fail on training; walk-forward on training only.
See SPEC.md and RESULTS.md.

## Per-candidate file (not in git)

candidates.csv (per-trade Kalshi prices and timestamps) is gitignored. Regenerate (cwd = repo root, pinned
.venv-run; needs the base strategies' training trade files listed in SPEC.md on disk):

```
PYTHONPATH=.:scripts python scripts/posthoc_meta.py
```
