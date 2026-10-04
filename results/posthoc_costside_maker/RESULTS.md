# Post-hoc maker / spread-capture search: RESULTS

Post-hoc, exploratory, training only (kickoff before 2026-08-01), 36 trials as fixed in SPEC.md (spec commit bb58f56,
2026-10-04 05:36 ET; the SPEC header says "05:5x" which is a typo, the commit time is 05:36). Costs always charged.
Evaluated on the 19 test ET weeks (1,024 games with usable markets; 1,266 of 1,267 training games usable overall).
Maker fee lines: m0 = 0, m175 = 0.0175*C*P*(1-P) rounded up per order (not first-party confirmed; secondary sources).
ROC and the ranking use m175. Exits are taker (0.07 fee). Fill rule: strict trade-through only, fill at the limit.

## Headline
- **No trial has a 95% CI wholly above zero.** Of 36 trials, 20 have a CI wholly below zero (the in-game two-sided
  quoting M2/M4_in and the exit variants); the rest straddle zero with wide CIs on tiny fill counts.
- **Adverse selection kills spread capture.** Strict trade-through fills occur when price moves against the resting bid:
  filled contracts win about 1.3 to 1.5 cents less than their fill price in-game (M2: win rate 0.48-0.49 vs fill
  price 0.50-0.51). The 1 to 3 cent spread you capture on paper is more than offset, before fees. With maker fee 0 the
  in-game trials still lose 1.3 to 1.5 c/contract; the m175 fee adds about 0.4 c.
- **Pregame quoting barely fills** (fill rate 0.3 to 8% for h=1, near 0 for h=2): pregame trading is too thin for a
  strict trade-through to occur. M1 h1 cap10 settle: 1,138 fills, -1.05 c/ct m175, -0.58 c/ct m0, CI [-6.5%, +2.3%].
- Exiting at the end of the window as taker makes every M1/M2 variant worse (exit crosses the spread and pays the
  taker fee): about -2.4 to -2.9 c/ct.
- **M3 favourites**: pregame thr 0.85 shows +3.8% ROC (+3.4 c/ct m175) but on 71 fills in 48 games, CI [-4.8%, +10.9%];
  not distinguishable from zero and fragile (thr 0.90 pregame is -5.4% on 34 fills). Late in-game 0.85: 1,259 fills,
  -1.1% [-3.8%, +1.4%], -1.0 c/ct; its win rate (0.8975) is below the mean fill price (0.9052).
- **M4 box**: both-legs-fill cycles are common in-game (h2 W15: 1,034 pairs, mean pair cost 0.981, paired-only net
  +$51.93 over 5-contract pairs, about +1.0 c/pair-contract after m175 fees) but the orphan legs (one side fills, the
  other never) lose far more, so the total is -$336 (ROC -3.5%). h1 pairs cost about 1.00 and lose to fees. So the box
  edge exists only for h>=2 in-game and is swamped by single-leg adverse selection. Hedging orphans by taker was not in
  the spec and was not tried.
- **Walk-forward selectors**: WF-M2 never selected a config (no past-week config was positive after fees); WF-M3
  traded 52 fills at +1.4 c/ct, CI [-8.7%, +9.9%]; WF-M1 and WF-M4 lose.
- Caveat: M4_pre_h1_W5 == M1_h1_cap10_settle and M4_in_h1_W5/M4_in_h2_W5 duplicate M2 cap10 settle (same simulation,
  counted separately per spec). Gross paper "spread capture" assumes fills at the limit and no queue, which is optimistic
  and would only be mitigated by the strict rule already used; true results are not better than these.

## Ranked trial table (sorted by lower CI bound of ROC m175; test weeks)

| rank | trial | fills | fill rate | adverse sel (win - px) | ROC m175 | 95% CI | c/ct m175 | c/ct m0 | ROC excl top5 | Sharpe | maxDD $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | M2_h3_cap10_settle | 3701 | 0.308 | -0.0127 | -0.0336 | [-0.0377, -0.0296] | -1.70 | -1.27 | -0.0343 | -9.5 | 315 |
| 2 | M2_h2_cap10_settle | 3825 | 0.418 | -0.0133 | -0.0345 | [-0.0381, -0.0311] | -1.76 | -1.33 | -0.0351 | -9.9 | 337 |
| 3 | M4_in_h2_W5 | 3825 | 0.418 | -0.0133 | -0.0345 | [-0.0381, -0.0311] | -1.76 | -1.33 | -0.0351 | -9.9 | 337 |
| 4 | M3_late_thr85 | 1259 | 0.276 | -0.0076 | -0.0111 | [-0.0384, 0.0139] | -1.01 | -0.76 | -0.0125 | -1.4 | 97 |
| 5 | M2_h1_cap30_settle | 11407 | 0.587 | -0.0142 | -0.0362 | [-0.0389, -0.0335] | -1.84 | -1.42 | -0.0367 | -9.8 | 1048 |
| 6 | M3_late_thr90 | 1077 | 0.245 | -0.0109 | -0.0139 | [-0.0395, 0.0103] | -1.29 | -1.09 | -0.0151 | -2.1 | 100 |
| 7 | M2_h2_cap30_settle | 10910 | 0.439 | -0.0141 | -0.0363 | [-0.0396, -0.0329] | -1.83 | -1.41 | -0.0369 | -10.2 | 1000 |
| 8 | M4_in_h2_W15 | 3782 | 0.641 | -0.0136 | -0.0352 | [-0.0398, -0.0307] | -1.78 | -1.36 | -0.0360 | -9.5 | 336 |
| 9 | M2_h1_cap10_settle | 3909 | 0.559 | -0.0148 | -0.0373 | [-0.0400, -0.0345] | -1.91 | -1.48 | -0.0377 | -9.9 | 373 |
| 10 | M4_in_h1_W5 | 3909 | 0.559 | -0.0148 | -0.0373 | [-0.0400, -0.0345] | -1.91 | -1.48 | -0.0377 | -9.9 | 373 |
| 11 | M4_in_h1_W15 | 3884 | 0.750 | -0.0144 | -0.0365 | [-0.0403, -0.0330] | -1.86 | -1.44 | -0.0372 | -9.7 | 361 |
| 12 | M2_h3_cap30_settle | 10308 | 0.341 | -0.0137 | -0.0360 | [-0.0403, -0.0318] | -1.80 | -1.37 | -0.0371 | -10.3 | 931 |
| 13 | M3_pre_thr85 | 71 | 0.037 | 0.0370 | 0.0383 | [-0.0483, 0.1087] | 3.43 | 3.70 | 0.0166 | 1.6 | 8 |
| 14 | M1_h1_cap30_exit | 1597 | 0.076 | -0.0020 | -0.0499 | [-0.0551, -0.0445] | -2.43 | -1.95 | -0.0539 | -12.4 | 194 |
| 15 | M1_h1_cap10_exit | 1138 | 0.059 | -0.0058 | -0.0504 | [-0.0573, -0.0433] | -2.46 | -1.99 | -0.0555 | -12.0 | 140 |
| 16 | M2_h2_cap10_exit | 3825 | 0.418 | -0.0133 | -0.0555 | [-0.0597, -0.0512] | -2.83 | -2.40 | -0.0572 | -11.0 | 542 |
| 17 | M2_h3_cap10_exit | 3701 | 0.308 | -0.0127 | -0.0553 | [-0.0601, -0.0506] | -2.79 | -2.36 | -0.0572 | -10.8 | 517 |
| 18 | M2_h1_cap30_exit | 11407 | 0.587 | -0.0142 | -0.0568 | [-0.0603, -0.0530] | -2.88 | -2.47 | -0.0585 | -10.9 | 1645 |
| 19 | M1_h2_cap30_exit | 55 | 0.003 | -0.0522 | -0.0451 | [-0.0613, -0.0277] | -2.14 | -1.68 | -0.0544 | -7.5 | 6 |
| 20 | M2_h1_cap10_exit | 3909 | 0.559 | -0.0148 | -0.0578 | [-0.0616, -0.0539] | -2.96 | -2.53 | -0.0595 | -11.0 | 578 |
| 21 | M2_h2_cap30_exit | 10910 | 0.439 | -0.0141 | -0.0577 | [-0.0617, -0.0534] | -2.91 | -2.49 | -0.0596 | -11.2 | 1590 |
| 22 | M1_h2_cap10_exit | 52 | 0.002 | -0.0640 | -0.0450 | [-0.0620, -0.0270] | -2.13 | -1.67 | -0.0550 | -7.6 | 6 |
| 23 | M1_h1_cap30_settle | 1597 | 0.076 | -0.0020 | -0.0140 | [-0.0632, 0.0354] | -0.68 | -0.20 | -0.0324 | -1.0 | 138 |
| 24 | M2_h3_cap30_exit | 10308 | 0.341 | -0.0137 | -0.0586 | [-0.0632, -0.0537] | -2.93 | -2.49 | -0.0608 | -11.3 | 1509 |
| 25 | M1_h1_cap10_settle | 1138 | 0.059 | -0.0058 | -0.0216 | [-0.0654, 0.0229] | -1.05 | -0.58 | -0.0361 | -1.8 | 97 |
| 26 | M4_pre_h1_W5 | 1138 | 0.059 | -0.0058 | -0.0216 | [-0.0654, 0.0229] | -1.05 | -0.58 | -0.0361 | -1.8 | 97 |
| 27 | M4_pre_h1_W15 | 819 | 0.146 | -0.0060 | -0.0221 | [-0.0814, 0.0357] | -1.07 | -0.60 | -0.0422 | -1.5 | 76 |
| 28 | WF-M3 | 52 | 0.030 | 0.0169 | 0.0159 | [-0.0875, 0.0987] | 1.45 | 1.69 | -0.0167 | 0.6 | 11 |
| 29 | M3_pre_thr90 | 34 | 0.029 | -0.0488 | -0.0545 | [-0.2107, 0.0657] | -5.08 | -4.88 | -0.1118 | -1.4 | 16 |
| 30 | M4_pre_h2_W15 | 66 | 0.012 | -0.0411 | -0.0952 | [-0.3448, 0.1740] | -4.62 | -4.11 | -0.2536 | -1.3 | 31 |
| 31 | M1_h2_cap30_settle | 55 | 0.003 | -0.0522 | -0.1195 | [-0.3747, 0.1170] | -5.68 | -5.22 | -0.3112 | -1.7 | 20 |
| 32 | WF-M4 | 62 | 0.004 | -0.0703 | -0.1522 | [-0.3762, 0.0736] | -7.53 | -7.03 | -0.2893 | -2.4 | 34 |
| 33 | WF-M1 | 54 | 0.003 | -0.0620 | -0.1405 | [-0.3857, 0.0954] | -6.66 | -6.20 | -0.3112 | -2.1 | 20 |
| 34 | M4_pre_h2_W5 | 52 | 0.002 | -0.0640 | -0.1452 | [-0.4010, 0.0983] | -6.86 | -6.40 | -0.3253 | -2.1 | 20 |
| 35 | M1_h2_cap10_settle | 52 | 0.002 | -0.0640 | -0.1452 | [-0.4010, 0.0983] | -6.86 | -6.40 | -0.3253 | -2.1 | 20 |
| 36 | WF-M2 | 0 |  |  |  | [, ] |  |  |  |  | 0 |

ROC m175 = net P&L / (entry cost + entry fee), ratio of sums; bootstrap over games, 2,000 reps, seed 20261004.
Sharpe = daily mean/std * sqrt(365) over game days, m175 line. maxDD in dollars on the cumulative daily P&L.
The ROC all-weeks diagnostic is in trials_log.csv (roc_m175_allweeks).

## Files
- results/posthoc_costside_maker/trials_log.csv (one row per trial, extra columns for both fee lines, fill rate,
  adverse selection, pairs, Sharpe, drawdown)
- results/posthoc_costside_maker/daily_pnl.csv (trial_id, et_date, pnl on m175; pnl_maker0 extra column)
- scripts/posthoc_costside_maker.py, scripts/run_posthoc_costside_maker.py, tests/test_posthoc_costside_maker.py
