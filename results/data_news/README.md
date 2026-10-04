# data_news: timestamped news events for training games (Aug 2025 to Jan 2026)

Output (gitignored): `data/raw/news/events.parquet`. Columns: ts_utc (ns, UTC), source, league, team (Kalshi code), game_id, event_type
(injury_out, questionable, qb_change, inactive, other), headline, url, ts_precision (second/minute/day), plus publisher,
hrs_before_kick, in_6h_pre_kick (true only for non-day-precision rows within 0 to 6 h before kickoff).
For lead-lag use filter `ts_precision != "day"`.

Regenerate (fetch stages are resumable and can run in parallel, then build):

    for s in gnews gdelt reddit bsky; do python3 scripts/fetch_news.py --stage $s & done; wait
    python3 scripts/fetch_news.py --stage build

Rate limits respected (<= 2 req/s per host; GDELT one per 5 s, in practice ~1 per 40 s).

## Sources, in order tried

| Source | Result | Timestamp | Used |
|---|---|---|---|
| ESPN league news / team news API | Works but shallow: newest 50 items only (about 2 days back). No history for 2025. | second | no (probe only, `probe_espn.json`) |
| ESPN summary JSON `news` (cached) | 7,596 articles, all published Oct 2026 (fetched after the fact). Not training-period. | second | no |
| ESPN summary JSON `injuries` (cached) | 3,310 NFL entries, all dated Aug to Oct 2026 snapshots. Not training-period. | minute | no |
| nflverse injuries_2025 | Works. Official report status (Out/Doubtful/Questionable) per player-week. Only season+week, no report date, no intraday time. Placed at game date 00:00 UTC. | day (week-level) | yes, flagged day |
| Google News RSS, per team per game, date-filtered | Works for history. pubDate of historical items is truncated to 00:00 Pacific (07:00/08:00 GMT) so effectively day precision; 311 items carry a real time. Titles only. | day (mostly) | yes |
| GDELT DOC 2.0 API | Works for 2025 history, `seendate` on a 15 min grid (first crawl, upper bound on publish time). Very slow and throttled (429s): only 31 of 331 NFL games fetched, randomly ordered (partial). CFB not fetched. | minute | yes, partial |
| Reddit r/nfl, r/CFB via Arctic Shift | Works, free, full Aug 2025 to Jan 2026 pulled (~100 posts/day). Second precision. Includes insider repost posts (`[Schefter]` style titles). Filtered to injury/status keywords and team-matched. | second | yes |
| Bluesky public API (getAuthorFeed) | Works for tompelissero, rapsheet, mortreport (searchPosts is 403). Adam Schefter's account is dormant (last post 2024); ianrapoport, jordanschultz, mikegarafolo, others absent or 400. | ms | yes (NFL mostly) |
| Apify X (apidojo/twitter-scraper-lite) | Works, second precision tweets from Schefter/Rapoport. Free plan returned only 10 items for 3 queries (Oct 12, Nov 16, Dec 14 2025), so only 4 attributed rows kept (Oct 12). | second | yes, tiny |
| Wayback CDX | Works for espn.com/nfl (snapshots a few per day) but no snapshots for espn injuries or NBC Sports RSS; would need page parsing. Snapshot times only bound news timing. | hours | not used |
| Wikipedia revisions API | Reachable, free, second timestamps; not built (rough proxy, per-player page mapping needed). | second | not used |
| Mastodon tag timelines | Reachable but only recent items, no 2025 history. | second | no |
| ESPN/CBS/NBC RSS, NFL.com transactions | Reachable, live only (current items), no history. Useful for live use, not training. | second | no |

## Counts (events.parquet, 60,486 rows)

By source: gnews_rss 55,025 (NFL 36,213, CFB 18,812); nflverse 2,761; reddit 1,490; gdelt 759; bluesky 447; apify_x 4.

By source, league, event_type:

| source, league | inactive | injury_out | other | qb_change | questionable |
|---|---|---|---|---|---|
| apify_x NFL | 1 | 1 | 2 | 0 | 0 |
| bluesky CFB | 0 | 0 | 3 | 0 | 1 |
| bluesky NFL | 88 | 71 | 160 | 16 | 108 |
| gdelt_doc NFL | 22 | 36 | 677 | 1 | 23 |
| gnews_rss CFB | 47 | 1051 | 16067 | 349 | 1298 |
| gnews_rss NFL | 1668 | 2313 | 28242 | 732 | 3258 |
| nflverse NFL | 0 | 1371 | 0 | 0 | 1390 |
| reddit CFB | 0 | 31 | 228 | 27 | 22 |
| reddit NFL | 49 | 164 | 744 | 49 | 176 |

Event types come from regexes on the headline (rough; `other` is the bulk).

## Timestamp precision

Minute-or-better rows: 3,011 of 60,486 (4.98%): reddit 1,490, gdelt 759 (minute), bluesky 447, gnews 311, apify 4.
All other rows (gnews 54,714 and nflverse 2,761) are day precision, recorded and flagged.

## Coverage of training games (1,267 games: 331 NFL, 936 CFB)

- Games with any event (any precision): 1,260.
- Intraday (non-day) rows within 6 h before kickoff: 608 rows covering 203 games (NFL 165 of 331, CFB 38 of 936).
- In that set by type: inactive 158, injury_out 37, qb_change 16, questionable 29, other 368.
- Non-"other" intraday events overall: reddit 518, bluesky 284, gdelt 82, gnews 89, apify 2.

## Known biases

- Google News history is day-truncated, so it cannot be used for first-mover timing; it is mainly useful for existence and day.
- GDELT `seendate` and Reddit post time are after the original publication or tweet; both lag the true event, Reddit by minutes to hours. Bluesky/X posts are closest to source but cover only a few reporters.
- GDELT is a partial random sample of NFL games only; CFB intraday coverage is thin (Reddit only).
- Team attribution is keyword based (NFL nickname, CFB school name); ambiguous names (e.g. "Texas", "Giants") produce false positives. A news item is attached to every game of that team kicking off within the following 48 h (and up to 4 h before).
- nflverse report status has no date; its ts_utc is the game date at 00:00 UTC, not a real time.
- Late indexing: Google News and GDELT only index items after crawling.
- ESPN APIs hold no training-period history.

## Apify spend

One run (apidojo/twitter-scraper-lite, 3 queries, 10 items, 0.003 compute units). The API did not report cost; estimate from the actor price list is about $0.05 (3 x $0.016 query + 10 x $0.0004 items + compute), far below the $5 cap.
