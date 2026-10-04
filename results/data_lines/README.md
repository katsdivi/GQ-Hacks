# Sportsbook line data for training games (Aug 2025 to Jan 2026)

Bottom line: no free source gives INTRADAY timestamped line history. The best free data is open and close spread (ESPN BET, some DraftKings) with NO timestamp on the open, plus closing moneylines. Intraday history needs the paid Odds API (see COST_QUOTE.md).

Regenerate: `python scripts/fetch_lines.py` (about 35 min on first run, ESPN core calls cached in data/raw/lines/espn_core/; later runs use `--skip-fetch`). Output: `data/raw/lines/moves.parquet` (gitignored).

## Output
Columns: ts_utc (ns, UTC), source, book, league, game_id (Kalshi game_id from kalshi_only_games.csv, mapped via ids_training.csv), market (moneyline/spread), home_value, away_value, implied_home_prob_novig (moneyline only), ts_precision, plus phase (open/close/current).
Spread values are the home and away points (home -1.5 means home favored). Moneyline values are American odds.

## Coverage (1,267 training games)
- Games with any row: 1,258 of 1,267. Games with any INTRADAY (more than one timed point) history: 0.
- Rows: 4,760, about 3.8 per game (range 1 to 11), all of which are open/close/current snapshots, not moves.
- ESPN BET: spread close 1,108 games, open 1,118, moneyline close 1,031. DraftKings via ESPN core: spread 203 open and close, moneyline close 161. DraftKings via summary pickcenter: 159 moneyline, 203 spread (current). nflverse close: 282 NFL games.
- Timestamp precision: open = none (ts_utc NaT, ts_precision none_untimed_open). Close/current = ASSUMED at kickoff (ts_precision assumed_at_kickoff); ESPN gives no time. Treat as a pre-kickoff level, not an event time.
- Caveat: ESPN "open" moneyLine merely repeats the spread price, so open moneylines are not emitted.

## Sources tried
| Source | Result |
|---|---|
| ESPN summary pickcenter (cache) | DraftKings current only, 208 of 1,266 games, no timestamps. |
| ESPN core `/odds` | Worked: open/close/current per provider (ESPN BET 58, DraftKings, live-odds). No timestamps. |
| ESPN core `/odds/{p}/history/0/movement` | Exists but returned count 0 for all 1,267 games. |
| nflverse games.csv | Closing spread and moneyline, NFL only, no timestamps (baseline). |
| The Odds API historical | Only true intraday source (5 min snapshots, per-book last_update). Paid; quoted in COST_QUOTE.md. Not purchased. |
| Wayback Machine | CDX works, but 2025 ESPN game pages are sparse and the HTML has no embedded odds; 2025 ESPN summary API barely archived. Not usable. |
| Pinnacle guest API (guest.api.arcadia.pinnacle.com) | Reachable with the public guest key, current lines only, no history. Only useful to start a live recorder going forward. Terms unreviewed; not used. |
| Action Network public API (api.actionnetwork.com, and Apify actor zen-studio/action-network-odds, $0.004 per game movement) | Endpoint responds and would have timestamped movement, but terms of use were not retrievable (404) and the site is a commercial product whose ToS normally bars scraping. Skipped under the rules; no Apify spend. |
| Covers.com (and Apify covers actors) | robots has a blanket Disallow for some agents and ToS forbid scraping. Skipped. |
| OddsPortal | Has timestamped movement, but ToS bar scraping and data is JS-encrypted. Skipped. |
| Sportsbookreview archive | Page URL moved (404); archive is season-level open/close in Excel, not intraday, and stops before 2025. Not used. |
| Kaggle spreadspoke / "NFL scores and betting data" | Closing spread/total per game, NFL only, no timestamps. Not added (nflverse already covers). Not downloaded (needs Kaggle login). |
| Kaggle/Scottfree CFB and NFL odds CSVs | Open and close only; Scottfree is paid. |
| GitHub repo search for Odds API archives | No relevant repos with 2025 football snapshots found. |
| Betfair historical (BASIC, free) | 1 minute last traded price; site returned 403 to bots, NFL inclusion unconfirmed (docs list racing, soccer, tennis, cricket, golf, "other"). Needs signup, which was not done. Exchange, not a sportsbook. |
| Unabated, OddsShark, VegasInsider | Public pages show current lines only, no archived history; VegasInsider robots forbids query URLs. Not scraped. |
| PredictIt | Has a public marketdata API but no NFL/CFB game markets of note and only current prices. |
| Polymarket | Extra venue, not a sportsbook. CLOB `prices-history` returns timestamped prices; data already in data/raw/polymarket_*. |
| TeamRankings odds-history | Season results pages with line history; ToS not cleared. Not used. |

## Apify
Spent: $0. Runs: none. Candidate actors were priced (zen-studio/action-network-odds $0.00399 per line-history game, parseforge/covers-scraper $0.004) but both scrape sites with restrictive terms and cover current games.

## Recommended next step
Buy the Odds API 100K plan ($59) for hourly -24h snapshots (79,080 credits), or the 5M plan ($119) for 10 min -6h, then add a loader to this script. Start a forward recorder of Pinnacle/ESPN before the holdout period if intraday free data is needed.
