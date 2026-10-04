# StaleLine

Does one football prediction market move before another? StaleLine records Kalshi, polymarket.com and Polymarket US books for the same games, tests a pre-registered lead-lag hypothesis once on sealed holdout games, and paper-trades three Kalshi strategies (favorite-longshot taker A, maker A-maker, cross-venue disagreement B) after real costs, latency and fees. Paper trading only.

Pre-registration: `HYPOTHESIS_v2.md` (lead test and trade-the-laggard, Amendments 1 to 5) and `HYPOTHESIS_v3.md` (Strategies A, B and A-maker, Amendments 1 to 5). Every amendment is a dated commit on main made before the holdout run; see `docs/holdout_run_disclosure.md`.

## Results

| | sample | trades | net edge or return | 95% CI | Sharpe (ann.) |
|---|---|---|---|---|---|
| Lead test, Kalshi vs polymarket.com | holdout | {{LEAD_OOS_POLYMARKET_COM_N_QUALIFYING}} games | {{LEAD_OOS_POLYMARKET_COM_DECISION}} | | |
| Lead test, Kalshi vs Polymarket US | holdout | {{LEAD_OOS_POLYMARKET_US_N_QUALIFYING}} games | {{LEAD_OOS_POLYMARKET_US_DECISION}} | | |
| Trade-the-laggard | holdout | {{LAGGARD_OOS_N_TRADES}} | see the latency curve | | |
| Strategy A, theta 0.80 | training | {{A_TRAIN_N_TRADES}} | ROC {{A_TRAIN_ROC_WEBULL}} (TODO: not yet a numbers.json key) | | {{A_TRAIN_SHARPE}} |
| Strategy A, theta 0.80 | holdout | {{A_OOS_N_TRADES}} | ROC {{A_OOS_ROC_WEBULL}} | {{A_OOS_ROC_WEBULL_CI}} | {{A_OOS_SHARPE}} |
| Strategy A-maker, theta 0.80 | holdout | {{A_MAKER_OOS_FILLS}} fills | ROC {{A_MAKER_OOS_ROC_WEBULL}} | {{A_MAKER_OOS_ROC_WEBULL_CI}} | |
| Strategy B (5 c, 10 s, 300 s) | training | {{B_TRAIN_N_TRADES}} | {{B_TRAIN_EDGE_WEBULL_CENTS_PER_CONTRACT}} c/contract | | {{B_TRAIN_SHARPE}} |
| Strategy B | holdout | {{B_OOS_N_TRADES}} | {{B_OOS_EDGE_WEBULL_CENTS}} c/contract | {{B_OOS_EDGE_WEBULL_CI}} | |

Every value comes from `results/numbers.json` through `docs/note/numbers_sheet.md` (`python scripts/numbers_sheet.py`); nothing is typed by hand. Webull line ($0.02 per contract per fill) is primary; Kalshi direct is the comparison.

Where things are:
- `results/numbers.json`: every reported number, key -> value + source script (training keys; `OOS.` keys after the holdout run).
- `results/holdout/`: the one holdout run (RUN_LOG.md with git hash and ET start/end, checklist, per-test and per-strategy tables).
- `results/figures/`: figures with the CSV behind each.
- `results/equity_training.png`, `docs/review/`: walkthroughs of every rule-7 file; `docs/holdout_run_disclosure.md`.

## Reproduce

Training numbers, one command (needs the raw training data under `data/`, see below):

```bash
scripts/reproduce_training.sh      # builds .venv-run from requirements.txt if missing, runs A, B and the book
                                   # report, diffs results/numbers.json against the committed file (115/115 keys)
```

The environment is pinned (`requirements.txt`: pandas 2.3.2, numpy 1.26.4; pandas 3 changes the default datetime unit). The raw vendor data is not in the repository; rebuild it with the ingest scripts (`python -m ingest.kalshi_only_train`, `python -m ingest.download_all`, `python -m ingest.kalshi_market_meta`, `python -m ingest.french_factors`, then `python scripts/build_b_games_espn.py`). The holdout run is `scripts/final_test_run.py --i-am-the-one-run` (refuses to run twice); `--dry-run` runs the same pipeline on synthetic fixtures.

## Data and venues

- Venue data is used read-only. No code places, amends or cancels an order on any venue, except paper orders to the Webull sandbox (execution/webull.py refuses any other host). Kalshi credentials are used only to open the read-only market-data websocket. polymarket.com data is read only: US residents cannot trade it.
- No raw vendor data and no API keys are in the repository (`data/`, `out/`, `.env` are gitignored).

## Shared data format

Every venue lands in `data/ticks/<game_id>.parquet` (and the live recorder in `data/live/<venue>/`):

| column | meaning |
|---|---|
| `ts` | UTC nanoseconds (int64) |
| `venue` | `kalshi` / `polymarket` / `polymarket_us` (`cme` for the retired v1) |
| `market_id` | venue's own symbol or ticker |
| `kind` | `trade` / `bid` / `ask` |
| `price` | 0 to 1, always P(home team wins); away-team contracts flipped with `1 - price` at ingest |
| `size` | contracts |
| `side` | `buy` / `sell` / `unknown` |

## Rules

- Only Divi merges to `main`. Work on your own branch.
- No API keys and no raw vendor data in the repo.
- Never look at test games (Aug to Oct 2026) until the final run. Record every setting tried (`experiments/variants.csv`).
