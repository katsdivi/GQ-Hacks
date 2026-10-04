# N maker on polymarket.com: inventory, round trips, spread and phase, top games

**Label: descriptive, post-hoc, not pre-registered, one day.** From the cached N fills of b346230 (verified 428 fills, +60 s $46.53). Books re-read from the same local Vultr files with the committed loader.
Phase split: ESPN halftime is not available in local holdout data, so the game window (kickoff + 20 min to the game's last Kalshi home-market trade in the window) is split at its midpoint; fills before kickoff are 'pre-game'. Quoted spread = polymarket.com ask minus bid just before the fill. Time at cap is time-weighted over the quoting window, excluding the kickoff cut.

## (1) Inventory

- games with fills: 59 of 88
- max absolute inventory per game: median 20, max 50 contracts
- games that ever reached the +/- 50 cap: 14
- time-weighted share of the quoting window at the cap: median 0.000, mean 0.030, max 0.427

## (2) FIFO round trips

- matched round-trip contracts: 1530, realized P&L $7.99 (0.52 c per matched contract)
- unmatched inventory at the end: net +620 contracts summed over games (gross 1220), settlement P&L $106.04
- check: round trips + unmatched at settlement = $114.03 vs held-to-settlement P&L $114.03

## (3) P&L per contract by quoted spread and by phase

| bucket | fills | contracts | pnl60 | pnlset | pnl60_c_per_contract | pnlset_c_per_contract |
|---|---|---|---|---|---|---|
| 1c | 154 | 1540 | -9.49 | 38.46 | -0.6162 | 2.497 |
| 2c | 68 | 680 | 3.78 | 46.71 | 0.5559 | 6.869 |
| 3c+ | 195 | 1950 | 53.24 | 27.94 | 2.73 | 1.433 |
| unknown | 11 | 110 | -1 | 0.92 | -0.9091 | 0.8364 |

| phase | fills | contracts | pnl60 | pnlset | pnl60_c_per_contract | pnlset_c_per_contract |
|---|---|---|---|---|---|---|
| first half | 113 | 1130 | 13.81 | 9.48 | 1.222 | 0.8389 |
| pre-game | 1 | 10 | 0.045 | -0.23 | 0.45 | -2.3 |
| second half | 314 | 3140 | 32.67 | 104.8 | 1.041 | 3.337 |

## (4) Top 5 games by +60 s P&L

| game | fills | contracts | median_spread_c | max_abs_inv | share_time_at_cap | pnl60 | pnlset | pre_game_home_mid | home_payout | largest_late_10min_move_c | final_score |
|---|---|---|---|---|---|---|---|---|---|---|---|
| cfb_20261003_colg_harv | 11 | 110 | 7 | 50 | 0.2082 | 14.75 | 17 | 0.635 | 1 | 87 | Harvard Crimson 7 - Colgate Raiders 7 (STATUS_IN_PROGRESS) |
| cfb_20261003_wmu_buff | 27 | 270 | 2 | 50 | 0.03405 | 9.35 | -13.9 | 0.175 | 0 | 72.4 | Buffalo Bulls 17 - Western Michigan Broncos 20 (STATUS_FINAL) |
| cfb_20261003_uk_scar | 41 | 410 | 2 | 50 | 0.1708 | 8.9 | 26.1 | 0.555 | 0 | 60.5 | South Carolina Gamecocks 34 - Kentucky Wildcats 35 (STATUS_FINAL) |
| cfb_20261003_aub_tenn | 13 | 130 | 2 | 40 | 0 | 5.25 | -2.1 | 0.675 | 1 | 21 | Tennessee Volunteers 24 - Auburn Tigers 14 (STATUS_FINAL) |
| cfb_20261003_wvu_isu | 23 | 230 | 3 | 50 | 0.2033 | 3.5 | 6.6 | 0.585 | 1 | 32.5 | Iowa State Cyclones 45 - West Virginia Mountaineers 42 (STATUS_FINAL) |

- cfb_20261003_colg_harv: pre-game home mid 0.64, home settled 1; late swing (87 c in 10 min in the second half); score: Harvard Crimson 7 - Colgate Raiders 7 (STATUS_IN_PROGRESS).
- cfb_20261003_wmu_buff: pre-game home mid 0.17, home settled 0; late swing (72 c in 10 min in the second half); score: Buffalo Bulls 17 - Western Michigan Broncos 20 (STATUS_FINAL).
- cfb_20261003_uk_scar: pre-game home mid 0.56, home settled 0; upset (pre-game favourite lost); late swing (60 c in 10 min in the second half); score: South Carolina Gamecocks 34 - Kentucky Wildcats 35 (STATUS_FINAL).
- cfb_20261003_aub_tenn: pre-game home mid 0.68, home settled 1; late swing (21 c in 10 min in the second half); score: Tennessee Volunteers 24 - Auburn Tigers 14 (STATUS_FINAL).
- cfb_20261003_wvu_isu: pre-game home mid 0.58, home settled 1; late swing (32 c in 10 min in the second half); score: Iowa State Cyclones 45 - West Virginia Mountaineers 42 (STATUS_FINAL).

Notes: the top 5 games hold $41.75 of the $46.53 +60 s P&L. The Colgate-Harvard score is from an ESPN scoreboard file
saved while the game was in progress, so it is not the final score (Kalshi settled home = 1). 11 fills had no book
side just before the fill (spread bucket "unknown"). Pre-game: only 1 fill, since quoting stops in the kickoff cut and
the windows start shortly before kickoff.
