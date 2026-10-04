# STATUS

Updated by Claude Code at the end of every task. Divi pastes the block below into his planning chat.

```
STATUS  (last update: Sun Oct 4, 3:30 AM ET)
HOLDOUT RUN: done once, 02:00:23 to 02:32:24 ET Oct 4, RUN_COMMIT 872ff43, exit 0, missing files/keys none.
  Outputs committed on main 5ef528f (02:53:39 ET), pushed; results/holdout/inputs_a_meta.csv gitignored (raw Kalshi
  settlement records, sha256 cf7ffbc6...dce5e). Before the run: stop script failed at step 3b (01:00:44 ET); steps
  4, 5, 3b, 6 done by hand on 872ff43; refetch 45 Kalshi + 25 polymarket.com files (guard bypassed at runtime);
  checklist PASS. Disclosure cfcdbb7 (t17).
PRE-REGISTERED RESULTS (results/holdout/, numbers.json):
  Orientation gate PASS (n 670, median 1.0100, p5 1.0000, p95 1.0200, 0 outside).
  Lead, polymarket.com: 88 qualifying, median lag 0.0 s, share positive 0.125, MW p 0.709 vs Holm 0.05,
    placebo median -1.0 s -> I (neither venue leads; all 3 conditions fail).
  Lead, Polymarket US: 76 qualifying, median 7.5 s, share positive 0.921, MW p 3.24e-08 vs Holm 0.025,
    placebo median 0.0 s -> K (kalshi leads).
  Receipt diagnostic (Vultr): kalshi median 0.030 s p90 0.034; polymarket.com 0.052 / 0.218; Polymarket US 0 rows.
  Laggard (exploratory): polymarket.com 521 trades at 1 s, -3.60 c [-4.72, -2.58]; Polymarket US 1,688 at 0 s,
    +1.55 c [+0.99, +2.07]; PM US capacity not measurable.
  A (theta 0.80): 263 trades / 768 games, ROC Webull -0.0300 [-0.0687, +0.0061], direct -0.0147
    [-0.0504, +0.0205]; placebo -0.4626. A-maker: 314 attempts, 9 fills, ROC Webull -0.150 [-0.496, +0.111].
  B (5c/10s/300s): 2,478 trades, net -4.67 c [-4.98, -4.36] Webull, -3.45 direct; costs x2 -9.67.
  Combined: Sharpe -7.78 (ann.), max DD $1,224, skew -3.18, worst month 2026-09 -$678; French n/a.
  B orientation check (0014b1e rule): 0 flagged of 477; median |K - PM| 0.0375; 25 games > 0.10.
POST-RUN DIAGNOSTICS (exploratory, results/holdout_diag/ on t17, do not change any pre-registered result):
  a  Lag = first max over -15..+15 (ties go to the MOST NEGATIVE lag). 0 tied games in every group; recomputed lag
     = recorded in 318/318. polymarket.com: 77 at 0, 11 at +1 (corr at 0 median 0.371 vs best negative 0.056).
     Polymarket US: 17 of 76 at +13..+15 (top of range).
  b  Polymarket US rows carry no venue timestamp (src_ts_ns null in 317,105 rows; ts = poll receipt). Not measurable
     from recorded data.
  c  PM US laggard: 1 s +1.480 [+0.924, +1.998]; 2 s +1.329 [+0.776, +1.842]; 5 s +0.930 [+0.361, +1.432];
     fee 0.0695 x C x P(1-P) banker's cent; 10 contracts assumed, no depth.
  d  25 games: 0 mismatch, 12 stale venue (polymarket.com), 13 real disagreement; B excl. them -4.62 c
     [-4.93, -4.31] (all: -4.67).
  e  A by league, holdout: CFB 259 trades / 670 games, NFL 4 / 98 (training CFB 258 / 936, NFL 44 / 331).
  f  A costs x2 ROC (run_strategy_a.costs_x2 + boot_ci): holdout Webull -0.0584 [-0.0957, -0.0233], direct
     -0.0283 [-0.0664, +0.0076]; training check exact (-0.0377).
  g  Only latency varied; reproduces the run's 14 points exactly. PM US mean > 0 at every latency 0..10 s; CI
     lower bound > 0 up to 5 s (7.5 s: [-0.05, +0.95]); mean does not cross 0 by 10 s (+0.08). polymarket.com
     < 0 at every latency (1..11 s). Daily Sharpe degenerate (one trading day), not reported. Per-game Sharpe
     (not annualized) PM US 1 s 0.547, 82% of games positive; excl. top 5 games +1.08 c.
  h0 Vultr: 0 PM US 429s / 0 errors logged (200s are not logged; /bbo never polled). Mac: 0 429s, 138 request
     errors (126 in 20:00-21:00 ET). Median gap between recorded PM US quote CHANGES ~31.6 s; snapshot age at
     1 s fills median 17.3 s entry / 1.7 s exit; fills with both ages <= 1.5 s: 28, +0.43 c [-1.37, +2.45].
  h1 LIVE: the polled endpoint is Cloudflare-cached, Cache-Control public max-age=30, cf-cache-status HIT,
     Age 1..29 s. No body change in 120 s (03:14 ET).
  h2-h5 (partial: before 17:00 ET Oct 3; T&S 20261003 file, 604 fills / 39 games): delay (receipt - venue trade
     time) median 19.2 s, p10 5.3, p90 28.2 (n 30,181 matched; 30 s cutoff). Fills confirmed by a real print
     at our price or better within [-1 s, +2 s]: both legs 2.3% at 1 s (entry 5.3%, exit 41.7%). Subset all
     fills +2.24 c [+1.59, +2.74]; both-confirmed (14 fills) -4.09 c [-5.47, -2.37].
NEXT: nothing started. Pending Divi: whether/how to disclose the PM US cache finding; t17 merge; numbers sheet.
```

## Log

- 2026-10-03 ~07:15 UTC: leadlag.py crash fix (no-jump games) merged after spec freeze; method unchanged; no results seen before the fix. (eedd1fe, merged to main)

## Task log

| Task | Status | Verified with | Notes |
|---|---|---|---|
| T1 Repo, fake game, hypothesis | done | clean clone loads 75,600 rows; regen gives identical data (parquet footer bytes differ, values equal) | |
| T2 CME data check | done: PASS (Jan to Feb 2026 only) | `out/cme_game_coverage.csv`; LAR at CHI 1,421 trades | $1.66 of Databento credit spent in total |
| T3 Kalshi same game | done | `out/nfl_20260118_lar_chi_overlay.png`; 189,475 Kalshi trades | kickoff 23:30Z is estimated from trade activity, confirm |
| T4 Live recorder | todo | | |
| T5 Lead/lag | todo | | |
| T6 First trades + costs | todo | | |
| T7 run.py, tag v0-made-it | todo | | |
| T8 Overnight download | todo | | |

## T2 findings (CME on Databento)

- Single-game contracts are options on Globex: raw symbol `FG<team><month><y><dd> C0001` (team wins, $0.01 to $0.99, scale 1) and `P0001`. Parent symbol `FG<team>.OPT` / `CG<school>.OPT`. Groups `NFLG` / `CFBG`; the future (group `0E`) never trades. Almost all volume is on the C0001 call.
- Team codes come from the season contracts (`FS<team>`, `CS<school>`, groups `NFLS`, `CFBS`). NFL codes are padded to 3 letters: GBX, KCX, LVX, NEX, NOX, SFX, TBX.
- Coverage: Dec 2025 has nothing on Databento (parent and guessed raw symbols both unresolved). First data 2026-01-11 00:00 UTC, so the Jan 9 to 10 CFP games have no trades. 2026 season: only the Aug 29 CFB week 0 games were listed (one counted: CGFSUQ629, 0 trades); nothing listed in Sep 2026, and the Sep 27 full definitions file has no FG/CG symbols.
- Databento side on LAR at CHI: 1,323 B (buy aggressor) vs 98 A. Looks lopsided; check before using CME trade side for anything.

## Polymarket US data sources (checked 2026-10-03, metadata only, no prices examined)

- Live recorder: venue `polymarket_us` since 2026-10-03 08:30:24 UTC. Public gateway, no key. Batched GET /v1/markets?slug=... once a second gives best bid/ask (no sizes) for every NFL/CFB moneyline in the date window (116 on Oct 3; 14 NFL + 102 CFB, all mapped to Kalshi games in data/live/polymarket_us_map.json). The long instrument is the away team, flipped to P(home). Game discovery uses /v2/leagues/{nfl,cfb}/events (the /v1/markets filters do not return them).
- Market websocket wss://api.polymarket.us/v1/ws/markets: HTTP 401 without an API key.
- GET /v1/markets/{slug}/bbo (sizes, sharesTraded, lastTradePx): 429 even at 1 request/s, so not polled.
- Price history (GET /v1/price-history, params `symbol`, `timestamp.startTimestamp`, `timestamp.endTimestamp`, `fidelity`): book-derived display prices (ask = longPrice, bid = 1 - shortPrice), not trades. A custom 7 h window around a past game (aec-nfl-bal-mia-2025-10-30) returned 421 points spaced exactly 60 s apart. Presets: 1 min (last hour/6 h) up to daily (INTERVAL_ALL).
- Closed NFL/CFB moneylines on Polymarket US: 246 (NFL 190, CFB 56), game start 2025-10-31 to 2026-03; none earlier, none closed yet in the 2026 season (20,997 closed moneylines scanned).
- Trade-by-trade history, public: YES. Daily Time & Sales CSVs at polymarketexchange.com/time-and-sales.html (manifest /files/time-and-sales/manifest.json): 339 daily files 2025-10-29 to 2026-10-02, columns Transaction Time, Symbol, Last Price, Last Quantity. Timestamps are nanosecond (9 fractional digits, ISO with offset); no aggressor side; 14% of trades share an exact timestamp (multi-fill). Symbols are the gateway slugs (aec-nfl-..., aec-cfb-...). Example training day 2025-11-16: 592 trades, 536 on 14 football markets. Downloaded to data/raw/polymarket_us_tns/ (gitignored); files from 2026-08-01 on are holdout and not opened.
- Time & Sales verification (2026-10-03): "Transaction Time" = timestamp of the executed trade (docs.polymarket.us/faqs/execution-tape); each file is one trading day 17:00 to 16:59 ET (the 5 PM ET reporting cutoff), posted ~6 PM ET; trades are spread through the day at ns precision, so the time is execution time, not batch time; D = 0 for this venue. Shared timestamps: 100% within one symbol (one order filling several resting orders), not cross-market batching.
- Training-period counts (counts only, no prices; out/polymarket_us_training_game_counts.csv): 222 football symbols with trades, 215 matched to T8 Kalshi games (NFL 162, CFB 53). Trades per game in kickoff - 2 h to + 5 h: median 442 (NFL 262, CFB 909), p10 8, p90 4,057. In-game trades/min (median of game medians): 1.0 (NFL 0.0, CFB 3.0). Games with >= 50 window trades: 165. Converter: ingest/polymarket_us_tns.py keeps NFL/CFB rows only (data/raw/polymarket_us_tns_football/, gitignored); holdout files not downloaded.
- Authenticated only (401 without a key): /v1beta1/report/trades/search and /trades/stats (api.polymarket.us), institutional report API (api.prod.polymarketexchange.com, bearer token); trade candles are trade-derived OHLC and also need a key. Report trade search returns only your own accounts' trades (docs).
- EZParlays V2 (Divi's other project): its `source=polymarket` capture is mostly Polymarket US (aec-nfl slugs), 2026 season only (holdout), snapshots about every 8.5 min per market: too coarse for second-level lag and sealed anyway. Its `data/historical/kalshi_ingame` and `kalshi_candles` are Kalshi 1-minute bid/ask/trade candles for the 2025 season (training): a possible source of historical Kalshi bid/ask at 1-minute resolution (Strategy B fills). Its own POLYMARKET_US_PROBE.md (2026-09-08) agrees with the findings above.

## Decision A (Oct 2, ~11 PM ET): CME vs Kalshi dropped

Retired in `HYPOTHESIS.md` (appended section, original text untouched): 0 CME NFL games in the holdout, the CFB week-0 game checked had 0 trades, ~18 training games. Next candidate: Kalshi vs Polymarket, draft in `HYPOTHESIS_v2.md` (not committed, waiting on Divi).

## Polymarket feasibility (checked 2026-10-02, no prices examined)

- **Access, trading.** Two venues. Polymarket international (polymarket.com, on-chain order book) blocks US persons from trading. Polymarket US (CFTC regulated via QCEX since Nov 2025, sports only) is rolling out by state; third-party guides list it as unavailable in Arizona (no first-party state list found; the Arizona cease-and-desist naming Polymarket is UNVERIFIED, see Amendment 2 draft; Arizona criminal charges against Kalshi and the CFTC suit also from third-party sources). Paper trading only for us anyway (hard rule 6).
- **Access, data.** International venue data is public, no key: Gamma API (`gamma-api.polymarket.com`) for events and markets, Data API (`data-api.polymarket.com/trades?market=<conditionId>`) for trades, CLOB (`clob.polymarket.com`) for live book and price history, public market websocket for live books. Polymarket US market data API not checked yet.
- **Historical trades.** Data API returns full taker trade history per market, checked on 3 games (taker notional is about half of reported two-sided volume). Limits: `offset` max 10,000 and `limit` up to 10,000, so markets with more than ~20,000 taker trades will be cut short; timestamps are whole seconds (15 to 23% of in-game trades share a second). Historical order book: CLOB `/orderbook-history` stopped producing snapshots around 2026-02-20, so no free historical book for most games; trades only (fill model must be trade+halfspread).
- **Game counts, training period (kickoff 2025-08-01 to 2026-07-31).** NFL: 285 game events (series 10187), all with a moneyline market (full 2025 season incl. playoffs and Super Bowl). CFB: 829 game events (series 10210), 715 with a moneyline market. Current season is under different series ids (12185 NFL, 12756 CFB); holdout listings not counted on purpose.
- **In-game activity, 3 NFL games picked by date before looking (first slug alphabetically on each date), moneyline taker trades, kickoff to +3h15m:**
  - nfl-atl-min-2025-09-14: 1,058 trades, median 5/min, 12 of 195 minutes with no trade
  - nfl-atl-no-2025-11-23: 1,158 trades, median 5/min, 11 of 195 minutes with no trade
  - nfl-atl-ari-2025-12-21: 1,087 trades, median 5/min, 7 of 195 minutes with no trade
- **Fees (international venue).** Taker only, makers free: `fee = C x rate x p x (1 - p)`, sports rate 0.05 now (official docs). Secondary sources say sports was 0.03 from 2026-03-30 and rose to 0.05 in July 2026; fees before 2026-03-30 not confirmed. Andrew to confirm history for the training period.
- **Polymarket US vs polymarket.com (added Oct 3).** Separate exchanges with separate order books and separate accounts (Polymarket help center; Polymarket US is QCX LLC, a CFTC designated contract market). Odds usually track but liquidity is split.
  - polymarket.com (international): NFL and CFB game markets for the 2025 season and now. Public trades back to the start of each market, 1 s timestamps. US residents cannot trade it.
  - Polymarket US: sports only, has NFL and CFB game markets (public `gateway.polymarket.us/v2/leagues/nfl/events` and `/cfb/events` return large lists). The only venue a US resident can legally trade, but not from Arizona (state cease-and-desist). Public API gives markets, live book, BBO and a book-derived price history (about 1-minute points, not trades). Trade history is NOT public: `/v1/report/trades/search` returns only your own account's trades, floor 2026-05-01. Live trades need the authenticated markets websocket (API key, which needs a KYC account). Fees from 2026-10-01: taker 0.0695 x C x p(1-p), maker rebate 0.0125.
  - So historical lead/lag can only use polymarket.com. Polymarket US can only be recorded live, and only with an API key.
- **Timestamp resolution.** polymarket.com historical trades: 1 second (`timestamp` is unix seconds). That is the floor on any lag we can measure on past games. Kalshi: microseconds (`created_time`).
- **Verdict.** Feasible for data and paper research (285 NFL + 715 CFB training games, live data public). Not tradable for real from Arizona on either Polymarket venue. Main risk: Polymarket is thin (about 5 trades/min vs Kalshi ~390/min on the CME game) and its 1 s timestamps limit how small a lag we can see.

## T3 notes (Kalshi)

- Data before `GET /historical/cutoff` (trades_created_ts, now 2026-08-03) is only on `/historical/markets` and `/historical/trades`; `/markets/trades` returns empty for those. `ingest/kalshi.py` switches automatically.
- Home/away from the event `sub_title` ("LA at CHI (Jan 18)"); team code is the market ticker suffix.
- Some Kalshi events are duplicated with zero volume (e.g. KXNFLGAME-26JAN17SFSEA, KXNFLGAME-26JAN25LASEA). Pick the market with volume.
