# Post-hoc cost-side price patterns: RESULTS (training only, exploratory)

Spec: SPEC.md (commit b8f2521, 2026-10-04 05:36 ET, before any trade file was read) plus Amendment 1 (P1 reference
moved to kickoff-105min because trade files start at about kickoff-2h; chosen from file coverage, not results).
57 trials, 19 test weeks (2025-09-08 to 2026-01-12), 1,024 test games of 1,266 usable. 10 contracts, +1 c fill after
a 1 s latency, Kalshi taker fee on every trade, hold to settlement. Bootstrap: 2,000 game resamples, seed 20261004.

## Verdict
No mechanism produces a result that survives its costs. Of 57 trials, none has a 95% CI lower bound clearly above 0
once sample size is considered: the only CIs that exclude 0 on the upside (P3-08, P5-03) are 6 and 11 trades where
every trade won (the bootstrap interval collapses), so they are not evidence. With 57 trials about 2.9 would show a
CI excluding 0 by chance. Across cells with >= 30 trades the best ROC is 0.090 (P4-01, 34 trades, CI [-0.072, 0.234]); the best
cell with over 100 trades is P3-04 (favourites 0.80-0.90 at kickoff-5min, 153 trades, ROC 0.032, CI [-0.030, 0.086],
+2.7 c/contract), which fades in other phases and in the NFL slice (0.002). Win rate stays at or within about 3 points of mean fill in nearly every cell, so the
costs (+1 c and fee, roughly 2 to 2.5 c/contract) remove any thin edge. The 0.70-0.80 band is negative
everywhere (CFB at kickoff+120min is significantly negative: -0.135, CI [-0.258, -0.021]), the opposite of a
favourite underpricing story.

- P1 pre-game drift: too few trades (pre-game markets are thin; 29 trades at d=3, 4 at d=5). Momentum and reversal
  are both indistinguishable from zero or negative. Not testable at 5.5 h.
- P2: skipped (no lookahead-free form; see SPEC).
- P3 longshot bias: no consistent band or phase; signs flip across phases.
- P4 slate correlation: 5-hour settlement lag leaves 6 to 34 trades per cell. K>=1, 0.70-0.80 shows +0.090
  (CI [-0.072, 0.234]), not significant, and the other bands are negative.
- P5 low-volume slots: small samples (11 to 42), CIs all include 0 (P5-03 is 11 all-win trades).
- Walk-forward selection (W-P1, W-P3, W-P5) loses (W-P3 ROC -0.085, CI [-0.180, 0.001]), so past-week winners
  do not carry forward.

## Lookahead avoided
- Prices are last trade with ts <= t (searchsorted right-1); unit test shows rows after t change nothing.
- Fills require ts >= t + 1.0 s (test at t+1s-1ns versus t+1s) within 5 min.
- P1 reference time is earlier than the decision time; the kickoff-2h comparison in P2 was refused as lookahead.
- P4 counts an upset only if kickoff + 5 h <= decision time; payouts of unsettled games are never read.
- P5 slot terciles and trailing volume use only weeks strictly before the game's week.
- Walk-forward selection uses only weeks strictly before the test week.
Caveats: favourite classification uses last-trade prices (no order book); NFL preseason is included; the 5 h
settlement lag is an assumption (long games could be unknown in reality); the 6 history weeks are excluded from metrics.

## Ranked table (by CI lower bound; n < 30 rows are not reliable)
| trial | params | trades | ROC | 95% CI | net c/contract | win vs fill | Sharpe x365 | max DD $ | ROC ex top-5 |
|---|---|---|---|---|---|---|---|---|---|
| P1-11 | d=5c mode=rev league=NFL | 1 | 1.008 | [1.008, 1.008] | 50.20 | 1.000 vs 0.480 | n/a | 0.0 | n/a |
| P3-08 | time=ko-5m band=0.90-0.95 league=NFL | 6 | 0.086 | [0.078, 0.092] | 7.92 | 1.000 vs 0.915 | 188.81 | 0.0 | 0.070 |
| P5-03 | time=ko-5m band=0.90-0.95 league=ALL | 11 | 0.062 | [0.052, 0.072] | 5.82 | 1.000 vs 0.937 | 35.43 | 0.0 | 0.049 |
| P3-06 | time=ko-5m band=0.80-0.90 league=CFB | 116 | 0.042 | [-0.026, 0.102] | 3.57 | 0.897 vs 0.852 | 4.01 | 25.3 | 0.034 |
| P3-04 | time=ko-5m band=0.80-0.90 league=ALL | 153 | 0.032 | [-0.030, 0.086] | 2.75 | 0.889 vs 0.852 | 2.64 | 26.8 | 0.026 |
| P3-16 | time=ko+60m band=0.90-0.95 league=ALL | 106 | 0.013 | [-0.033, 0.051] | 1.20 | 0.943 vs 0.931 | 1.44 | 17.1 | 0.008 |
| P5-02 | time=ko-5m band=0.80-0.90 league=ALL | 31 | 0.072 | [-0.041, 0.152] | 6.25 | 0.935 vs 0.865 | 5.88 | 8.0 | 0.047 |
| P3-15 | time=ko+60m band=0.80-0.90 league=CFB | 165 | 0.017 | [-0.044, 0.075] | 1.47 | 0.879 vs 0.855 | 1.85 | 25.1 | 0.009 |
| P3-27 | time=ko+120m band=0.90-0.95 league=CFB | 103 | 0.003 | [-0.050, 0.046] | 0.23 | 0.942 vs 0.935 | 0.27 | 25.7 | -0.003 |
| P3-18 | time=ko+60m band=0.90-0.95 league=CFB | 78 | 0.011 | [-0.054, 0.054] | 1.06 | 0.949 vs 0.933 | 1.36 | 17.1 | 0.006 |
| P5-06 | time=ko+60m band=0.90-0.95 league=ALL | 25 | 0.028 | [-0.059, 0.073] | 2.58 | 0.960 vs 0.929 | 3.39 | 8.0 | 0.013 |
| P3-25 | time=ko+120m band=0.90-0.95 league=ALL | 141 | -0.017 | [-0.064, 0.025] | -1.60 | 0.922 vs 0.933 | -1.58 | 37.9 | -0.021 |
| P3-22 | time=ko+120m band=0.80-0.90 league=ALL | 161 | -0.008 | [-0.067, 0.049] | -0.73 | 0.863 vs 0.862 | -0.77 | 27.7 | -0.015 |
| P3-24 | time=ko+120m band=0.80-0.90 league=CFB | 118 | 0.001 | [-0.071, 0.068] | 0.06 | 0.873 vs 0.864 | 0.07 | 21.4 | -0.009 |
| P3-13 | time=ko+60m band=0.80-0.90 league=ALL | 219 | -0.017 | [-0.071, 0.035] | -1.45 | 0.849 vs 0.855 | -1.43 | 63.8 | -0.024 |
| P4-01 | K>=1 band=0.70-0.80 league=ALL | 34 | 0.090 | [-0.072, 0.234] | 6.89 | 0.824 vs 0.756 | 5.28 | 17.9 | 0.046 |
| P3-17 | time=ko+60m band=0.90-0.95 league=NFL | 28 | 0.017 | [-0.080, 0.078] | 1.61 | 0.929 vs 0.925 | 1.75 | 9.4 | -0.000 |
| P5-08 | time=ko+120m band=0.80-0.90 league=ALL | 30 | 0.030 | [-0.100, 0.146] | 2.65 | 0.900 vs 0.865 | 2.62 | 9.6 | -0.002 |
| P3-07 | time=ko-5m band=0.90-0.95 league=ALL | 46 | -0.023 | [-0.117, 0.048] | -2.19 | 0.913 vs 0.930 | -1.73 | 29.6 | -0.037 |
| P3-10 | time=ko+60m band=0.70-0.80 league=ALL | 175 | -0.036 | [-0.123, 0.051] | -2.75 | 0.737 vs 0.751 | -1.98 | 64.6 | -0.048 |
| P3-05 | time=ko-5m band=0.80-0.90 league=NFL | 37 | 0.002 | [-0.130, 0.123] | 0.16 | 0.865 vs 0.854 | 0.11 | 26.7 | -0.030 |
| P4-04 | K>=2 band=0.70-0.80 league=ALL | 19 | 0.085 | [-0.132, 0.283] | 6.63 | 0.842 vs 0.763 | 5.48 | 10.2 | -0.002 |
| P5-05 | time=ko+60m band=0.80-0.90 league=ALL | 35 | -0.007 | [-0.146, 0.109] | -0.63 | 0.857 vs 0.855 | -0.54 | 16.3 | -0.046 |
| P3-12 | time=ko+60m band=0.70-0.80 league=CFB | 117 | -0.041 | [-0.146, 0.064] | -3.11 | 0.735 vs 0.753 | -2.57 | 57.4 | -0.059 |
| P3-09 | time=ko-5m band=0.90-0.95 league=CFB | 40 | -0.040 | [-0.146, 0.043] | -3.71 | 0.900 vs 0.932 | -2.98 | 31.2 | -0.058 |
| P3-01 | time=ko-5m band=0.70-0.80 league=ALL | 217 | -0.079 | [-0.161, 0.000] | -6.03 | 0.705 vs 0.754 | -5.38 | 136.0 | -0.089 |
| P3-11 | time=ko+60m band=0.70-0.80 league=NFL | 58 | -0.027 | [-0.168, 0.113] | -2.02 | 0.741 vs 0.748 | -1.10 | 32.3 | -0.064 |
| P3-23 | time=ko+120m band=0.80-0.90 league=NFL | 43 | -0.033 | [-0.168, 0.078] | -2.89 | 0.837 vs 0.857 | -2.33 | 19.8 | -0.064 |
| W-P3 | cum-net-pnl past weeks, >=30 trades | 112 | -0.085 | [-0.180, 0.001] | -7.19 | 0.768 vs 0.834 | -5.90 | 89.9 | -0.103 |
| P3-20 | time=ko+120m band=0.70-0.80 league=NFL | 36 | -0.004 | [-0.180, 0.169] | -0.27 | 0.750 vs 0.753 | -0.18 | 22.0 | -0.061 |
| P3-26 | time=ko+120m band=0.90-0.95 league=NFL | 38 | -0.070 | [-0.184, 0.039] | -6.58 | 0.868 vs 0.929 | -4.76 | 28.2 | -0.095 |
| P3-03 | time=ko-5m band=0.70-0.80 league=CFB | 143 | -0.090 | [-0.188, 0.006] | -6.90 | 0.699 vs 0.755 | -6.81 | 110.1 | -0.106 |
| P3-02 | time=ko-5m band=0.70-0.80 league=NFL | 74 | -0.057 | [-0.193, 0.076] | -4.37 | 0.716 vs 0.753 | -2.93 | 49.4 | -0.087 |
| P5-09 | time=ko+120m band=0.90-0.95 league=ALL | 20 | -0.036 | [-0.199, 0.076] | -3.36 | 0.900 vs 0.929 | -2.60 | 14.7 | -0.079 |
| P3-19 | time=ko+120m band=0.70-0.80 league=ALL | 142 | -0.101 | [-0.201, -0.008] | -7.75 | 0.683 vs 0.750 | -4.91 | 131.3 | -0.120 |
| P5-01 | time=ko-5m band=0.70-0.80 league=ALL | 42 | -0.074 | [-0.258, 0.082] | -5.74 | 0.714 vs 0.758 | -3.35 | 33.7 | -0.130 |
| P3-21 | time=ko+120m band=0.70-0.80 league=CFB | 106 | -0.135 | [-0.258, -0.021] | -10.29 | 0.660 vs 0.750 | -7.23 | 124.1 | -0.162 |
| P4-02 | K>=1 band=0.80-0.90 league=ALL | 28 | -0.085 | [-0.263, 0.080] | -7.28 | 0.786 vs 0.849 | -6.46 | 20.4 | -0.147 |
| P3-14 | time=ko+60m band=0.80-0.90 league=NFL | 54 | -0.120 | [-0.265, 0.007] | -10.39 | 0.759 vs 0.854 | -6.38 | 67.4 | -0.152 |
| P4-05 | K>=2 band=0.80-0.90 league=ALL | 21 | -0.059 | [-0.282, 0.113] | -5.06 | 0.810 vs 0.851 | -4.24 | 15.2 | -0.139 |
| P5-07 | time=ko+120m band=0.70-0.80 league=ALL | 25 | -0.065 | [-0.320, 0.147] | -5.02 | 0.720 vs 0.757 | -2.86 | 24.8 | -0.166 |
| W-P5 | cum-net-pnl past weeks, >=30 trades | 7 | -0.007 | [-0.332, 0.167] | -0.61 | 0.857 vs 0.854 | -2.33 | 1.5 | -0.418 |
| P1-01 | d=3c mode=mom league=ALL | 29 | -0.047 | [-0.396, 0.312] | -2.73 | 0.552 vs 0.562 | -1.11 | 27.6 | -0.260 |
| P1-03 | d=3c mode=mom league=CFB | 23 | -0.060 | [-0.407, 0.272] | -3.62 | 0.565 vs 0.585 | -1.66 | 21.8 | -0.305 |
| P5-04 | time=ko+60m band=0.70-0.80 league=ALL | 27 | -0.177 | [-0.419, 0.059] | -13.51 | 0.630 vs 0.751 | -7.28 | 47.7 | -0.291 |
| P1-04 | d=3c mode=rev league=ALL | 28 | -0.069 | [-0.449, 0.361] | -3.45 | 0.464 vs 0.482 | -1.41 | 21.0 | -0.336 |
| P4-06 | K>=2 band=0.90-0.95 league=ALL | 6 | -0.112 | [-0.467, 0.073] | -10.48 | 0.833 vs 0.933 | -5.30 | 9.3 | -1.000 |
| P1-06 | d=3c mode=rev league=CFB | 22 | -0.050 | [-0.481, 0.405] | -2.40 | 0.455 vs 0.461 | -1.10 | 16.7 | -0.419 |
| P1-10 | d=5c mode=rev league=ALL | 4 | 0.395 | [-0.585, 1.049] | 21.23 | 0.750 vs 0.520 | 15.66 | 1.1 | n/a |
| P4-03 | K>=1 band=0.90-0.95 league=ALL | 8 | -0.200 | [-0.597, 0.067] | -18.74 | 0.750 vs 0.932 | -6.04 | 18.6 | -0.645 |
| P1-02 | d=3c mode=mom league=NFL | 6 | 0.014 | [-0.718, 1.234] | 0.67 | 0.500 vs 0.477 | 0.18 | 12.2 | -1.000 |
| P1-05 | d=3c mode=rev league=NFL | 6 | -0.127 | [-0.759, 0.745] | -7.30 | 0.500 vs 0.557 | -1.99 | 15.1 | -1.000 |
| P1-12 | d=5c mode=rev league=CFB | 3 | 0.210 | [-1.000, 1.092] | 11.57 | 0.667 vs 0.533 | 8.12 | 1.1 | n/a |
| P1-09 | d=5c mode=mom league=CFB | 3 | -0.352 | [-1.000, 1.342] | -18.10 | 0.333 vs 0.497 | -14.30 | 5.4 | n/a |
| P1-08 | d=5c mode=mom league=NFL | 1 | -1.000 | [-1.000, -1.000] | -56.80 | 0.000 vs 0.550 | n/a | 5.7 | n/a |
| P1-07 | d=5c mode=mom league=ALL | 4 | -0.526 | [-1.000, 0.622] | -27.77 | 0.250 vs 0.510 | -22.94 | 11.1 | n/a |
| W-P1 | cum-net-pnl past weeks, >=30 trades | 3 | -0.451 | [-1.000, 0.859] | -27.40 | 0.333 vs 0.590 | -8.21 | 8.2 | n/a |

Files: trials_log.csv (all 57), daily_pnl.csv; per-trade trades_all.csv is gitignored.
