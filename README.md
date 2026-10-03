# StaleLine

The same football game trades on CME and Kalshi at once, and one of them is slow. StaleLine measures that delay, trades it after real costs, and shows the reaction speed at which the edge disappears. Paper trading only.

See `HYPOTHESIS.md` for the pre-registered hypothesis.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python make_sample.py --plot   # fake game -> data/ticks/sample.parquet, out/sample.png
```

## Shared data format

Every venue lands in `data/ticks/<game_id>.parquet` with these columns:

| column | meaning |
|---|---|
| `ts` | UTC nanoseconds (int64) |
| `venue` | `cme` / `kalshi` / `polymarket` |
| `market_id` | venue's own symbol or ticker |
| `kind` | `trade` / `bid` / `ask` |
| `price` | 0 to 1, always P(home team wins). Away-team contracts are flipped with `1 - price` at ingest. |
| `size` | contracts |
| `side` | `buy` / `sell` / `unknown` |

The fake game (`sample`) has 15 planted CME jumps (`data/ticks/sample_truth.csv`) and Kalshi lags CME by exactly 2 seconds. `leadlag.py` must recover both.

## Layout

```
ingest/      databento_cme.py, kalshi.py, polymarket.py, massive.py, pbp.py
store/       timescale.py, snowflake.py
execution/   webull.py
app/         demo screen (draws, never calculates)
collector/   Vultr live recorder service
align.py  leadlag.py  strategy.py  costs.py  backtest.py  report.py
run.py       python run.py --game <id>
```

## Rules

- Only Divi merges to `main`. Work on your own branch.
- No API keys and no raw vendor data in the repo.
- Never look at test games (Aug to Oct 2026) until the final run. Record every setting tried.
- Venue data is used read-only. No code places, amends or cancels an order on any venue, except paper orders to the Webull sandbox (execution/webull.py refuses any other host). Kalshi credentials are used only to open the read-only market-data websocket. polymarket.com data is read only: US residents cannot trade it.
