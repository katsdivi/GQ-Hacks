exploratory, post-run, partial: before 17:00 ET Oct 3

h3 rule (fixed before computing): for each T&S trade in a game's laggard window (home price p, venue time tv), take the last recorded snapshot with ts <= tv (old book). Classify p against old best bid and old best ask with |difference| <= 1e-9. If p equals exactly one of them, that is the side. Scan the recorded snapshots with ts > tv and ts - tv <= 30 s in time order; the delay is ts of the FIRST snapshot whose value on that side differs from the old value (NaN vs a number counts as a change, NaN vs NaN does not) minus tv. Excluded as ambiguous, by reason: no_old_book (no snapshot with ts <= tv), matches_both, matches_neither, no_change_30s.

| stat | value |
|---|---|
| n_trades_in_windows | 152692.0 |
| n_matched | 30181.0 |
| n_ambiguous | 122511.0 |
| n_matches_neither | 79233.0 |
| n_no_change_30s | 41555.0 |
| n_no_old_book | 1723.0 |
| delay_median_s | 19.227186402 |
| delay_p10_s | 5.290451534 |
| delay_p90_s | 28.192414553 |
| delay_mean_s | 17.923144013414333 |
| n_matched_bid_side | 14877.0 |
| n_matched_ask_side | 15304.0 |
| share_delay_le_1s | 0.016003445876544845 |
| share_delay_le_2s | 0.03174182432656307 |

| game_id | n_matched | median_s | n_ambiguous |
|---|---|---|---|
| cfb_20261003_ala_msst | 3414 | 20.2473417385 | 14123 |
| cfb_20261003_alcn_gram | 163 | 18.238177354 | 428 |
| cfb_20261003_aub_tenn | 1270 | 20.324235383999998 | 4504 |
| cfb_20261003_bc_smu | 1667 | 19.035333079 | 3969 |
| cfb_20261003_brwn_uri | 366 | 16.184336534 | 1470 |
| cfb_20261003_cal_unlv | 527 | 18.772639676 | 2010 |
| cfb_20261003_cit_scst | 366 | 19.0119377745 | 1553 |
| cfb_20261003_cor_gtwn | 180 | 16.6953451625 | 522 |
| cfb_20261003_day_drke | 262 | 17.885940543 | 1104 |
| cfb_20261003_dsu_alby | 50 | 19.3246839185 | 152 |
| cfb_20261003_elon_unh | 470 | 19.6846007265 | 2410 |
| cfb_20261003_fla_mizz | 1505 | 19.897841905 | 6606 |
| cfb_20261003_hc_wm | 114 | 18.692147464999998 | 428 |
| cfb_20261003_how_hamp | 147 | 16.915211882 | 436 |
| cfb_20261003_lou_ncst | 723 | 18.339301682 | 2734 |
| cfb_20261003_md_neb | 333 | 18.612271481 | 869 |
| cfb_20261003_mhu_liu | 428 | 17.761971305499998 | 1263 |
| cfb_20261003_mich_minn | 4127 | 19.940044588 | 17909 |
| cfb_20261003_morg_vill | 627 | 18.611684978 | 4102 |
| cfb_20261003_mrmk_yale | 421 | 18.420295633 | 1524 |
| cfb_20261003_mrsh_jmu | 176 | 18.04738826 | 570 |
| cfb_20261003_mrst_stet | 166 | 18.617177396499997 | 522 |
| cfb_20261003_navy_afa | 1253 | 19.895807832 | 4898 |
| cfb_20261003_norf_rmu | 157 | 19.817465254 | 501 |
| cfb_20261003_penn_dart | 170 | 16.275623235 | 833 |
| cfb_20261003_prin_clmb | 380 | 14.6970216195 | 1163 |
| cfb_20261003_pur_ill | 92 | 17.24078997 | 452 |
| cfb_20261003_rich_laf | 444 | 16.085125337 | 1625 |
| cfb_20261003_shu_me | 65 | 16.707864392 | 191 |
| cfb_20261003_syr_conn | 490 | 18.870623474 | 2256 |
| cfb_20261003_tol_ball | 688 | 17.694772878 | 2992 |
| cfb_20261003_tows_monm | 293 | 17.590957661 | 989 |
| cfb_20261003_ucf_hou | 2934 | 18.344395819 | 9406 |
| cfb_20261003_uk_scar | 487 | 19.297994742 | 2174 |
| cfb_20261003_ust_pre | 697 | 19.382327376 | 3469 |
| cfb_20261003_uva_fsu | 1038 | 19.329038750000002 | 4114 |
| cfb_20261003_wmu_buff | 1032 | 19.208771463 | 5131 |
| cfb_20261003_wof_fur | 280 | 16.253224826 | 641 |
| cfb_20261003_wvu_isu | 2179 | 20.43817262 | 12468 |
