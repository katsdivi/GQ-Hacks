# posthoc_idea6

## Close-out (2026-10-04 04:27 ET)

**Label: post-hoc, exploratory; designed and selected on training only.**

- **Winner leg: INVALID.** In 15 of the 20 games with a winner trade, ESPN's end-marker wallclock E is wrong (too early): ESPN has real plays 15 to 162 min after it (10 NFL preseason games, Aug 8 to 16, 2025, with "END GAME" at about 23:59 UTC; 5 CFB games: byu_ecu, haw_afa, wku_del, jvst_shsu, ariz_hou). Fills happen while the game is still being played, with the winner taken from a score that is already final: lookahead, not edge. The other 5 traded games (gb_ind, txst_utsa, la_phi, psu_iowa, pit_det) are not shown bad and not shown clean. The training winner-leg table in TRAINING.md (ROC, Sharpe, P&L) must not be quoted as a result.
- **No D selected.** No D reaches 50 winner trades (20, 14, 14).
- **Holdout not run.** Decided on training results only, before any Idea 6 holdout data (ESPN holdout summaries, holdout trades) was touched.
- **Proposed end-time fix rejected** (E = latest of marker and all play wallclocks, within kickoff + 2 h to + 6 h): it uses hindsight about which play was last. Not implemented, not run.
- **Descriptive results kept:** median time from E to the winner's first Kalshi trade at >= 0.99 is 11 s (p90 253 s); ESPN winner at E vs Kalshi settlement disagreements: 0. Item c (share of games with a winner trade <= 0.97 after E + D) is not reported.
- Variants: 3 (D = 60, 180, 600 s), counted in experiments/variants.csv.

## Per-trade files (not in git)

2026-10-04: per-trade files with Kalshi prices or timestamps are kept on disk but untracked (no vendor data in git): training_trades.csv training_games.csv . Regenerate them (cwd = repo root, pinned .venv-run):

```
PYTHONPATH=.:scripts python scripts/posthoc_idea6_ids.py   # ESPN ids + summary cache (data/espn_raw/)
PYTHONPATH=.:scripts python scripts/posthoc_idea6.py
```
