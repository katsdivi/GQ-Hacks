# STATUS

Updated by Claude Code at the end of every task. Divi pastes the block below into his planning chat.

```
STATUS  (last update: Sat Oct 3, 4:05 PM ET)
Current task: 3:35 PM list done except sim part (a) (running) and the power sentence that waits on it
Done:
  1 Sim (b) on sim box (fa5b19f, seed 20261003, 500 reps, 8 procs, 585 s): docs/results/sim/ (8b2071d).
    Lead/zero cells reproduce the 14:52 run 24/24. Preset rule -> DESIGN 1: D2 zero-lag upper 0.8% (pass),
    shared-shift (iid) D2 upper polymarket.com 6.8% n30, 5.6% n40, 8.2% n60 (FAIL); PM US 2.9/5.9/5.1% (pass).
    D2 point estimates no worse than D1 (0.036-0.058 vs 0.048-0.058); a 5%-sized test has expected upper 7.3%.
    Reverse lead: Kalshi-leads 0/500 every cell. Clustered shared-shift (sensitivity): <= 1% everywhere.
  2 Fees: t9-costs ba36a6a + 7528eab (fees.md). polymarket.com 5 dp HALF_UP (direction unstated in docs), no
    cent ceiling; Polymarket US 0.0695, HALF_EVEN cents, raises before 2026-10-01 14:00 UTC. Hand tests incl.
    C=120 P=0.50 raw 2.085 -> 2.08, C=1000 -> 17.38. Integer reference grid 79,600 cases (199 prices x C 1..100
    x 4 schedules; the old 59,700 was x 3) all equal. t13: no Polymarket fee code exists there, nothing to fix.
  3 A3 draft (uncommitted): fallback [T-2, T+20], T = min(ESPN, map game_start = Gamma gameStartTime; equal
    in 111/112, 1 min later in 1). Runner + test a0ea17d: 15-min copy leaks under +10 in 15/20, under +20 0/20.
    Limitation paragraph added; placebo sentence filled (Design 1); power sentence placeholder.
  4 v3 Amendment 3 draft (uncommitted, for review): all 4 blank settlements are Kalshi "scalar" 0.5000
    (GB-DAL + 3 preseason); games table re-settled (777/486/4 x 0.5). Preseason flag (NFL Jul/Aug ET, 49 games)
    + side-by-side summary; fill cap 0.99 with n_capped_fills; strategy_a a1b24c9. Conf champs + SB excluded
    (no 2-market Kalshi game event; SB only in 32-market KXSB-26). A NOT run.
  5 .venv-exec with webull-openapi-python-sdk 3.0.2 (d34b762); collector .venv pip freeze identical (63 pkgs)
  6 Mac gap 11:57-12:34 ET = lid closed on battery ("Clamshell Sleep", pmset), DarkWakes only until 12:40;
    9 clamshell sleeps today incl. 14:00:41 (226 s). Mac polymarket heartbeat live (last_ok 19:57:13Z).
    Holdout games kicked off by 15:57 ET (62/112), heartbeat/GAPS rule, nominal window end:
    polymarket.com 57 clean on Vultr, 0 only on Mac, 5 excluded; PM US 52 / 0 / 1, 9 no PM US instrument
  7 Secrets scan clean (11 unpushed commits); all named branches pushed; nothing merged to main
  8 laggard.py on t14-laggard (7e2f760, = t13 + merge of t9-costs): 9 synthetic tests pass
Running: sim (a) power n=30/40/60/80 on sim box (tmux gqhsim), started 15:57 ET, ~3.2 h
Next: scp (a) -> docs/results/sim/a, fill A3 power sentence; Divi commits A3 (v2) and reviews v3 A3
Decisions pending: D1 vs D2 rule per venue or joint (joint applied -> D1); keep Mac on AC with lid open
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
