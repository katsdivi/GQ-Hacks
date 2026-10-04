# Full-history training data (Kalshi and polymarket.com)

Data only, no strategy. TRAINING games only (kickoff before 2026-08-01, asserted in code). Free public
endpoints only, no account, no key. Raw files live under `data/raw/fullhist/` (gitignored, vendor data);
this README and `scripts/fetch_fullhist.py` are the only committed files.

## Files (paths only; all under data/raw/fullhist/, gitignored)

| Path | Contents | Contract |
|---|---|---|
| `kalshi/<game_id>.parquet` | Kalshi trades, both team markets, market open to close | tick contract (ts ns UTC, venue, market_id, kind, price = P(home), size, side) |
| `polymarket/<game_id>.parquet` | polymarket.com taker trades, full market history | tick contract |
| `polymarket_fills/<game_id>.parquet` | sidecar: every fill record (taker and maker) with `proxyWallet`, `transactionHash`, raw side, outcomeIndex, raw price, size, `in_taker_feed`, `home_index` | sidecar, raw outcome prices (not flipped) |
| `kalshi_candles/<game_id>.parquet` | sidecar: Kalshi 1-min candles over [kickoff - 24 h, min(close, kickoff + 8 h)] and 60-min candles over [open, close], with `yes_bid` and `yes_ask` OHLC, trade price OHLC, volume, open interest | sidecar, the market's own YES price (not flipped); `team`, `is_home` columns |
| `kalshi_manifest.csv`, `polymarket_manifest.csv`, `kalshi_candles_manifest.csv` | one row per game: counts, windows, validation, errors | |
| `coverage.json` | summary written by `report` | |

## Sources and windows

- **Kalshi trades:** `GET /trade-api/v2/historical/trades` and `/markets/trades` (public), via the repo's
  `ingest.kalshi.fetch_trades` with `ingest.kalshi_only_train._kget` (throttled, backoff-aware) patched in at
  import. Only the windows the existing files lack are fetched: [market open_time, kickoff - 2 h) and
  (kickoff + 5 h, close_time]. The full file is pre + the unchanged existing `data/raw/kalshi_only/<game_id>.parquet`
  + post. open_time/close_time come from `data/raw/kalshi_kx{nfl,ncaaf}game_historical.parquet`, else
  `/historical/markets/{ticker}` or `/markets/{ticker}`. Timestamp precision: microseconds (Kalshi created_time).
- **polymarket.com trades:** `GET https://data-api.polymarket.com/trades?market=<condition>&takerOnly=true`,
  paged BACKWARDS with the `end` parameter, because `offset` is capped at 10,000 (an offset above that returns
  HTTP 400). Orientation exactly as `ingest/download_all.py` line 327 (`home_index = 0 if pm_flipped else 1`),
  using `data/raw/t8_game_plan.csv` (977 games). Timestamp precision: 1 second.
- **polymarket.com fills sidecar:** the same endpoint with `takerOnly=false` (taker and maker records). Every row
  carries `proxyWallet` (the trader's proxy wallet) and `transactionHash`. This unlocks wallet-level work (for
  example the skilled-wallet idea, which earlier had no wallet ids).
- **Kalshi candlesticks sidecar:** `GET /trade-api/v2/historical/markets/{ticker}/candlesticks` with
  `period_interval` 1 or 60 (public, no auth; max 5,000 candles per request). The live-market path
  `/series/{s}/markets/{m}/candlesticks` returns 404 for these settled markets.
- Rate limits: polymarket.com 2 req/s; Kalshi 2 req/s for trades and 1 req/s for candles (separate processes).

## Regenerate (cwd = staleline repo root, pinned .venv-run)

```
python <worktree>/scripts/fetch_fullhist.py kalshi --validate 50
python <worktree>/scripts/fetch_fullhist.py polymarket
python <worktree>/scripts/fetch_fullhist.py candles
python <worktree>/scripts/fetch_fullhist.py report
```

All modes are resumable (existing per-game files are skipped).

## Coverage and validation

Run 2026-10-04, 06:13 to 07:46 ET. Complete (not partial).

| Venue / file set | Games | Errors | Pre-game history before kickoff (first trade), median / p10 / p90 | Trades per game, median |
|---|---|---|---|---|
| Kalshi trades | 1,267 of 1,267 | 0 | 234 h / 148 h / 628 h | 9,599 (of which 1,636 pre-window, 7,935 in the old window, 0 after +5 h) |
| polymarket.com taker trades | 977 of 977 | 0 | 118 h / 79 h / 179 h | 778 (220 pre-window); last trade a median 5.3 h after kickoff |
| polymarket.com fills sidecar (wallets) | 976 of 977 have fill rows (1 game has no trades) | 0 | same markets | 1,729 fill records; 3,445,043 records in total, 104,227 distinct proxy wallets |
| Kalshi candles sidecar | 1,267 of 1,267, both team markets in every game | 0 | 1-min from kickoff - 24 h; 60-min from market open | 2,477 one-minute and 556 sixty-minute candles; yes_bid/yes_ask present in all games |

Validation (Kalshi): for 50 random games (seed 20261004) the [kickoff - 2 h, kickoff + 5 h] window was refetched
and compared with the existing `data/raw/kalshi_only` files on (ts, market_id, price, size): 618,868 home and
704,580 away rows on both sides, 0 rows only in the new fetch, 0 rows only in the old file; all 50 games match
exactly. polymarket.com paging: at most 3 pages per game, no stuck pages, so no truncation by the 10,000 offset
cap (the `end` cursor removes that cap).

Fixes during the run, disclosed:
- 13 games with team code OH (Miami OH, ticker suffix M-OH) first fetched only the home market's pre/post
  windows and candles, because the away ticker was built from the team code. The away ticker is now taken from
  the existing file's market_id; those 13 games were refetched. Old manifest rows are kept; `report` uses the
  last row per game.
- The first polymarket.com pass (about 100 games, taker trades only) was stopped and restarted to add the wallet
  sidecar; its files were deleted and rewritten.

## Free sources checked (for order-book depth and richer trade data, Aug 2025 to Jan 2026)

| Source | Provides | Timestamp | Training coverage | Terms / cost | Fetch | Verdict |
|---|---|---|---|---|---|---|
| Kalshi `/historical/markets/{t}/candlesticks` | 1-min and 60-min OHLC of trade price, yes_bid, yes_ask, volume, open interest | minute (end of period) | full: every training market | public, no auth, free | `fetch_fullhist.py candles` | FETCHED. The only free history of Kalshi quotes (top of book at minute resolution); no depth |
| Kalshi `/markets/{t}/orderbook` | live book only | n/a | none (settled markets return empty) | free | n/a | no history |
| Kalshi historical depth (L2) | none from Kalshi itself | | | | | Kalshi publishes no historical L2 |
| Fable5 Kalshi L2 archive (HuggingFace naratron33/fable5-kalshi-l2) | recorded L2 snapshots and trades | unknown | unknown (gated, recorded from whenever its recorder started) | requires agreeing to share contact info | not fetched | not signed up (gated); coverage of our dates unverified |
| Oddpool | Kalshi and Polymarket tick-level book deltas and trades | ms | from Mar 19/20, 2026 only | free tier for Polymarket, paid institutional | API | no training coverage |
| CoinAPI / FinFeed / EntityML / Tardis | full book update streams | ms | varies | paid | | excluded (paid) |
| polymarket.com data-api `/trades` | every fill, taker and maker records, with `proxyWallet`, `transactionHash`, outcome, side, price, size | 1 s | full: every training market | public, free | `fetch_fullhist.py polymarket` | FETCHED (tick contract + wallet sidecar) |
| polymarket.com data-api `/activity` | per-user activity | 1 s | n/a | free, requires a `user` parameter | | wallet-level follow-up only |
| polymarket.com CLOB `/prices-history` | price series per token, fidelity in minutes | 1 min | full (checked: 5,897 points for one NFL game from Sep 1) | public, free | `GET clob.polymarket.com/prices-history?market=<token>&startTs&endTs&fidelity=1` | not fetched; trades already give finer data |
| polymarket.com CLOB `/book` | live book only | | none for closed markets (404) | free | | no history |
| Polymarket Goldsky orderbook subgraph | on-chain OrderFilled events with maker and taker | block time | was full | was free | | deprecated after Polymarket's V2 migration; the endpoint now returns an error saying the data is stale |
| Envio Polymarket dataset (HuggingFace, CC-BY-4.0) | every CLOB fill 2020 to Apr 24, 2026, 1.17 B fills, makers and takers | block time (about 2 s) | full | free, CC-BY-4.0 | DuckDB over HTTPS | not fetched; equivalent to the data-api fills above, useful as a cross-check |
| trentmkelly/polymarket_historical_data (HuggingFace) | 5-min book snapshots with full book JSON and depth levels | 5 min | starts Jul 23, 2026 | CC-BY-4.0 | | no training coverage (holdout period only) |
| pmxt archive (archive.pmxt.dev) | hourly orderbook and trade dumps | hourly | unknown (site refused connection) | free | | unverified |
| Apify scrapers (Kalshi, Polymarket) | live markets and book snapshots | live | none historical | pay per use | | excluded |

Bottom line: there is no free historical ORDER-BOOK DEPTH for Kalshi or polymarket.com covering Aug 2025 to
Jan 2026. The free gains are (1) Kalshi minute-level best bid and ask for every training market, (2) full
pre-game trade history on both venues (median about 10 days on Kalshi, 5 days on polymarket.com), and (3)
polymarket.com wallet ids for every fill, which make the skilled-wallet idea testable.
