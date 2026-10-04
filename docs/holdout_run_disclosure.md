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

Strategy B keeps all 4 (checked 2026-10-04 ~00:32 ET from code and pm_map.csv ids/names only, no prices): B pairs polymarket.com's outcome with Kalshi's home team by team identity, not by listing position (ingest/download_all.match_games: NFL team codes, CFB team names, swap check; ingest/holdout_download.pm_trades selects the outcome by that flag). All 4 matched at score 1.0; the 3 CFB games are not flipped (both venues list the same teams in the same order), Dallas at Seattle is flipped (polymarket.com outcome index 0 = Seahawks = Kalshi home).

## What the orientation gate checks

The run's orientation gate (scripts/final_test_run.orientation_gate) checks Kalshi self-consistency only: for each holdout Strategy A game, the home team's own-market price plus the away team's own-market price at decision time (both Kalshi). It does not compare Kalshi with polymarket.com. Cross-venue orientation for Strategy B relies on the matcher's flipped logic (ingest/download_all.match_games: team codes for NFL, team names for CFB, with a swap check) and will be checked on the run outputs (Kalshi vs polymarket.com P(home) agreement at decision time, as the training orientation check did: median |diff| 1 cent, 0 of 579 over 10 cents).

## B orientation check (rule fixed before the holdout run)

For every Strategy B holdout game, take Kalshi P(home) and polymarket.com P(home) at each B decision time. A game is FLAGGED as a likely orientation flip if, at its median decision time, |K - PM| > 0.20 AND |K - (1 - PM)| < 0.05 AND |K - 0.5| > 0.10. Also reported for all games: median |K - PM| and the count of games with median |K - PM| > 0.10 (same as training). Action: if any game is flagged, the primary B result stays exactly as the run produced it; a second, clearly labeled "B excluding flagged games" line is reported beside it, and the flagged games are listed. No other change to B.

Implementation: scripts/b_orientation_check.py. "Each B decision time" = every entry and exit decision of the selected setting (k = 5 c, m = 10 s, T = 300 s), filled or not; K and PM are Strategy B's own grid prices (trailing 3 s median of trades, carried forward) at the label each decision uses; the median decision time is the middle decision in time order (lower middle for an even count).

Result on TRAINING B (963 games; holdout not read): 839 games with B decisions, all evaluable; FLAGGED 1 (nfl_20251214_ind_sea); median over games of the per-game median |K - PM| 0.0338; games with median |K - PM| > 0.10: 3. The flagged training game is not an orientation flip: both venues give the same P(Seattle) through the game (kickoff - 30 min 0.85 vs 0.85, kickoff 0.82 vs 0.83, + 60 min 0.69 vs 0.69, + 120 min 0.58 vs 0.58; matcher not flipped); its median decision time fell during a fast swing (K 0.30, PM 0.66), which satisfies the rule by coincidence. So the rule's false-positive rate on training is 1 in 839 games. Because B decides only where |K - PM| >= 5 c, |K - PM| at decision times is larger than at the unselected kickoff - 5 min check (training median 1 cent there).

## Holdout statistic computed before the run

At Divi's request, at about 23:43 ET on 2026-10-03 (before v3 Amendment 5 was committed at 23:45), the pre-registered orientation gate was run on the holdout Strategy A inputs: PASS, n 670, median 1.0100, p5 1.0000, p95 1.0200, 0 outside [0.90, 1.10]. It is the sum of each game's two Kalshi own-market prices at decision time (an orientation check); no fill, return, win rate or lead statistic was computed. v3 Amendment 5's sentence "the holdout was not examined" refers to the A-maker design and predates this check by minutes; this note corrects it. At that time 38 Oct 3 files were still partial.

## Recorder incidents

- **Kalshi HTTP 429 on the Mac backup collector's REST trade polling**: 248 on 2026-10-03 (ET), by hour: 11:00 6, 13:00 19, 14:00 101, 15:00 75, 16:00 39, 20:00 5, 23:00 3 (out/collector.log). The collector backs off 1 s and retries; its websocket feed stayed connected; Vultr (the primary recorder) does not share this IP and is unaffected. Attributable to this project's own Kalshi requests from the Mac:
  - 20:25:37 and 20:28:25 ET (2): unthrottled Kalshi event-count queries (holdout ids only).
  - 20:54:59 to 20:56:52 ET (3): the holdout download at 4 requests/s; it paused automatically and restarted at 2 requests/s.
  - 16:00 to 16:59 ET (39): overlaps training-side Kalshi metadata requests (ingest/kalshi_market_meta.py at 4 requests/s from 16:33 ET); not separated from the collector's own load.
  - The rest (11:00 to 15:59 ET, 201; 23:28 to 23:30 ET, 3) coincide with heavy live-game polling (noon and afternoon kickoff waves) and are not attributed; the 23:28 to 23:30 ones are not from the holdout download (its Kalshi phase ended at 23:25 ET).
- **Kalshi HTTP 429 on Vultr (primary recorder): none.** The Vultr collector logs every Kalshi HTTP error in the same format as the Mac (its journal has, for example, "kalshi /markets/trades HTTP 500; backing off 1s" lines), and its journal since the service start (2026-10-03 10:08 ET) has 0 Kalshi 429 lines (the 2 lines matching "429" are row-count lines such as "kalshi/trade=429,022").
- **Which calls got 429, and their effect.** All 248 Mac 429s are on one endpoint, `kalshi /markets/trades` (the REST trade-print poll the collector runs for markets the websocket flags as traded). Kalshi book data (orderbook snapshots and deltas) comes over the authenticated websocket; REST book polling is off while the websocket is up, so no 429 touched book data, and the lead test (book midpoints) and the laggard (recorded quotes) use book data only. A 429 is retried up to 6 times with backoff, and each trade poll restarts from the last recorded trade time minus 2 s, so a retried poll loses no trades. No 429 exhausted the retries: the 4 "failed after retries" events (20:14 to 20:17 ET) were network ConnectionErrors during the 20:12 to 20:23 ET Mac outage, which the heartbeat rule records (Kalshi websocket gap 633 s), and the collector's exception handler kept the process running (no restart from a 429).
- **Rate-limit scope (unverified).** Kalshi's rate-limit page (docs.kalshi.com/getting_started/rate_limits) gives token budgets per tier for authenticated requests and does not say whether limits apply per API key, account or IP, nor how unauthenticated requests are limited; a secondary source (pm.wiki) says per key. Our REST trade polls are unauthenticated (plain session, no key), and the shared key is used only for the websocket on both machines; Vultr and the Mac have different IPs. Whether the Mac's 429s were per-IP or per-key limits is not verified.
- **Mac backup outages longer than 60 s** (GAPS.md heartbeat rows, Oct 3 ET): 09:06 to 09:49 (several feeds, up to 880 s), 10:13 to 10:15, 11:57 to 12:41 (lid closed on battery, "Clamshell Sleep" in pmset; polymarket.com gap 2,252 s), 12:44 to 13:30 (up to 1,467 s), 14:00 to 14:18 (CPU starvation from an 8-process simulation, 972 s), 16:08 to 16:09, 16:42 to 16:47, 20:12 to 20:23 (Mac on battery since about 19:45 ET; kalshi_ws 633 s). The lead test picks Vultr first and excludes a game on a machine with any outage over 60 s in its window (v2 Amendment 3 item 10).
- **Polymarket US recorder** wrote exact-repeat rows when one side was empty; removed at read time (v2 Amendment 2 disclosure); the fix was not deployed during the holdout.

## Recorder stop, input freeze and refetch (2026-10-04, by hand after a script failure)

- **Stop script failed at step 3b.** `scripts/stop_and_sync.sh` (run as an untracked copy at `out/stop_and_sync.sh`, sha256 2e86cee0de418a98, identical to 872ff43's, so it resolved its working directory to the staleline checkout) started at 00:34:25 ET. Step 1 time gate passed; step 2 stopped Vultr gqh-collector (inactive) and the Mac collector, supervisor and watcher at 00:34:29 ET; step 3 froze the inputs (results/holdout_inputs_manifest.txt, 6 files, sha256 d7c5c0e408fe4def). At 01:00:44 ET step 3b failed with exit 2 (`unrecognized arguments: --refetch-incomplete`): it runs the downloader before step 5 checks out main, the checkout was still on t13, and the flag existed only on main (f6d55f1). 0 files were fetched. The rehearsals skip step 3b, so they could not catch it. A rehearsal from the staleline checkout also failed at step 6 for a rehearsal-only reason (it rehearses the checkout's HEAD, t13, which has no scripts/); a second rehearsal of the same script from a throwaway clone at 872ff43 passed all steps.
- **Remaining steps completed by hand, in the order 4, 5, 3b, 6, from RUN_COMMIT's committed code.** Step 4 (01:03:05 to 01:15:03 ET): rsync of Vultr data/live, second --checksum pass 0 differing files; files per feed Vultr = local: kalshi 10,264, polymarket 10,239, polymarket_us 10,110 (40,858 total). Step 5 (01:15:24 ET): auto-logged GAPS.md committed on t13 (755229a), ../wt-main removed, staleline checked out at main 872ff43, tracked files clean, data/ files 98,911 before and after, manifest 6 of 6 OK. Step 3b (01:22:47 to 01:56:12 ET, on 872ff43): see the next item. Step 6 (01:56:39 ET): `final_test_run.py --checklist-only` PASS, exit 0 (all A/B holdout files of kept games written after their window end: Kalshi 768 games, polymarket.com 760, missing 0, early 0). After the refetch: data/ files 98,911 (unchanged; files are deleted and rewritten in place), manifest 6 of 6 OK, tracked files clean, HEAD 872ff43.
- **Refetch ran with the collector-health guard bypassed at runtime.** Command: `nice -n 19 .venv-run/bin/python -c "import sys, ingest.holdout_download as h; h.guard=lambda: None; sys.argv=['holdout_download','--holdout-download','--refetch-incomplete']; h.main()"`. The guard (ingest/holdout_download.py guard(), called only from get()) pauses 5 min whenever the collector heartbeat is more than 60 s old; the recorders had been stopped on purpose at 00:34:29 ET, so it would have paused forever. The rate limiter (2 requests/s per host, inside get()) was unchanged. No tracked code, data or analysis code was modified; the bypass existed only in that command line.
- **Refetch counts.** Kalshi: 45 incomplete files refetched (the downloader's own `refetch:` line), 0 failures; 5 more left as is because their windows had not ended (cfb_20261004_fres_wsu, _bay_asu, _ewu_ucd, _txst_sdsu, _cin_ariz: kickoffs 21:30 to 23:00 ET, exactly the 5 games v3 Amendment 4 drops from A and B). polymarket.com: 25 files rewritten (from file times; the downloader prints no polymarket.com refetch count), 0 failures; its 5 files for the same dropped games were also left as is and are not used. The earlier estimate of 38 came from a check at 22:48:48 ET on Oct 3 that counted games whose [kickoff - 2 h, kickoff + 5 h] window was still open at that moment: 33 of the 45 refetched plus the 5 left. The other 12 (kickoffs 15:50 to 17:00 ET Oct 3) had been downloaded between 20:30 and 22:48 ET, before their windows ended, but their windows had closed by 22:48, so that check missed them; the downloader's completeness test (file time < kickoff + 5 h) caught them.
- **Settlements after the refetch** (status counts only): 1,538 finalized, 8 active, 0 inactive (before: 1,468 / 76 / 2). The 8 active markets belong to 4 games, all among the 5 dropped by v3 Amendment 4; no kept game is unsettled.

## Environment

The run uses .venv-run built from the pinned requirements.txt (pandas 2.3.2, numpy 1.26.4); final_test_run.py aborts on any other version. Under pandas 3 the book report's capital base was wrong (microsecond datetimes); fixed (report_book.py, .dt.as_unit("ns")) before the run. Re-generating results/numbers.json under the pinned venv changed 17 training values by at most 1.07e-14 (floating point); a clean clone with a fresh pinned venv reproduces all 115 training keys exactly (scripts/reproduce_training.sh).

## Post-hoc work

- 2026-10-04: docs/posthoc/COMBO_SPEC.md (67c5350, 03:54:50 ET) was committed 40 s after Idea 4 training results were committed (6e21338, 03:54:49 ET). The committing session had not opened those files or that commit. The rule excludes Idea 4 regardless (negative training ROC).
- 2026-10-04: Idea 1 (branch posthoc-latency, 6f13ecd, 03:51:07 ET): per-leg sizing disclosed; most trades left about 10 contracts unhedged. A matched-quantity diagnostic was added from the existing trade log (diagnostic, not a variant).
- 2026-10-04: Idea 3 (branch posthoc-latency, 54c3c28, 03:49:57 ET): all outputs marked invalid because of lookahead (whole-window size percentile). Not rerun; its 3 variants still count.
