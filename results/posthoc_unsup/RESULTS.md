# Post-hoc unsupervised regime mining: results

**Label: post-hoc, exploratory; clusters fit on past weeks only; training only; holdout not run.** Spec: SPEC.md.

Snapshot build: {"games": 1267, "no_file": 0, "espn_ok": 542, "espn_defect": 725, "espn_missing": 0, "orient_none": 0}; 44888 snapshot rows; ESPN features missing for games failing the wallclock defect rule or with no orientation.

## All 64 trials (walk-forward test weeks; primary cost line: taker 0.07 fee, or maker 0.0175 fee; alt_roc = maker fee 0 for maker trials)

| trial | trades | games | roc | roc_lo | roc_hi | c_per_contract | win_rate | breakeven | sharpe_x365 | max_dd | excl5_roc | excl5_pnl | alt_roc | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| U.gmm.k16.m1.n100.maker.secondary | 143 | 58 | 0.03566 | -0.02452 | 0.08214 | 3.034 | 0.8811 | 0.8508 | 7.843 | 16.1 | 0.004099 | 3.96 | 0.03815 | 1 |
| U.gmm.k16.m1.n300.maker.secondary | 122 | 48 | 0.03519 | -0.02398 | 0.07846 | 3.176 | 0.9344 | 0.9027 | 9.711 | 16.1 | 0.008041 | 6.86 | 0.03731 | 1 |
| U.gmm.k16.m0.n300.taker.secondary | 126 | 49 | 0.02545 | -0.03836 | 0.0744 | 2.344 | 0.9444 | 0.921 | 8.606 | 15.81 | -0.002627 | -2.45 | 0.02545 | 1 |
| U.gmm.k16.m0.n100.taker.secondary | 136 | 52 | 0.02249 | -0.04375 | 0.07042 | 1.924 | 0.875 | 0.8558 | 6.832 | 15.81 | -0.006209 | -5.81 | 0.02249 | 1 |
| U.gmm.k16.m1.n100.maker.primary | 37 | 37 | 0.01582 | -0.1132 | 0.1326 | 1.178 | 0.7568 | 0.745 | 1.483 | 11.45 | -0.05745 | -14.02 | 0.01929 | 1 |
| U.kmeans.k16.m1.n300.maker.primary | 105 | 105 | 0.01053 | -0.1575 | 0.1865 | 0.4762 | 0.4571 | 0.4524 | 0.4653 | 25.39 | -0.07354 | -34.13 | 0.01803 | 1 |
| U.kmeans.k16.m0.n300.maker.secondary | 3822 | 608 | -0.006481 | -0.06215 | 0.04781 | -0.2953 | 0.4526 | 0.4556 | -0.4956 | 505.9 | -0.03352 | -581.4 | 0.000399 | 1 |
| U.gmm.k8.m0.n300.maker.secondary | 335 | 133 | -0.008397 | -0.07883 | 0.04619 | -0.7179 | 0.8478 | 0.8549 | -1.179 | 106.1 | -0.03134 | -83.15 | -0.005811 | 1 |
| U.gmm.k8.m0.n100.maker.secondary | 335 | 133 | -0.008397 | -0.07883 | 0.04619 | -0.7179 | 0.8478 | 0.8549 | -1.179 | 106.1 | -0.03134 | -83.15 | -0.005811 | 1 |
| U.gmm.k16.m1.n300.maker.primary | 27 | 27 | -0.01003 | -0.1397 | 0.1001 | -0.863 | 0.8519 | 0.8605 | -1.412 | 11.45 | -0.0662 | -12.76 | -0.007337 | 1 |
| U.kmeans.k16.m0.n100.maker.secondary | 3864 | 618 | -0.01044 | -0.06383 | 0.0435 | -0.4744 | 0.4498 | 0.4545 | -0.7925 | 505.9 | -0.03726 | -651.8 | -0.003549 | 1 |
| U.gmm.k16.m0.n300.taker.primary | 36 | 36 | -0.01134 | -0.1258 | 0.07875 | -1.019 | 0.8889 | 0.8991 | -2.144 | 14.77 | -0.04893 | -13.89 | -0.01134 | 1 |
| U.gmm.k16.m0.n100.taker.primary | 39 | 39 | -0.01687 | -0.1271 | 0.07164 | -1.408 | 0.8205 | 0.8346 | -3 | 14.77 | -0.05499 | -15.71 | -0.01687 | 1 |
| U.kmeans.k16.m1.n100.maker.primary | 121 | 121 | -0.01881 | -0.1821 | 0.1511 | -0.8554 | 0.4463 | 0.4548 | -0.8293 | 44.43 | -0.09172 | -49.48 | -0.01135 | 1 |
| U.gmm.k16.m0.n100.maker.secondary | 2040 | 369 | -0.03008 | -0.07816 | 0.01682 | -1.59 | 0.5127 | 0.5286 | -3.253 | 441.2 | -0.0532 | -557.4 | -0.02425 | 1 |
| U.gmm.k16.m0.n300.maker.secondary | 2018 | 365 | -0.03149 | -0.08318 | 0.01609 | -1.666 | 0.5124 | 0.529 | -3.433 | 452.9 | -0.05489 | -569.1 | -0.02567 | 1 |
| U.gmm.k8.m0.n300.taker.secondary | 80 | 29 | -0.04456 | -0.1845 | 0.05202 | -4.139 | 0.8875 | 0.9289 |  | 33.11 | -0.09212 | -53.78 | -0.04456 | 1 |
| U.gmm.k8.m0.n100.taker.secondary | 80 | 29 | -0.04456 | -0.1845 | 0.05202 | -4.139 | 0.8875 | 0.9289 |  | 33.11 | -0.09212 | -53.78 | -0.04456 | 1 |
| U.kmeans.k16.m0.n100.maker.primary | 425 | 425 | -0.04967 | -0.1367 | 0.03778 | -2.361 | 0.4518 | 0.4754 | -3.418 | 110.5 | -0.07082 | -142.5 | -0.04235 | 1 |
| U.gmm.k8.m0.n100.maker.primary | 66 | 66 | -0.04976 | -0.1815 | 0.066 | -3.888 | 0.7424 | 0.7813 | -5.264 | 44.76 | -0.1099 | -54.32 | -0.04632 | 1 |
| U.gmm.k8.m0.n300.maker.primary | 66 | 66 | -0.04976 | -0.1815 | 0.066 | -3.888 | 0.7424 | 0.7813 | -5.264 | 44.76 | -0.1099 | -54.32 | -0.04632 | 1 |
| U.kmeans.k16.m0.n300.maker.primary | 416 | 416 | -0.05054 | -0.1352 | 0.03837 | -2.393 | 0.4495 | 0.4734 | -3.6 | 100.5 | -0.07224 | -141.7 | -0.04318 | 1 |
| U.gmm.k8.m1.n300.maker.secondary | 57 | 23 | -0.05632 | -0.1997 | 0.05141 | -5.235 | 0.8772 | 0.9295 |  | 29.84 | -0.1299 | -46.28 | -0.05464 | 1 |
| U.gmm.k8.m1.n100.maker.secondary | 57 | 23 | -0.05632 | -0.1997 | 0.05141 | -5.235 | 0.8772 | 0.9295 |  | 29.84 | -0.1299 | -46.28 | -0.05464 | 1 |
| U.gmm.k16.m0.n300.maker.primary | 266 | 266 | -0.05955 | -0.1495 | 0.03231 | -3.178 | 0.5019 | 0.5337 | -3.707 | 104.1 | -0.08837 | -124.6 | -0.05353 | 1 |
| U.gmm.k16.m0.n100.maker.primary | 270 | 270 | -0.0617 | -0.1531 | 0.02415 | -3.276 | 0.4981 | 0.5309 | -3.811 | 108 | -0.09026 | -128.5 | -0.05568 | 1 |
| U.kmeans.k16.m1.n300.maker.secondary | 696 | 144 | -0.06777 | -0.2083 | 0.07258 | -2.559 | 0.352 | 0.3776 | -3.319 | 209.6 | -0.1825 | -453.3 | -0.06029 | 1 |
| U.kmeans.k16.m1.n100.maker.secondary | 733 | 165 | -0.08436 | -0.2208 | 0.05082 | -3.18 | 0.3452 | 0.377 | -3.999 | 238.9 | -0.1941 | -508.2 | -0.07691 | 1 |
| U.gmm.k8.m0.n100.taker.primary | 22 | 22 | -0.08898 | -0.2863 | 0.07094 | -7.991 | 0.8182 | 0.8981 |  | 17.58 | -0.1732 | -27.24 | -0.08898 | 1 |
| U.gmm.k8.m0.n300.taker.primary | 22 | 22 | -0.08898 | -0.2863 | 0.07094 | -7.991 | 0.8182 | 0.8981 |  | 17.58 | -0.1732 | -27.24 | -0.08898 | 1 |
| U.gmm.k8.m1.n100.maker.primary | 13 | 13 | -0.1415 | -0.3954 | 0.08198 | -12.68 | 0.7692 | 0.896 |  | 16.48 | -0.3182 | -23.34 | -0.1394 | 1 |
| U.gmm.k8.m1.n300.maker.primary | 13 | 13 | -0.1415 | -0.3954 | 0.08198 | -12.68 | 0.7692 | 0.896 |  | 16.48 | -0.3182 | -23.34 | -0.1394 | 1 |
| U.kmeans.k8.m0.n300.maker.secondary | 409 | 41 | -0.1677 | -0.3635 | 0.01765 | -7.982 | 0.3961 | 0.4759 | -13.81 | 326.5 | -0.3373 | -529.2 | -0.1609 | 1 |
| U.kmeans.k8.m0.n100.maker.secondary | 409 | 41 | -0.1677 | -0.3635 | 0.01765 | -7.982 | 0.3961 | 0.4759 | -13.81 | 326.5 | -0.3373 | -529.2 | -0.1609 | 1 |
| U.kmeans.k16.m1.n100.taker.primary | 22 | 22 | -0.1808 | -0.5921 | 0.2241 | -8.027 | 0.3636 | 0.4439 | -9.235 | 23.08 | -0.5935 | -43.8 | -0.1808 | 1 |
| U.kmeans.k16.m0.n100.taker.primary | 35 | 35 | -0.1899 | -0.5509 | 0.198 | -7.369 | 0.3143 | 0.388 | -10.38 | 31.21 | -0.4967 | -59.22 | -0.1899 | 1 |
| U.kmeans.k8.m0.n300.maker.primary | 37 | 37 | -0.209 | -0.4544 | 0.0241 | -12.86 | 0.4865 | 0.6151 | -9.676 | 47.57 | -0.3666 | -75.24 | -0.2039 | 1 |
| U.kmeans.k8.m0.n100.maker.primary | 37 | 37 | -0.209 | -0.4544 | 0.0241 | -12.86 | 0.4865 | 0.6151 | -9.676 | 47.57 | -0.3666 | -75.24 | -0.2039 | 1 |
| U.kmeans.k16.m0.n300.taker.primary | 13 | 13 | -0.2132 | -0.7851 | 0.64 | -6.254 | 0.2308 | 0.2933 | -63.38 | 8.13 | -1 | -26.01 | -0.2132 | 1 |
| U.kmeans.k16.m1.n100.taker.secondary | 49 | 23 | -0.3318 | -0.6445 | 0.03029 | -12.16 | 0.2449 | 0.3665 | -11.84 | 65 | -0.6472 | -91.72 | -0.3318 | 1 |
| U.kmeans.k16.m0.n100.taker.secondary | 163 | 36 | -0.4148 | -0.6779 | -0.1142 | -10.87 | 0.1534 | 0.2621 | -12.44 | 182.6 | -0.6862 | -240.6 | -0.4148 | 1 |
| U.kmeans.k16.m0.n300.taker.secondary | 114 | 13 | -0.475 | -0.8819 | -0.0343 | -10.32 | 0.114 | 0.2172 | -12.1 | 117.6 | -0.8787 | -144.9 | -0.475 | 1 |
| U.kmeans.k8.m0.n100.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m0.n100.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m0.n300.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m0.n300.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m1.n100.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m1.n100.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m1.n100.maker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m1.n100.maker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m1.n300.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m1.n300.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m1.n300.maker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k8.m1.n300.maker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k16.m1.n300.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.kmeans.k16.m1.n300.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.gmm.k8.m1.n100.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.gmm.k8.m1.n100.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.gmm.k8.m1.n300.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.gmm.k8.m1.n300.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.gmm.k16.m1.n100.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.gmm.k16.m1.n100.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.gmm.k16.m1.n300.taker.primary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |
| U.gmm.k16.m1.n300.taker.secondary | 0 | 0 |  |  |  |  |  |  |  |  |  |  |  | 1 |

## Multiple-testing correction over cumulative trials

```
{
 "own_trials": 64,
 "prior": {
  "costside_own": 174,
  "search": {
   "trials": 54,
   "status": "daily P&L used",
   "with_daily": 50
  },
  "maker": {
   "trials": 36,
   "status": "daily P&L used",
   "with_daily": 36
  },
  "patterns": {
   "trials": 57,
   "status": "daily P&L used",
   "with_daily": 57
  },
  "unsup": {
   "trials": 0,
   "status": "not found yet"
  },
  "regress": {
   "trials": 48,
   "status": "daily P&L used",
   "with_daily": 48
  }
 },
 "cumulative_trials": 433,
 "rc_p_best_by_t": 0.4475,
 "best_by_t": "patterns:P3-08",
 "best_t": 2.4953726779022576,
 "dsr_best": 6.691871112367474e-24,
 "dsr_best_normal_returns": 6.282335168619991e-08,
 "days": 112,
 "holm_survivors_005": [],
 "stop_candidates": [],
 "stop_condition_met": false
}
```

## Walk-forward performance by the past rank of the trade's cluster (k-means k 8, margin 0, n_min 100, taker, primary)

| past_rank | trades |
|---|---|
| 1 | 0 |
| 2 | 0 |
| 3 | 0 |
| 4 | 0 |
| 5 | 0 |

## Pooled walk-forward performance by past cluster rank (added after the run; descriptive only)

The SPEC reference trial made 0 trades (no k-means k 8 cluster ever cleared the taker cost on past weeks), so the table above is empty. This supplement pools all trades of all 64 trials, de-duplicated on (game, team, decision time, execution), by the past rank of the trade's cluster. Overlapping trials; not a trial and not counted in the correction.

| execution | clusterer | past_rank | trades | games | roc | roc_lo | roc_hi | c_per_contract | win_rate | breakeven | excl5_roc |
|---|---|---|---|---|---|---|---|---|---|---|---|
| maker | gmm | 1 | 1223 | 294 | -0.003397 | -0.05869 | 0.04976 | -0.1809 | 0.5307 | 0.5325 | -0.03358 |
| maker | gmm | 2 | 543 | 107 | -0.04464 | -0.1576 | 0.05742 | -2.59 | 0.5543 | 0.5802 | -0.1089 |
| maker | gmm | 3 | 335 | 68 | -0.117 | -0.2573 | 0.01245 | -6.251 | 0.4716 | 0.5341 | -0.1998 |
| maker | gmm | 4 | 77 | 10 | 0.001741 | -0.07742 | 0.07568 | 0.09481 | 0.5455 | 0.5445 | -0.1107 |
| maker | gmm | 5 | 0 |  |  |  |  |  |  |  |  |
| maker | kmeans | 1 | 1649 | 323 | -0.02765 | -0.1196 | 0.06162 | -1.276 | 0.4488 | 0.4615 | -0.07955 |
| maker | kmeans | 2 | 1531 | 225 | -0.06071 | -0.1626 | 0.03949 | -2.436 | 0.3769 | 0.4012 | -0.1263 |
| maker | kmeans | 3 | 852 | 183 | 0.02737 | -0.0615 | 0.109 | 1.645 | 0.6174 | 0.6009 | -0.03839 |
| maker | kmeans | 4 | 162 | 14 | 0.04614 | -0.4273 | 0.6231 | 1.334 | 0.3025 | 0.2891 | -0.5223 |
| maker | kmeans | 5 | 0 |  |  |  |  |  |  |  |  |
| taker | gmm | 1 | 157 | 54 | 0.009134 | -0.06778 | 0.06384 | 0.7898 | 0.8726 | 0.8647 | -0.02259 |
| taker | gmm | 2 | 0 |  |  |  |  |  |  |  |  |
| taker | gmm | 3 | 0 |  |  |  |  |  |  |  |  |
| taker | gmm | 4 | 0 |  |  |  |  |  |  |  |  |
| taker | gmm | 5 | 0 |  |  |  |  |  |  |  |  |
| taker | kmeans | 1 | 163 | 36 | -0.4148 | -0.6779 | -0.1142 | -10.87 | 0.1534 | 0.2621 | -0.6862 |
| taker | kmeans | 2 | 0 |  |  |  |  |  |  |  |  |
| taker | kmeans | 3 | 0 |  |  |  |  |  |  |  |  |
| taker | kmeans | 4 | 0 |  |  |  |  |  |  |  |  |
| taker | kmeans | 5 | 0 |  |  |  |  |  |  |  |  |

## Cluster atlas (DESCRIPTIVE ONLY, in-sample: k-means k 8 on all training rows)

net_resid_taker = mean(payout - price - taker cost); raw_resid = mean(payout - price).

| cl | rows | price | mins_from_ko | nfl | score_diff | espn_missing | pm_gap | dp5 | n15 | imb5 | net_resid_taker | raw_resid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 7561 | 0.6361 | 83.32 | 0.0006613 | 3.143 | 0.7101 | -0.02483 | 0.04588 | 1003 | 0.135 | -0.03064 | -0.007048 |
| 1 | 3293 | 0.5053 | 96.11 | 0.8709 | -0.00161 | 0.05679 | -0.003877 | 0.001442 | 4604 | 0.001477 | -0.02734 | -0.004215 |
| 2 | 7414 | 0.5072 | 81.31 | 0.9814 | 0.1271 | 0.02131 | -0.003646 | -8.363e-05 | 1144 | -0.003271 | -0.02429 | -0.00353 |
| 3 | 8946 | 0.8571 | 82.89 | 0.002124 | 11.48 | 0.7708 | -0.002523 | -0.001723 | 214.3 | -0.3887 | -0.01932 | -0.001972 |
| 4 | 1830 | 0.51 | 86.82 | 1 | 0.128 | 0.347 |  | -0.0001858 | 118.8 | -0.000522 | -0.02907 | -0.007508 |
| 5 | 489 | 0.4986 | 133.3 | 0.9407 | -0.0766 | 0.01227 | -0.002244 | -0.0005521 | 1.128e+04 | -0.004642 | -0.02426 | -0.001656 |
| 6 | 4850 | 0.3683 | 98.55 | 0.004742 | -2.966 | 0.7148 | 0.02003 | -0.06881 | 1225 | -0.05931 | -0.0252 | -0.001551 |
| 7 | 10505 | 0.1273 | 82.96 | 0.00257 | -12.23 | 0.7603 | -0.005035 | -0.001498 | 217.5 | 0.34 | -0.02698 | -0.009995 |
## Verdict

**No candidate edge.** No trial has a walk-forward ROC CI above 0. The best trial (GMM k 16, margin 1 c, n_min 100,
maker, secondary) has ROC +0.036 [-0.025, +0.082] on 143 trades in 58 games, falls to +0.004 without its top 5
games, and is one of 64 trials here and 433 cumulative. Reality Check p over the 433 cumulative trials = 0.45, no
Holm survivor, stop condition not met. Nothing is recommended for a holdout test.

24 of 64 trials made 0 trades: with the taker cost (1 c spread plus fee), no cluster's past mean net residual was
positive in any week for k-means k 8 or for any margin-1 taker setting.

**Atlas reading (in-sample, descriptive):** all 8 k-means regimes have a NEGATIVE raw residual (payout minus last
price, -0.2 to -1.0 c) and a net residual after taker cost of -1.9 to -3.1 c. The regimes span heavy favourites,
heavy underdogs, NFL coin-flips, high-volume and thin markets, with and without polymarket.com and ESPN state. No
market or game state in training has Kalshi underpricing the team even before costs.

ESPN features are missing for 725 of 1,267 games (wallclock defect rule, mostly plays outside
[kickoff - 30 min, kickoff + 6 h]); 21 percent of rows lack polymarket.com; 76 percent lack an nflverse line.
