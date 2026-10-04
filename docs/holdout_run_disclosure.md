# Holdout run disclosure (draft)

The holdout was evaluated once at **<HH:MM> ET on <date>**, from RUN_COMMIT **<hash>** (scripts/final_test_run.py --i-am-the-one-run; results/holdout/RUN_LOG.md). Nothing in this file changes a rule; it lists what was decided, excluded and seen before that run, with commit hashes and times.

## Pre-registration, in order (main branch; ET commit times)

| commit | ET time | what |
|---|---|---|
| f12c1dc | 2026-10-02 22:20 | Retire the CME vs Kalshi hypothesis before any backtest (0 CME NFL holdout games). |
| d6bfa9c | 2026-10-03 00:01 | v2: Kalshi vs polymarket.com lead-lag hypothesis. |
| bc9d583 | 2026-10-03 00:41 | v2 Amendment 1: lower / upper bound fill rule for polymarket.com timestamps. |
| 508f2db | 2026-10-03 03:25 | v3: Strategy A (Kalshi favorite-longshot) and Strategy B (cross-venue disagreement). |
| 8a509ff | 2026-10-03 11:15 | v2 Amendment 2: book-midpoint holdout lead test with the fixed candidate list. |
| 9507d6a | 2026-10-03 11:42 | v3 Amendment 1: combined A + B book, track reporting, ESPN kickoffs for B, A and B fill corrections. |
| 37170aa | 2026-10-03 13:57 | v3 Amendment 2: Strategy A no-favorite rule, underdog placebo fill. |
| ed5db9b | 2026-10-03 18:14 | v2 Amendment 3: window start, Holm, REST outage, venue rules (per-market 1 s taker delay), placebo Design 1, laggard and diagnostic rules. |
| 8964ea9 | 2026-10-03 19:30 | Power note to v2 Amendment 3 (sim run (a), seed 20261003; changes no rule). |
| d349e50 | 2026-10-03 19:40 | v3 Amendment 3: scalar settlements, preseason by opener date, fill cap 1 - tick, conference games excluded, team markets from trade files, staleness on both markets. |
| f6aa3b5 | 2026-10-03 20:25 | v2 Amendment 4: lead test limited to kickoffs at or before 20:00 ET Oct 3 (106 of 112). |
| cf8f4e9 | 2026-10-03 21:22 | v2 Amendment 5: laggard trading end min(kickoff + 4.5 h, pin_start + 60 s); game-bootstrap CI. |
| 9f469e7 | 2026-10-03 23:20 | v3 Amendment 4: A and B holdout scope (ESPN kickoff at or before 20:00 ET Oct 3); complete files only. |
| 04c3843 | 2026-10-03 23:45 | v3 Amendment 5: Strategy A-maker (one new variant, 21 -> 22); 4 orientation mismatches vs ESPN kept. |

## Data exclusions and fixes (counts)

- **Miami (OH) team code.** The downloader cut Kalshi team codes at the last hyphen ("M-OH" -> "OH"). Strategy A resolves market ids from the trade files instead: 13 training games kept (7 away, 6 home). The holdout has no hyphenated code (126 Kalshi events of Oct 2 to 4 checked at 5:40 PM ET). The live collector would skip a hyphenated market; 0 holdout games affected (docs/known_limitations.md).
- **LAM at UNT (cfb_20250831_lam_unt).** Excluded from Strategy A training: the UNT market's 33 trades all end 2 h 12 min before kickoff, 0 in the download window.
- **No ESPN kickoff (holdout).** 7 Kalshi events dropped and listed (v3): Lafayette at Georgetown, and 6 games involving Albany (UNH, Delaware St, Buffalo, LIU, Monmouth, Princeton). polymarket.com has 8 such events (the same 7 plus SE Louisiana at UL Monroe, which has no Kalshi game).
- **T8 kickoff errors (training, Strategy B).** 14 games with a T8 kickoff more than 15 min from ESPN fail window coverage and are excluded (v3 Amendment 1, listed there).
- **v2 Amendment 4 cutoff (lead test).** 6 of 112 candidates dropped (Saturday kickoffs 21:30 to 23:59 ET); 106 kept.
- **v3 Amendment 4 cutoff (A and B).** 5 of 773 ESPN-matched Kalshi games dropped (Saturday kickoffs 21:30 to 23:00 ET); 768 kept (98 NFL, 670 CFB).
- **Strategy B holdout match.** polymarket.com moneylines matched to <B_MATCHED> of the kept games (765 of all 773 before the cutoff; 8 Kalshi games unmatched: 6 NFL, 2 CFB).
- **Incomplete Oct 3 files.** 38 games of 2026-10-03 were downloaded while their window was open; they are refetched after their windows close (stop_and_sync step 3b) and the run checks every file was written after its window end. Refetched: <N_REFETCHED>.
- **Unsettled games.** Excluded under the existing rule: <N_UNSETTLED> at the run (76 Kalshi markets were still active at 23:25 ET).
- **No polymarket.com rows (lead test).** 3 Friday-night games have no polymarket.com rows on either machine ("no rows").

## Orientation mismatches vs ESPN (4 games, all kept; v3 Amendment 5)

Alabama A&M vs Howard (2026-08-29), Southern vs Alabama St (2026-08-29), Grambling vs Prairie View (2026-09-26, State Fair Classic): neutral-site games where Kalshi's and polymarket.com's second-listed team differs from ESPN's nominal home team; Kalshi and polymarket.com agree with each other. Dallas at Seattle (2026-08-15, NFL preseason): polymarket.com lists the teams in reverse order; the matcher set flipped = True, so both venues' P(home) refer to Seattle. None is in the lead-test holdout.

## Holdout statistic computed before the run

At Divi's request, at about 23:43 ET on 2026-10-03 (before v3 Amendment 5 was committed at 23:45), the pre-registered orientation gate was run on the holdout Strategy A inputs: PASS, n 670, median 1.0100, p5 1.0000, p95 1.0200, 0 outside [0.90, 1.10]. It is the sum of each game's two Kalshi own-market prices at decision time (an orientation check); no fill, return, win rate or lead statistic was computed. v3 Amendment 5's sentence "the holdout was not examined" refers to the A-maker design and predates this check by minutes; this note corrects it. At that time 38 Oct 3 files were still partial.

## Recorder incidents

- **Kalshi HTTP 429 on the Mac backup collector's REST trade polling**: 248 on 2026-10-03 (ET), by hour: 11:00 6, 13:00 19, 14:00 101, 15:00 75, 16:00 39, 20:00 5, 23:00 3 (out/collector.log). The collector backs off 1 s and retries; its websocket feed stayed connected; Vultr (the primary recorder) does not share this IP and is unaffected. Attributable to this project's own Kalshi requests from the Mac:
  - 20:25:37 and 20:28:25 ET (2): unthrottled Kalshi event-count queries (holdout ids only).
  - 20:54:59 to 20:56:52 ET (3): the holdout download at 4 requests/s; it paused automatically and restarted at 2 requests/s.
  - 16:00 to 16:59 ET (39): overlaps training-side Kalshi metadata requests (ingest/kalshi_market_meta.py at 4 requests/s from 16:33 ET); not separated from the collector's own load.
  - The rest (11:00 to 15:59 ET, 201; 23:28 to 23:30 ET, 3) coincide with heavy live-game polling (noon and afternoon kickoff waves) and are not attributed; the 23:28 to 23:30 ones are not from the holdout download (its Kalshi phase ended at 23:25 ET).
- **Mac backup outages longer than 60 s** (GAPS.md heartbeat rows, Oct 3 ET): 09:06 to 09:49 (several feeds, up to 880 s), 10:13 to 10:15, 11:57 to 12:41 (lid closed on battery, "Clamshell Sleep" in pmset; polymarket.com gap 2,252 s), 12:44 to 13:30 (up to 1,467 s), 14:00 to 14:18 (CPU starvation from an 8-process simulation, 972 s), 16:08 to 16:09, 16:42 to 16:47, 20:12 to 20:23 (Mac on battery since about 19:45 ET; kalshi_ws 633 s). The lead test picks Vultr first and excludes a game on a machine with any outage over 60 s in its window (v2 Amendment 3 item 10).
- **Polymarket US recorder** wrote exact-repeat rows when one side was empty; removed at read time (v2 Amendment 2 disclosure); the fix was not deployed during the holdout.

## Environment

The run uses .venv-run built from the pinned requirements.txt (pandas 2.3.2, numpy 1.26.4); final_test_run.py aborts on any other version. Under pandas 3 the book report's capital base was wrong (microsecond datetimes); fixed (report_book.py, .dt.as_unit("ns")) before the run. Re-generating results/numbers.json under the pinned venv changed 17 training values by at most 1.07e-14 (floating point); a clean clone with a fresh pinned venv reproduces all 115 training keys exactly (scripts/reproduce_training.sh).
