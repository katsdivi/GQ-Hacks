# Post-hoc Idea 6: descriptive outputs (training)

**Label: post-hoc, exploratory; designed and selected on training only.** Not variants.

## a) Clean E and skip counts

Games: 1267. Clean E (traded or eligible): 1064.

- no untied end marker: 104
- play or score after marker: 97
- missing market (KXNCAAFGAME-25AUG30LAMUNT-UNT: no rows in the trade file): 1
- team mapping: 1

## b) Time from E to the winner's first trade at >= 0.99

Games with such a trade: 802 of 1064 (none: 262). Median 11 s, p90 253 s, min 0 s, max 87584 s.

## c) Share of clean-E games with any winner trade <= 0.97 after E + D

- E + 60 s: 71 of 1064 (6.7%)
- E + 180 s: 67 of 1064 (6.3%)
- E + 600 s: 64 of 1064 (6.0%)

## d) Sanity

- D = 60 s: winner's last trade at or before E + D below 0.90: 18 games: nfl_20250808_cle_car (0.46), nfl_20250808_was_ne (0.88), nfl_20250809_ten_tb (0.53), nfl_20250809_pit_jac (0.49), nfl_20250809_dal_la (0.83), nfl_20250815_ten_atl (0.80), nfl_20250816_tb_pit (0.75), nfl_20250816_gb_ind (0.71), nfl_20250816_nyj_nyg (0.75), nfl_20250816_bal_dal (0.59), nfl_20250816_lac_la (0.41), cfb_20250906_liu_emu (0.13), cfb_20250906_txst_utsa (0.77), nfl_20250921_la_phi (0.80), cfb_20251003_wku_del (0.77), cfb_20251010_jvst_shsu (0.54), cfb_20251018_ariz_hou (0.82), nfl_20251221_pit_det (0.66)
- D = 180 s: winner's last trade at or before E + D below 0.90: 15 games: nfl_20250808_cle_car (0.49), nfl_20250808_was_ne (0.88), nfl_20250809_ten_tb (0.53), nfl_20250809_pit_jac (0.53), nfl_20250809_dal_la (0.85), nfl_20250815_ten_atl (0.75), nfl_20250816_tb_pit (0.73), nfl_20250816_nyj_nyg (0.82), nfl_20250816_bal_dal (0.67), nfl_20250816_lac_la (0.45), cfb_20250906_liu_emu (0.13), cfb_20250927_haw_afa (0.86), cfb_20251003_wku_del (0.80), cfb_20251010_jvst_shsu (0.54), cfb_20251018_ariz_hou (0.79)
- D = 600 s: winner's last trade at or before E + D below 0.90: 12 games: nfl_20250808_cle_car (0.43), nfl_20250809_ten_tb (0.66), nfl_20250809_pit_jac (0.59), nfl_20250809_dal_la (0.85), nfl_20250815_ten_atl (0.73), nfl_20250816_tb_pit (0.63), nfl_20250816_nyj_nyg (0.74), nfl_20250816_bal_dal (0.66), nfl_20250816_lac_la (0.47), cfb_20251003_wku_del (0.84), cfb_20251010_jvst_shsu (0.70), cfb_20251018_ariz_hou (0.74)

- ESPN winner at E differs from Kalshi settlement (payout of ESPN winner's market != 1): 0 games: 
- Clean-E games unsettled on Kalshi: 0
- Median time from E to Kalshi's last trade in the file (clean-E games): 166 s
