# STATUS

Updated by Claude Code at the end of every task. Divi pastes the block below into his planning chat.

```
STATUS  (last update: Sat Oct 3, ~1:05 AM ET)
Current task: review fixes DONE on branch t5b-fixes (3d3cda7), not merged; main = a532304 (v0-made-it kept on 850f081)
Done: merge t5-made-it -> main; HYPOTHESIS_v2.md Amendment 1 committed bc9d583 (00:41 ET) BEFORE the code change;
  fill bounds, trailing 3 s median price, latency label, run.py fetches missing public ticks
Verified numbers (latency 1 s; 0 s = decision within 1 s of the move; PLACEHOLDER FEE 2c/fill; PROVISIONAL):
  Fake game: cme 15/15 jumps, median +2.0 s, xcorr +2 s; placebo (kalshi leads) 15 jumps, 0 signals, 0 trades;
    edge -88.0c at 0 s and 1 s: the 3 s median adds ~1 s detection delay, using up the 2 s planted lag (5 s lag test: positive); 10 tests pass
  Jumps with 3 s median vs last trade: was_mia kalshi 180 (was 286), polymarket.com 114 (was 152); fake 15 (was 15)
  nfl_20251116_was_mia:
    kalshi leads: 180 jumps, 116 covered, median +10.5 s, xcorr +10 s; 92 trades on polymarket.com:
      lower bound -37.8c (-0.41c/trade), upper bound -21.7c (-0.24c/trade)
    polymarket.com leads: 114 jumps, 57 covered, median +6.0 s, xcorr -10 s; 21 trades on kalshi -100.0c (-4.76c/trade)
  Clean clone with NO data files: run.py fetched was_mia (49,291 kalshi + 2,977 polymarket.com trades), ticks identical
    (52,268 rows); stdout, leadlag/signals parquets and chart md5 identical for both games
Flags: lower-bound polymarket.com entry fills can use trades matched up to (D p90 - D) s after the fill (chosen adverse; decisions never see it)
Blockers: none. Pending from Divi: Kalshi key (websocket), Vultr IP, TIGER_DATABASE_URL
Next: Divi reviews t5b-fixes + docs/review_t5.md, merges; Alden hand-checks; T8 finishing (~1.5 h); no multi-game run yet
Decisions pending: price definition (Alden), B (Webull, deferred)
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
