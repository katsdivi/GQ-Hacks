# Build plan (Divi's tasks)

One task at a time. Each has a spec and a "done when" check that must be run and shown before the task counts as done. Times are targets, Eastern.

API notes below are starting points from memory of the public docs. Verify field names against the live API on the first call and fix this file if they differ.

---

## Friday night: path to Made It (target 2:30 AM)

### T1. Repo, fake game, hypothesis (7:30 to 8:00 PM) DONE

Done when: Olmer loads `data/ticks/sample.parquet`; `HYPOTHESIS.md` commit is timestamped before any backtest.

### T2. CME data check / Decision A (7:45 to 8:30 PM)

Script exists: `ingest/databento_cme.py` (untested against the real API).

1. `list --date 2026-09-27` (last Sunday). Prints cost first. Filters `FG*` / `CG*`.
2. If zero hits: inspect `asset`, `security_type`, `instrument_class` columns by hand; ask the Databento rep what root the sports contracts use. Do not burn money on `ALL_SYMBOLS` across many days.
   Checked 2026-10-02: single-game contracts are options `FG<team><mon><y><dd> C0001` (parent `FG<team>.OPT`, group `NFLG`; college `CG...`, `CFBG`), priced 0 to 1. Databento has them from 2026-01-11 only. See STATUS.md.
3. Pick one NFL game that also has a Kalshi market. `pull` trades + bbo-1s from 2 h before kickoff to 30 min after the end.
4. Check on the first real pull: price scale (0 to 1 vs 0 to 100, set `--price-scale`), which team the contract pays on (`--away`), and that timestamps are UTC.

Done when: one sentence to the team, "PASS / THIN / NO DATA", with trade count, trades per minute, and number of price changes. Fewer than ~50 trades in a game = THIN. If NO DATA or THIN: fallback is Kalshi vs Polymarket plus the fair-value model; same steps, different venues.

### T3. Same game on Kalshi (8:30 to 9:30 PM)

Write `ingest/kalshi.py`.

- Base: `https://api.elections.kalshi.com/trade-api/v2`. Market data endpoints are public (no auth).
- Find the series (likely `KXNFLGAME`, college maybe `KXNCAAFGAME`): `GET /series`, then `GET /markets?series_ticker=...&status=settled` (and `open`). Each game has one market per team; ticker ends with a team code. Use the home team's market, or the away one flipped.
- Trades: `GET /markets/trades?ticker=...&min_ts=<unix s>&max_ts=<unix s>&limit=1000&cursor=...`, page until `cursor` is empty. Fields to expect: `created_time`, `yes_price` (cents) or `yes_price_dollars`, `count`, `taker_side`.
  Checked 2026-10-02: fields are `created_time`, `yes_price_dollars`, `count_fp`, `taker_side`, `trade_id`. Anything before `GET /historical/cutoff` is only on `/historical/markets` and `/historical/trades`.
- Convert: `ts` to UTC ns, price to 0 to 1, flip away, `kind=trade`, `side` from `taker_side` (yes = buy of the YES contract; swap if flipped).
- Merge with the CME file into `data/ticks/<game_id>.parquet`. Add the row to `data/games.csv`.
- Function signature: `fetch_trades(ticker, start_utc, end_utc) -> DataFrame` in the shared format; `find_game_markets(series, date) -> DataFrame`.

Done when: one chart (`out/<game_id>_overlay.png`) with CME and Kalshi on the same axes tracking each other. A mirror image means a flipped team. Post the chart to the team.

### T4. Live recorder on Vultr into Tiger Data (9:30 to 11:30 PM)

Write `store/timescale.py` and `collector/run.py`.

- Table (run once):

```sql
CREATE TABLE ticks (
  ts TIMESTAMPTZ NOT NULL, ts_ns BIGINT NOT NULL, venue TEXT NOT NULL,
  market_id TEXT NOT NULL, kind TEXT NOT NULL, price DOUBLE PRECISION,
  size DOUBLE PRECISION, side TEXT
);
SELECT create_hypertable('ticks', by_range('ts'));
CREATE INDEX ON ticks (venue, market_id, ts DESC);
```

- `store/timescale.py`: `connect()` from `TIGER_DATABASE_URL`; `write_rows(rows)` using `COPY` via psycopg 3 for speed; `latest_per_venue()` for the health page.
- `collector/run.py`: one asyncio process, two listeners, one writer.
  - CME: `databento.Live(key)`, `subscribe(dataset="GLBX.MDP3", schema="trades")` and `bbo-1s` for this weekend's FG/CG symbols (from `data/games.csv` or a symbols file).
  - Kalshi: websocket `wss://api.elections.kalshi.com/trade-api/ws/v2`, authenticated with headers `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-TIMESTAMP` (ms), `KALSHI-ACCESS-SIGNATURE` = base64 RSA-PSS SHA256 signature of `timestamp + "GET" + "/trade-api/ws/v2"` with the private key file. Subscribe to `orderbook_delta` and `trade` for the game tickers. Maintain the book locally and emit best bid/ask rows on change.
  - Each listener: exponential backoff on disconnect (1, 2, 4 ... capped at 30 s), logs every reconnect.
  - Writer: buffer in memory, flush to Tiger Data once per second.
  - Decision D: if the Kalshi websocket is not working by 10 PM, poll `GET /markets/{ticker}/orderbook` every 1 to 2 s instead.
- systemd unit at `collector/gqh-collector.service` (WorkingDirectory `/opt/gqh`, `EnvironmentFile=/opt/gqh/.env`, `ExecStart=/opt/gqh/.venv/bin/python -m collector.run`, `Restart=always`, `RestartSec=5`).
- Log any gap to `GAPS.md` (time, venue, cause).

Done when: 30 minutes of nonstop rows from both venues, then `sudo systemctl restart gqh-collector` and rows keep arriving. Show `SELECT venue, count(*), max(ts) FROM ticks GROUP BY venue;` before and after.

### T5. Lead/lag (11:30 PM to 12:30 AM; spec from Alden's `docs/math_spec.md`)

Write `align.py` and `leadlag.py`.

- `align.py`: `mid_or_last(ticks, venue) -> Series` (mid of bid/ask when both exist, else last trade; per spec); `asof_join(left, right, on="ts")` using `merge_asof(direction="backward")` only.
- `leadlag.py`:
  1. `detect_jumps(cme, jump_cents, window_s) -> DataFrame`: every CME move of at least `jump_cents` within `window_s`; skip ahead `window_s` after each so one play counts once.
  2. `response_times(jumps, kalshi, cover, max_wait_s) -> DataFrame`: time until Kalshi has moved `cover` of the same distance in the same direction. Never-covered jumps are KEPT with `covered=False` (dropping them biases the lag down).
  3. `xcorr_lag(a, b, grid_s, max_lag_s) -> float`: independent estimate from cross-correlation of returns on a fixed grid (previous-tick carried forward, or Hayashi-Yoshida, per Alden).
- PROVISIONAL defaults until the spec lands: `jump_cents=3`, `window_s=10`, `cover=0.8`, `max_wait_s=60`, `grid_s=0.25`, `max_lag_s=15`.
- Writes `out/leadlag/<game_id>.parquet`.
- Tests in `tests/test_leadlag.py` against the fake game.

Done when: fake game finds 15 jumps (match against `sample_truth.csv` by timestamp) and median `response_s` ~2.0, `xcorr_lag` ~2.0. Real game prints a lag number. Hand Alden 5 real jumps (raw rows around each) for his spreadsheet check.

### T6. First trades and profit after costs (12:30 to 1:30 AM)

Write `strategy.py`, `costs.py`, `backtest.py` (first version; full version is T9).

- Signal: CME jump detected at `t` AND `cme(t) - kalshi_asof(t) >= entry_gap` cents in the jump's direction. Long Kalshi if CME jumped up, short if down. 1 contract.
- Exit: gap < 1 cent or `timeout_s`, whichever first.
- Fill: decide at `t`, fill at `t + latency_s` at the ask (buy) or bid (sell), using the as-of book at the fill time. Trades-only history: trade price plus an assumed half-spread, and flag `fill_model="trade+halfspread"`.
- Costs: `costs.fee(price, qty, side, venue)`. PLACEHOLDER 2 cents/contract until Andrew's numbers.
- PROVISIONAL defaults: `entry_gap=2`, `timeout_s=60`, `latency_s=1.0`.
- Writes `out/signals/<game_id>.parquet`.

Done when: list of trades for the real game and one net profit number. Placebo on the fake game (swap leader and follower) shows ~zero or negative edge.

### T7. One command = MADE IT (1:30 to 2:30 AM)

`run.py --game <id>`: load ticks, align, lead/lag, strategy, print lag + net profit, save `out/<id>_run.png`. Deterministic (fixed seeds, sorted inputs).

Done when: a teammate clones, installs, runs the same command, and gets identical numbers and chart. Then `git tag v0-made-it` and push the tag.

### T8. Overnight download of every overlapping game (before sleep)

`ingest/download_all.py`: loop T2 + T3 over every game on both CME and Kalshi since 2025-12-06. Sum `get_cost` for the whole run and show Divi before starting. Log failures to `out/download_errors.csv`, keep going on errors, skip games already on disk.

Done when: `data/games.csv` lists every game, each has a ticks file, error log reviewed.

---

## Saturday

### T9. Strategy, backtest, costs, full version (8 to 11 AM)
From Alden's spec and Andrew's fees. Every game gets `out/signals/<game_id>.parquet`. Backtest refuses test games without `--final-test`. Every run appends to `experiments/variants.csv`.
Done when: every training game has a signals file; Alden hand-checked 3 trades.

### T10. Tune on train, test once (11 AM to 1 PM)
Grid from `docs/stats_plan.md` (draft: jump 3/4/6c, window 5/10/20s, entry gap 2/3/4c, timeout 30/60/120s = 81). Selection rule: best mean net edge per trade among settings with >= 30 trades. Then ONE run on test games with the chosen setting.
Done when: one training result, one test result, variant count recorded, test run logged once.

### T11. Latency curve, robustness, metrics (1 to 5 PM) in `report.py`
Test games at latency 0, 0.25, 0.5, 1, 2, 5, 10 s. Confidence intervals by resampling whole games (block bootstrap by game). Robustness from Alden's list: NFL vs college, close vs lopsided, placebo (Kalshi leads), without top 5 trades, costs doubled. Required metrics in-sample and out-of-sample: annualized return, volatility, Sharpe, max drawdown, turnover, equity curve, skew, worst month.
Done when: `out/latency_curve.csv` + robustness table exist and Alden initialed every number.

### T12. Webull module (3 to 7 PM)
`execution/webull.py`: `fee(price, qty, side)`, `place_paper_order(market_id, side, qty, limit_price)` (real paper order if Decision B allows, else log only), every call to `out/orders.csv`. Run backtest through Webull costs and Kalshi direct.
Done when: both numbers handed to Andrew.

### T5b. CME playoff lead/lag, descriptive only (after Made It)
Run `leadlag.py` on all CME playoff games with data: 13 NFL games (26 team contracts, Jan 10 wild card only partly covered) plus the CFP final (2 contracts) (Jan to Feb 2026, data already in `data/raw/fg_cg_train_*.parquet`) against Kalshi. Report who leads and how often, with lag numbers. No trading, no strategy. The original brief: "if CME turns out to be the slow one, report it as the finding."
Done when: one table (game, leader, median lag, n jumps) and one sentence for the team.

### T13. ES vs SPY method check on Databento (replaces the Massive check)
Use Databento ES futures (GLBX.MDP3) vs SPY (an equities dataset) as a known-answer check for `leadlag.py`: ES is expected to lead SPY by milliseconds. Show `get_cost` first and wait for Divi.
Done when: leadlag.py reports the known direction on a few days.

### T13b. Polymarket third venue (with T12 window)
Gamma API for markets, data API for trades, order book websocket added to the recorder.
Done when: third line on the overlay chart; lead/lag includes it.

### T14. Fair-value model (Sat night)
From `docs/fair_value.md`. Pregame CME price backs out expected margin; in-game uses score and clock from Olmer's play-by-play file.
Done when: fourth line appears for one game and passes Alden's checks.

## Sunday morning
Live/Replay with Olmer (demo reads Tiger Data). Snowflake backup if time. Repo cleanup: clean clone reproduces every number in the note with one command. Submit by 9:30 AM (Devpost closes 10:00, pushes until 11:00).
