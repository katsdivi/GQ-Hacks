# HYPOTHESIS_v4 maker on truncated late Oct 3 games (descriptive, truncated recordings, outside HYPOTHESIS_v4 rule; not test set 1)

Committed maker code scripts/posthoc_mm_v4.py (1d3d68a), one run, unedited. Recordings end about 00:34 ET Oct 4,
so these games are cut mid-play; this is NOT test set 1 and is not evidence for or against HYPOTHESIS_v4.
No synthetic data mixed in. Settlement only from data/holdout_raw/settlements.csv (no API calls).

## Totals

| arm | games | fills | contracts | pnl60_usd | pnl60_c_per_contract | fills_mark_after_cutoff | pnlset_usd_settled_games_only |
|---|---|---|---|---|---|---|---|
| A | 6 | 34 | 340 | 2.76 | 0.8118 | 0 | -12.2 |
| B | 6 | 7 | 70 | 2.45 | 3.5 | 0 | -3.4 |

## Per game

| game | arm | kickoff_et | recording_end_et | ingame_recorded_min | share_game_covered | trades_in_recording | fills | contracts | fills_mark_after_cutoff | pnl60_usd | pnl60_c_per_contract | settled | pnlset_usd |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cfb_20261004_fres_wsu | A | 21:30 | 00:34 | 164.4 | 0.878 | 427 | 15 | 150 | 0 | -0.2 | -0.1333 | True | -12.2 |
| cfb_20261004_fres_wsu | B | 21:30 | 00:34 | 164.4 | 0.878 | 427 | 2 | 20 | 0 | 0.7 | 3.5 | True | -3.4 |
| cfb_20261004_bay_asu | A | 22:30 | 00:34 | 104.4 | 0.592 | 280 | 3 | 30 | 0 | 0.85 | 2.833 | False | nan |
| cfb_20261004_bay_asu | B | 22:30 | 00:34 | 104.4 | 0.592 | 280 | 1 | 10 | 0 | 0.55 | 5.5 | False | nan |
| cfb_20261004_ewu_ucd | A | 22:30 | 00:34 | 104.4 | 0.592 | 20 | 0 | 0 | 0 | 0 | nan | False | nan |
| cfb_20261004_ewu_ucd | B | 22:30 | 00:34 | 104.4 | 0.592 | 20 | 0 | 0 | 0 | 0 | nan | False | nan |
| cfb_20261004_txst_sdsu | A | 22:30 | 00:34 | 104.3 | 0.592 | 117 | 6 | 60 | 0 | 1.01 | 1.683 | False | nan |
| cfb_20261004_txst_sdsu | B | 22:30 | 00:34 | 104.3 | 0.592 | 117 | 1 | 10 | 0 | 0.45 | 4.5 | False | nan |
| cfb_20261004_cin_ariz | A | 23:00 | 00:34 | 74.4 | 0.45 | 214 | 5 | 50 | 0 | 0.75 | 1.5 | False | nan |
| cfb_20261004_cin_ariz | B | 23:00 | 00:34 | 74.4 | 0.45 | 214 | 3 | 30 | 0 | 0.75 | 2.5 | False | nan |
| cfb_20261004_sjsu_haw | A | 23:59 | 00:34 | 15.4 | 0.169 | 67 | 5 | 50 | 0 | 0.35 | 0.7 | False | nan |
| cfb_20261004_sjsu_haw | B | 23:59 | 00:34 | 15.4 | 0.169 | 67 | 0 | 0 | 0 | 0 | nan | False | nan |
