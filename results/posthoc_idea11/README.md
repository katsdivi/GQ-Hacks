# posthoc_idea11

Post-hoc, exploratory. Spec: SPEC.md (277769a). Results: RESULTS.md (a), RESULTS_b.md (b, original execution
model), CORRECTED_EXECUTION.md (b, post-run correction of the execution model).

## Per-trade files (not in git)

2026-10-04 04:41 ET: per-trade and per-attempt files with Kalshi and polymarket.com prices or timestamps are kept on disk but
untracked (no vendor data in git): opportunities.csv, executions.csv, executions_settled.csv,
corrected_attempts.csv. Regenerate them (cwd = repo root, pinned .venv-run, in this order):

```
PYTHONPATH=.:scripts nice -n 19 python scripts/posthoc_idea11.py                  # opportunities.csv, executions.csv (the one run)
PYTHONPATH=.:scripts nice -n 19 python scripts/posthoc_idea11.py --settle-only    # executions_settled.csv
PYTHONPATH=.:scripts nice -n 19 python scripts/posthoc_idea11_corrected.py        # corrected_attempts.csv
```
