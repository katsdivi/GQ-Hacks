# CLAUDE.md: StaleLine

You are pairing with Divi (Divyam Kataria), who owns all the code, data and infrastructure for StaleLine at Gator Quant Hacks (UF, Oct 2 to 4, 2026, Systematic track). Teammates: Alden (math spec, hand checks, stats plan, signs off every number), Andrew (fees, Webull, research, quant note), Olmer (demo app; draws, never calculates).

## The project in one paragraph

The same NFL or college football game trades on CME (event contracts since Dec 6, 2025; NFL symbols start `FG`, college `CG`; data from Databento `GLBX.MDP3`) and on Kalshi (retail prediction market; Webull routes to it). Hypothesis: CME reprices first after a big play and Kalshi lags by seconds. We measure the lag, paper-trade the Kalshi side after real costs, tune on games before Aug 1 2026, test once on Aug 1 to Oct 2026, and plot net edge vs assumed reaction delay (the latency curve, our headline chart). Pre-registered in `HYPOTHESIS.md`. Do not edit that file without Divi saying so.

## Where we are

Read `STATUS.md` first, every session. It says which task is current. Task specs and "done when" checks are in `docs/BUILD_PLAN.md`. Work one task at a time, in order, unless Divi says otherwise.

If behind, protect this order: recorder, Made It (`run.py`), lead/lag, backtest, test once, latency curve. Everything else comes after.

## Hard rules (judging caps our score at 4/10 if any break)

1. **No lookahead.** Every join between venues is `pd.merge_asof(..., direction="backward")` on `ts`. A decision at time `t` may only use rows with `ts <= t`. Fills happen at `t + latency`, never at `t`. If you are unsure whether a line peeks at the future, stop and say so.
2. **Test set is sealed.** Games with kickoff on or after 2026-08-01 are test games. Never load, plot, print or tune on them until Divi explicitly says "final test run". `backtest.py` and the tuning code must refuse test games unless passed `--final-test`.
3. **Record every variant tried.** Every parameter combination run on training data gets one row appended to `experiments/variants.csv` (timestamp, git sha, params, n_trades, mean edge). This file is committed. Never delete rows.
4. **Costs are always charged.** Fees, spread and latency in every backtest number. Until Andrew's fee file lands, fee is 2 cents per contract and the output must say `PLACEHOLDER FEE`.
5. **No secrets, no vendor data in git.** Keys live in `.env` (gitignored). Raw Databento, Kalshi and Massive data stays under `data/` and `out/` (gitignored). Only the fake game (`data/ticks/sample*`) and `data/games.csv` are committed. Never print a key value to the terminal.
6. **Paper trading only.** No code path places a real-money order.
7. **`strategy.py`, `costs.py`, `backtest.py`, `leadlag.py` are written only in Divi's pairing sessions, reviewed line by line by Divi before merge to `main`, and outputs hand-checked by Alden.** Teammates' code never touches them.

## Data contracts (do not change without Divi)

**Ticks:** `data/ticks/<game_id>.parquet`

| col | type | notes |
|---|---|---|
| `ts` | int64 | UTC nanoseconds. Use `.dt.as_unit("ns")` before `astype("int64")`; pandas 3 defaults to microseconds. |
| `venue` | str | `cme` / `kalshi` / `polymarket` (also `es` / `spy` for the Massive check) |
| `market_id` | str | venue symbol or ticker |
| `kind` | str | `trade` / `bid` / `ask` |
| `price` | float | 0 to 1, ALWAYS P(home team wins). Flip away-team contracts with `1 - p` at ingest, and swap bid/ask and buy/sell when you do. |
| `size` | float/int | contracts |
| `side` | str | `buy` / `sell` / `unknown` (aggressor for trades) |

**Games:** `data/games.csv`: `game_id, league, home, away, kickoff_utc, cme_symbol, kalshi_ticker, polymarket_token`

**Outputs Olmer and Alden read:**

- `out/leadlag/<game_id>.parquet`: `jump_ts, jump_cents, direction, response_s, covered`
- `out/signals/<game_id>.parquet`: `ts, action (enter_long/enter_short/exit), venue, price, qty, fee, pnl_cum`
- `out/latency_curve.csv`: `latency_s, n_trades, edge_cents_mean, edge_ci_low, edge_ci_high, pnl_total`

**Tiger Data (Timescale) table:** `ticks(ts TIMESTAMPTZ, ts_ns BIGINT, venue, market_id, kind, price DOUBLE PRECISION, size DOUBLE PRECISION, side)`, hypertable on `ts`. Keep `ts_ns` because Postgres stops at microseconds.

## Ground truth for testing

`python make_sample.py` writes the fake game (`game_id=sample`): 3.5 h at 1 tick/s, 15 planted CME jumps of 3 to 10 cents (answer key in `data/ticks/sample_truth.csv`), Kalshi = CME from exactly 2 s earlier plus noise, rounded to cents. Any lead/lag or strategy code must pass on this before it touches a real game: ~15 jumps found, ~2 s median lag, and the placebo (Kalshi as leader) finds no edge.

## Commands

```bash
pip install -r requirements.txt
python make_sample.py --plot                         # fake game + out/sample.png
python -m ingest.databento_cme list --date 2026-09-27
python -m ingest.databento_cme pull --symbol <sym> --start <utc> --end <utc> --game-id <id> [--away] [--price-scale N]
python run.py --game <id>                            # Made It target
pytest -q                                            # tests/ (add tests as you build)
```

## How to work with Divi

- He is a CS + Math student, fluent in Python and quant concepts. Skip basics.
- Deliver complete, runnable files, not patch fragments, when writing a new module.
- Before saying a task is done, run its "done when" check from `docs/BUILD_PLAN.md` and show the output. If you could not run it (missing key, no network), say so plainly.
- Ask before spending money: every Databento request prints `metadata.get_cost` first.
- If Alden's `docs/math_spec.md` does not exist yet, use the defaults in `docs/BUILD_PLAN.md`, label them `PROVISIONAL (pre-spec)` in code comments and output, and list what needs his confirmation.
- When a real-data surprise shows up (flipped team, wrong price scale, timezone off, CME lagging instead of leading), stop and report it with numbers. Do not paper over it.
- No em dashes in any text you write (docs, comments, commit messages). Plain English.
- Commit small and often on a feature branch. Divi merges to `main`. Commit messages: imperative, one line, what changed.

## End of every task

1. Update `STATUS.md`: mark the task done, what was verified (with the actual numbers), what's next, any blocker.
2. Print the STATUS block from `STATUS.md` so Divi can paste it to his planning chat.
3. Commit.
