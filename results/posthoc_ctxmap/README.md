# posthoc_ctxmap

Regenerate everything here (cwd = repo root of this branch, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_ctxmap.py --pool ../wt-meta/results/posthoc_meta/candidates.csv
```

The input pool is a per-candidate file with Kalshi prices; it is not in git. Rebuild it on branch posthoc-meta with
`PYTHONPATH=.:scripts python scripts/posthoc_meta.py`. All files committed here are summaries (per context,
idea-leg or week); no per-trade rows.
