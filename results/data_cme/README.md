# CME event-contract data for TRAINING games: diagnosis, free fix, quotes, free sources

Branch data-cme-train. Written 2026-10-04 ET. Read-only on vendor data; nothing purchased. Raw vendor data is
never committed (data/ is gitignored); map.csv here holds symbols, game ids and row counts only, no prices.

## Diagnosis: why "only 1 of 32" CME training games mapped

Two causes. One was a mapping bug, fixable for free; the other is real missing data.

1. **Mapping bug.** The 32 CME game contracts dated before 2026-08-01 use the raw symbol format
   `<FG|CG><root><month code><year digit><day> C0001`, e.g. `FGNEXF611 C0001`. The root pads two-letter NFL codes
   with X (GBX, NEX, SFX), and some roots differ from Kalshi codes:
   - JAX = JAC;
   - LAR = Kalshi LA;
   - OLE = Ole Miss, Kalshi MISS.

   The day code is the listed game date, which can be the ET game date or the day after. The wild-card Saturday
   games carry day 11, for example. Matching team + league + ET date within 1 day fixes it. `scripts/cme_train_map.py` does this.
2. **Missing data, CME side.** CME trades and quotes on disk start 2026-01-11 (bbo-1s from 2026-01-10 20:45 UTC).
   Databento symbology resolves the FG/CG game contracts only from 2026-01-11. Even the CFP semifinal contracts
   (games Jan 8 and 9) resolve only from Jan 11. A free brute-force resolve of 3,968 plausible NFL symbols for
   Dec 2025 to Jan 10 found none. CME says pro-football game contracts were listed effective Dec 6, 2025, so
   either their December symbology differs or Databento lacks them. A one-day definition pull ($0.81, see
   COST_QUOTE.md) would settle it.
3. **Missing data, Kalshi side.** `data/raw/kalshi_only_games.csv` ends at kickoff 2026-01-18. The CME contracts
   for the CFP final (Jan 19), the two conference championships (Jan 25) and the Super Bowl (Feb 8) have no
   Kalshi training file. Kalshi trade history is free through its public API, so these 4 games could be added at
   no cost. That was not done here (CME scope only).

## Coverage

| | before | after free fix |
|---|---|---|
| CME game contracts dated before 2026-08-01 | 32 | 32 |
| matched to a Kalshi training game | 1 (reported by posthoc-costside) | 24 contracts, 12 games |
| contracts with CME AND Kalshi trades in [kickoff - 2 h, kickoff + 5 h] | about 1 | 20 contracts, 10 games |

The 10 usable games are all NFL playoffs:
- wild card: LA at CAR, GB at CHI, BUF at JAC, SF at PHI, LAC at NE, HOU at PIT;
- divisional: BUF at DEN, SF at SEA, HOU at NE, LA at CHI.

They run from kickoff 2026-01-10 21:30 UTC to 2026-01-18 23:30 UTC. Per game the windows hold 103 to 1,684 CME trades per contract and
97k to 275k Kalshi trades. The CFP semifinals map but have no CME data in their window.

Caveat for LA at CAR (kickoff Jan 10 21:30 UTC): CME trades on disk start Jan 11 00:00 UTC and bbo-1s at
Jan 10 20:45 UTC, so its CME trade coverage starts mid-game.

Ten games is a small sample. A lead-lag test there is descriptive, with wide intervals.

## Files

- `scripts/cme_train_map.py`: the mapping and coverage script. It reads data/raw/fg_cg_*.parquet,
  kalshi_only_games.csv and kalshi_only/, and writes data/raw/cme_train_v2/map.csv (gitignored).
- `results/data_cme/map.csv`: a copy of that map. Symbols, game ids and row counts, no prices.
- `results/data_cme/COST_QUOTE.md`: exact Databento quotes for depth (mbp-10), mbp-1 and the December check.

Regenerate (cwd = this worktree): `nice -n 19 ../staleline/.venv-run/bin/python scripts/cme_train_map.py --data ../staleline/data`

## Free sources

Researched 2026-10-04 by web search only. No sign-ups, no spending.

| source | what it provides | timestamp precision | coverage | terms | usable for second-level lead-lag? |
|---|---|---|---|---|---|
| Databento GLBX.MDP3 (paid, with free credit) | full tick: trades, mbp-1, mbp-10, mbo, bbo-1s | ns exchange timestamps | event contracts from 2025-09-25; FG/CG game contracts resolve from 2026-01-11 | $125 free historical credit for new accounts, 6 months, one per team; usage billing after | yes (best source) |
| CME DataMine | Time and Sales, top of book, end-of-day settlement | Time and Sales to the ms or better | historical CME products; event-contract availability not confirmed | paid; small free samples by data type via FTP, not product-specific | samples too small; paid version yes |
| CME Group website and notices | product listings, symbol roots (e.g. FGARI = Arizona game, FS = season), notices | daily | from Dec 2025 | free | no (no intraday history) |
| FanDuel Predicts / DraftKings Predictions | retail apps routing to CME event contracts | live only in the app | from Dec 2025 | brokers; no export or history API found | no |
| Webull, Robinhood, NinjaTrader, TradingView | no evidence that CME FG/CG sports contracts are listed with exportable history | n/a | not found | n/a | no |
| GitHub / open datasets | no repo with saved CME FG/CG sports ticks found | n/a | none found | n/a | no |

Bottom line: no free source gives second-level CME football history. Databento is the only practical source.
The data that would extend coverage (mbp-10 and mbp-1 for the 32 contracts) costs under $0.07, plus $0.81 to
check whether December listings exist at all.

Sources:
- [CME notice 2025-12-19](https://www.cmegroup.com/notices/electronic-trading/2025/12/20251219.html)
- [CME SER 9634](https://www.cmegroup.com/content/dam/cmegroup/notices/ser/2025/11/ser-9634.pdf)
- [SBC Americas, CME sports launch](https://sbcamericas.com/2025/11/20/cme-group-prediction-markets/)
- [Databento, CME event contract data](https://databento.com/blog/historical-cme-event-contract-data)
- [Databento, $125 free credits](https://roadmap.databento.com/announcements/end-of-early-access-125-in-free-credits-for-all-users)
- [Databento usage pricing FAQ](https://databento.com/docs/faqs/usage-pricing-and-data-credits)
- [CME DataMine FAQ](https://cmegroup.com/market-data/datamine-faq.html)
- [Covers, FanDuel event contracts](https://www.covers.com/industry/fanduel-to-offer-sports-event-contracts-november-12-2025)
