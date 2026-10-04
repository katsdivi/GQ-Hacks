# Other venues for US football game-outcome contracts: tradability and data for lead-lag

Research 2026-10-04 (07:05 to 07:13 ET), web plus what is on disk. "Reported" = press, not first-party.
Ranked by (data for our training or holdout period) x (tradability for us) x (plausible lead-lag with Kalshi/CME).

## Ranking

| rank | venue | US retail access | products | launch / history | our data | new lead-lag pair with >= 100 games? |
|---|---|---|---|---|---|---|
| 1 | Polymarket US (CFTC DCM, QCEX) | Yes (app, nationwide rollout, started with NFL and NBA game winners) | game winners | Nov 2025 onward | **On disk, training period**: data/raw/polymarket_us_tns_football, daily trade prints (ts ns, symbol, price, qty) Oct 29, 2025 to Jul 31, 2026: 642,527 prints before 2026-08-01 on 229 games (NFL 524k prints, CFB 118k), 148 games with >= 200 prints, mostly Dec 2025 to Feb 2026. Holdout: live recorder books (Oct 3) and lead test (pre-registered: Kalshi leads Polymarket US by 7.5 s median, not tradable after costs) | **Yes**: Kalshi vs Polymarket US on TRAINING (148 to 183 games) has not been tested with trade prints; the pre-registered lead test was holdout-only. Trades only, no book, so execution would need print-based fills. |
| 2 | CME Group event contracts (via FanDuel Predicts; IBKR reported) | Partly (FanDuel Predicts in a few states, IBKR rolling) | game winners (and spreads/totals listed later per CME SERs) | Dec 6, 2025 | 14 training games with depth (Jan 11 to Feb 8, 2026) bought for $0.88; Databento has no December 2025 game contracts. Holdout-period CME data would need a Databento purchase | Already tested (this branch): Kalshi leads CME; not tradable after the CME spread. More games would need 2026 data ($, quote first) |
| 3 | Crypto.com / CDNA (via Underdog in 16 states; Crypto.com app) | Yes, state-limited (reported) | NFL, college football, other leagues | Sept 2025 (Underdog partnership) | None. No public historical trade API found | Unknown; data would have to be recorded live from now on (no history) |
| 4 | polymarket.com (non-US) | Not tradable for us (non-US) | full sports menu | years | On disk: training trades for about 960 B games (data/ticks), full history being fetched (branch data-fullhist) | Already used: in-game Kalshi leads (IS 0.04); pre-game polymarket.com leads (IS 0.67, leadlag2 R1). Signal only |
| 5 | Kalshi via Robinhood / Coinbase / Webull | Yes | same Kalshi markets | Aug 2025 (Robinhood), later Coinbase | Same order book as Kalshi | Not a new pair (same exchange) |
| 6 | DraftKings Predictions (Railbird DCM) | Yes, state-limited (reported) | game winners, spreads, totals, props (filed Aug 10, 2026) | 2026 | None | Not enough history for training; record live |
| 7 | Novig, ProphetX (CFTC DCMs) | Yes (Novig 50 states, June 2026; ProphetX June 2026) (reported) | sports exchange markets | June 2026 | None | Only holdout-period history at best; no historical API found |
| 8 | Interactive Brokers ForecastEx | Yes, but sports for retail undecided (reported) | mostly non-sports | 2024 | None | Not a football venue yet |
| 9 | Sporttrade | DCM application filed (reported); state sportsbook exchange in NJ/CO | sports exchange | n/a | None | No |
| 10 | Fanatics Markets, Underdog | via CDNA or Kalshi | sports | 2025 to 2026 | None | Not separate pairs (CDNA or Kalshi books) |
| 11 | PredictIt | Yes | politics only, no sports | n/a | None | No |
| 12 | Betfair Exchange | Not available to US persons | NFL, college football, in-play | decades | Historical data sold by Betfair (paid, PRO data) | Possible as a signal-only pair, paid data, not tradable for us |

## New lead-lag pairs with >= 100 games

1. **Kalshi vs Polymarket US on training (Dec 2025 to Feb 2026)**: 148 games with >= 200 prints already on disk,
   free. This is the only new pair that can be tested now without spending. Trade prints with ns timestamps; no
   book, so fills would be print-based.
2. **Kalshi vs CME on the 2026 season**: tradable in principle (CME, via FanDuel Predicts or IBKR), but
   needs a Databento purchase for 2026 books (quote first), and the training evidence says the CME spread
   eats the move.
3. **Kalshi vs Crypto.com/CDNA**: tradable for some US states, but no history; would need live recording from now
   on before any test.

Sources (first-party where available): CME press release 2025-11-12 (cmegroup.com media room); CME Submission
25-466 (cftc.gov ptc11192532737.pdf); developer.webull.com trade-api/event-contract. Press: theblock.co (Robinhood,
Coinbase, Crypto.com/Underdog), bitcoinmagazine and cointelegraph (Polymarket US launch), actionnetwork/covers/defirate
(ProphetX, Novig), legalsportsreport/igamingbusiness (DraftKings Railbird), defirate/forklog (IBKR).
