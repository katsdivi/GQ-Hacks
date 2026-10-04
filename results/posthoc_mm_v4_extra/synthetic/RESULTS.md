# Synthetic simulation results (SYNTHETIC SIMULATION, calibrated to one day of observed data; not market evidence; not a test of HYPOTHESIS_v4)

Spec 4c7da20. One run. P&L in cents per contract (total P&L / total contracts); CI = game bootstrap, 2,000 reps, seed 20261011. Observed day for comparison (N maker, 88 real games, 863eb69): +1.09 c [0.17, 2.12] at +60 s.

| scenario | arm | games | fills | contracts | pnl60_c_pc | pnl60_lo | pnl60_hi | pnlset_c_pc | pnlset_lo | pnlset_hi | share_games_pos60_traded |
|---|---|---|---|---|---|---|---|---|---|---|---|
| base | A | 500 | 3503 | 3.5e+04 | 1.01 | 0.916 | 1.11 | 1.29 | -0.164 | 2.7 | 0.816 |
| base | B | 500 | 1137 | 1.14e+04 | 2.68 | 2.52 | 2.86 | 5.17 | 2.43 | 7.72 | 0.898 |
| informed_0.5x | A | 200 | 1418 | 1.42e+04 | 1.07 | 0.898 | 1.23 | 0.18 | -2.12 | 2.57 | 0.83 |
| informed_0.5x | B | 200 | 447 | 4.47e+03 | 2.93 | 2.7 | 3.14 | 0.933 | -3.44 | 4.99 | 0.949 |
| informed_2x | A | 200 | 1466 | 1.47e+04 | 0.696 | 0.546 | 0.846 | 0.744 | -1.32 | 2.82 | 0.734 |
| informed_2x | B | 200 | 466 | 4.66e+03 | 2.43 | 2.2 | 2.67 | 4.16 | 0.229 | 8.27 | 0.94 |
| jumps_0.5x | A | 200 | 1413 | 1.41e+04 | 0.983 | 0.848 | 1.12 | 0.325 | -1.56 | 2.26 | 0.835 |
| jumps_0.5x | B | 200 | 438 | 4.38e+03 | 2.64 | 2.37 | 2.93 | 2.16 | -1.45 | 5.81 | 0.954 |
| jumps_2x | A | 200 | 1400 | 1.4e+04 | 1.01 | 0.836 | 1.18 | 1.81 | -0.307 | 4.07 | 0.789 |
| jumps_2x | B | 200 | 456 | 4.56e+03 | 2.62 | 2.32 | 2.93 | 2.62 | -1.12 | 6.28 | 0.894 |
| spread_narrow_1c | A | 200 | 1326 | 1.33e+04 | 0.102 | -0.0282 | 0.225 | 1.41 | -1.05 | 3.81 | 0.62 |
| spread_narrow_1c | B | 200 | 0 | 0 | nan | nan | nan | nan | nan | nan | nan |
| spread_wide_plus2c | A | 200 | 1401 | 1.4e+04 | 1.95 | 1.78 | 2.13 | 3.08 | 0.707 | 5.39 | 0.955 |
| spread_wide_plus2c | B | 200 | 1401 | 1.4e+04 | 1.95 | 1.78 | 2.13 | 3.08 | 0.707 | 5.39 | 0.955 |
