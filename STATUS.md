# STATUS

Updated by Claude Code at the end of every task. Divi pastes the block below into his planning chat.

```
STATUS  (last update: Fri Oct 2, ~11:50 PM ET)
Current task: HYPOTHESIS_v2.md final text out for Alden's review (not committed); T4 recorder live on the Mac
Done: T1, T2, T3; CME vs Kalshi retired (f12c1dc) + count correction ~14 games (d37d9df); recorder committed (d842ead)
Verified numbers:
  Recorder (Mac, Kalshi REST polling, 218 game markets, local parquet only):
    before restart 03:09:16-03:39:16 UTC: 15,640 trades, 3,821 bid + 3,509 ask rows, 0 of 30 minutes empty
    killed 03:39:28, back up 03:39:34 (6 s); after-restart 30-min window ends 04:09:34 UTC
  polymarket.com trade timestamp = on-chain block time (20 of 20 trades, two training games); match-to-block delay not measured yet
Blockers: none tonight. Waiting on Divi: Vultr IP, Kalshi API key + .pem, TIGER_DATABASE_URL (deploy script ready: collector/deploy_vultr.sh)
Next: Alden reads v2 -> commit v2 -> Polymarket book websocket in recorder; Vultr deploy when keys arrive; then T5-T7 Made It on one training game
Decisions pending: v2 approval (Alden), B (Webull paper orders, deferred)
```

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

## Decision A (Oct 2, ~11 PM ET): CME vs Kalshi dropped

Retired in `HYPOTHESIS.md` (appended section, original text untouched): 0 CME NFL games in the holdout, the CFB week-0 game checked had 0 trades, ~18 training games. Next candidate: Kalshi vs Polymarket, draft in `HYPOTHESIS_v2.md` (not committed, waiting on Divi).

## Polymarket feasibility (checked 2026-10-02, no prices examined)

- **Access, trading.** Two venues. Polymarket international (polymarket.com, on-chain order book) blocks US persons from trading. Polymarket US (CFTC regulated via QCEX since Nov 2025, sports only) is rolling out by state; it is NOT available in Arizona (Arizona Dept of Gaming cease-and-desist; Arizona also filed criminal charges against Kalshi in March 2026; the CFTC has sued Arizona). Paper trading only for us anyway (hard rule 6).
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
