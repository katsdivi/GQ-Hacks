# Paid options for timestamped line history (NOT purchased; awaiting Divi approval)

Sources: the-odds-api.com pricing page and v4 docs, fetched 2026-10-04. Verify on the page before buying.

## The Odds API (historical)
- Plans (monthly): Starter free 500 credits (no historical); 20K = $30 / 20,000 credits; 100K = $59 / 100,000; 5M = $119 / 5,000,000; 15M = $249 / 15,000,000. Historical endpoints need a paid plan.
- Endpoint `/v4/historical/sports/{sport}/odds`: cost = 10 x markets x regions per call, and one call returns ALL events of that sport at that snapshot. So price by snapshot slots, not by game.
- Snapshots: 5-minute grid since Sep 2022 (10 min before). Response has snapshot `timestamp` and per-bookmaker `last_update`. Data from 2020-06-06, so Aug 2025 to Jan 2026 is covered.
- Markets h2h + spreads, region us = 2 x 1 x 10 = 20 credits per call (h2h only = 10).
- Per-event endpoint costs the same per call per event, so it is far more expensive for this use; use the bulk endpoint.

Union of snapshot slots over the 1,267 training games (windows end at kickoff), both sports (americanfootball_nfl 331 games, americanfootball_ncaaf 936 games):

| Option | Calls (NFL + NCAAF) | Credits (h2h+spreads, us) | Credits (h2h only) | Cheapest plan that fits one month |
|---|---|---|---|---|
| Hourly, kickoff-24h to kickoff | 1,977 + 1,977 = 3,954 | 79,080 | 39,540 | 100K at $59 (h2h only: 100K too; 20K plan is too small) |
| 10 min, kickoff-6h to kickoff | 4,220 + 4,746 = 8,966 | 179,320 | 89,660 | 5M at $119 (h2h only: 100K at $59) |
| 10 min, kickoff-24h to kickoff | 11,647 + 11,756 = 23,403 | 468,060 | 234,030 | 5M at $119 |
| 5 min, kickoff-24h to kickoff (est., x2 of 10 min) | about 46,800 | about 936,000 | about 468,000 | 5M at $119 |

Recommended: hourly -24h at $59 (one month of the 100K plan) as a pilot, then 10 min -6h at $119 if lead-lag at minute scale is needed. Cancel after one month. Extra cost of a second month is not required. Credits are consumed only on calls that return data.

Caveats: the slot counts assume each call is aligned to a grid and not re-run. A snapshot only shows events that have not started, so in-game movement is not available from this endpoint. Bookmaker coverage (DraftKings, FanDuel, BetMGM, Pinnacle may need region eu) multiplies cost by regions requested.

## Others (not priced exactly)
- SportsDataIO, OddsJam: enterprise or sales-quoted, no public price found; not pursued.
- Apify actors (Covers, Action Network wrappers, ~$0.004 per game of line history) scrape sites whose terms forbid scraping, and they serve current games, so they were NOT run ($0 spent).

## Cheapest option (NFL only, $30 plan)
The 20K plan ($30/month, 20,000 credits) is enough for a pilot on NFL only (331 NFL games in training; 90 from Dec 1; 10 in the Jan playoff window in kalshi_only_games.csv). Credits by window, from the same slot-union method:

| NFL window | Grid | Calls | Credits h2h+spreads | Credits h2h only | Fits $30 plan |
|---|---|---|---|---|---|
| All 331 games | hourly, -24h | 1,977 | 39,540 | 19,770 | h2h only (barely, 19,770 of 20,000) |
| Dec 1 onward (90 games) | hourly, -24h | 602 | 12,040 | 6,020 | yes, both markets |
| Dec 1 onward (90 games) | 10 min, -6h | 1,282 | 25,640 | 12,820 | h2h only |
| Playoffs (10 games) | 10 min, -24h | 756 | 15,120 | 7,560 | yes (could use the free 500 credit Starter for nothing, historical needs paid) |
| Playoffs (10 games) | 10 min, -6h | 291 | 5,820 | 2,910 | yes |

No free trial of historical access exists (docs: historical is paid plans only). The free Starter tier (500 credits, no historical) is not usable here and multiple accounts are not an option.
