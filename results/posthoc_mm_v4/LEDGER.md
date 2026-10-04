# posthoc-mm-v4 ledger (HYPOTHESIS_v4, main 94aa1a0)

| ET time | entry |
|---|---|
| 2026-10-04 07:56 | HYPOTHESIS_v4.md committed alone on main (94aa1a0), before any test data was opened. |
| 2026-10-04 07:58 ET | Test set 1 (Oct 3 games kicking off after 20:00 ET, complete polymarket.com books and trades): 0 eligible games, NOT run. Candidates from data/live/holdout_candidates.csv: cfb_20261004_fres_wsu (21:30 ET), bay_asu, ewu_ucd, txst_sdsu (22:30), cin_ariz (23:00), sjsu_haw (23:59). All have books and trades on Vultr and Mac (max in-game gap 2.0 min) but every recording ends at 00:34 ET Oct 4 (recorder stop), before these games end, so none spans kickoff - 2 h to the last trade or settlement (completeness rule). None is in the posthoc-mm-signal game set (its 88 games kick off at or before 20:00 ET; none appears in n_detail_games.csv). Label: v4 test set 1, descriptive, n small (n = 0). |
| 2026-10-04 07:58 ET | Arm B parameter (min_spread, quote only while best ask - best bid >= 3 c) added to scripts/posthoc_mm_v4.py, a copy of posthoc-mm-signal scripts/posthoc_mm_signal.py at 38da93d with nothing else changed; 3 new synthetic tests plus the 5 copied base tests pass (8 passed). Ready for test set 2 (Oct 8 to 12). |
