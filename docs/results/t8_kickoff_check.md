# T8 kickoff check (2026-10-03)

## Method
- T8 kickoff: `kickoff_utc` in data/raw/t8_game_plan.csv (977 games, all before 2026-08-01).
- ESPN kickoff: `espn_kickoff` imported from ingest/kalshi_only_train.py (ESPN scoreboards, date +-1 day, both teams matched by name/code, score >= 1.6). Cached boards under data/raw/espn/. Script: scratchpad kocheck.py (not in repo).
- Cross-check: kickoff_utc_espn in data/raw/kalshi_only_games.csv agrees for all 331 games present (0 mismatches).
- diff_min = T8 kickoff minus ESPN kickoff, in minutes.
- T8 download window: ingest/download_all.py line 53 `PRE, POST = 2h, 5h`, used at lines 313 and 359 as [kick - PRE, kick + POST].
- Coverage rule: covered iff T8ko - 2h <= ESPNko - 30min AND T8ko + 5h >= ESPNko + 4.5h. Secondary check for |diff| > 15 only: first and last ts of data/ticks/<game_id>_polymarket.parquet (ts column only), in minutes relative to ESPN kickoff.

## Counts
- ESPN matched: 977 of 977. No ESPN match: 0.
- |diff| > 15 min: 14 (all 14 fail the coverage rule).
- |diff| > 1 min: 26 (12 of these are between 1 and 15 min).

## Games with |diff| > 15 min
| game_id | T8 kickoff (UTC) | ESPN kickoff (UTC) | diff_min | covered | PM first/last ts vs ESPN ko (min) |
|---|---|---|---|---|---|
| cfb_20251129_ore_wash | 2025-11-29 05:00 | 2025-11-29 20:30 | -930 | n | -1037/-642 |
| cfb_20251129_cin_tcu | 2025-11-29 05:00 | 2025-11-29 20:30 | -930 | n | -1025/-633 |
| cfb_20251129_hou_bay | 2025-11-29 05:00 | 2025-11-29 17:00 | -720 | n | -831/-457 |
| cfb_20251129_colo_ksu | 2025-11-29 05:00 | 2025-11-29 17:00 | -720 | n | -815/-424 |
| nfl_20251208_phi_lac | 2025-12-08 20:15 | 2025-12-09 01:15 | -300 | n | -419/-0 |
| nfl_20251225_det_min | 2025-12-25 16:30 | 2025-12-25 21:30 | -300 | n | -419/-0 |
| nfl_20251225_den_kc | 2025-12-25 20:15 | 2025-12-26 01:15 | -300 | n | -420/-0 |
| cfb_20250913_usc_pur | 2025-09-13 19:30 | 2025-09-13 22:45 | -195 | n | -312/100 |
| cfb_20251129_ucla_usc | 2025-11-29 21:30 | 2025-11-30 00:30 | -180 | n | -295/119 |
| cfb_20250913_fau_fiu | 2025-09-13 22:00 | 2025-09-14 00:30 | -150 | n | -246/148 |
| cfb_20251018_txam_ark | 2025-10-18 19:30 | 2025-10-18 21:30 | -120 | n | -238/180 |
| cfb_20250920_tem_gt | 2025-09-20 20:30 | 2025-09-20 21:05 | -35 | n | -144/164 |
| cfb_20251018_utsa_unt | 2025-10-18 19:30 | 2025-10-18 20:05 | -35 | n | -144/254 |
| cfb_20250913_ull_mizz | 2025-09-13 20:00 | 2025-09-13 17:00 | 180 | n | 61/400 |

## No ESPN match
None.

Metadata only: no prices, trade values or results were examined.
