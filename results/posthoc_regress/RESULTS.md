# Post-hoc supervised residual regression: results

**Label: post-hoc, exploratory; supervised residual model over all data sources; walk-forward on training only; holdout not run.**

Spec: SPEC.md (4b318d6, committed before any real data). One run.

Snapshot rows: 46469 (1267 games); games with usable ESPN state (orientation defined, passing the Idea 10 defect rule): 921.

## Is there any predictable residual? (out of sample, test weeks)

R^2 is against the Kalshi price as the forecast (r = 0); corr is predicted vs realised residual.

| model | phase | rows | oos_r2_vs_price | corr_pred_real |
|---|---|---|---|---|
| RIDGE1 | all | 38060 | -0.0032 | 0.0323 |
| RIDGE1 | pregame | 4009 | -0.0079 | -0.0055 |
| RIDGE1 | ingame | 34051 | -0.0025 | 0.0374 |
| RIDGE10 | all | 38060 | -0.0032 | 0.0323 |
| RIDGE10 | pregame | 4009 | -0.0079 | -0.0055 |
| RIDGE10 | ingame | 34051 | -0.0024 | 0.0375 |
| LOGIT01 | all | 38060 | -0.2463 | -0.0018 |
| LOGIT01 | pregame | 4009 | -0.0454 | -0.0171 |
| LOGIT01 | ingame | 34051 | -0.2787 | -0.0007 |
| LOGIT1 | all | 38060 | -0.2524 | -0.0021 |
| LOGIT1 | pregame | 4009 | -0.0494 | -0.0176 |
| LOGIT1 | ingame | 34051 | -0.2851 | -0.001 |
| BOOST | all | 38060 | -0.0024 | 0.0208 |
| BOOST | pregame | 4009 | -0.0008 | -0.0188 |
| BOOST | ingame | 34051 | -0.0027 | 0.0232 |
| ISO | all | 38060 | -0.0035 | -0.0119 |
| ISO | pregame | 4009 | -0.0017 | 0.0037 |
| ISO | ingame | 34051 | -0.0038 | -0.0143 |

## Trials (48), top 12 by ROC CI lower bound (>= 20 trades)

Primary cost line: taker fee (TAKER) or maker fee 0.0175 (MAKER); alt_roc = maker fee 0 for MAKER.

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | win_rate | breakeven | sharpe_x365 | excl5_roc | alt_roc |
|---|---|---|---|---|---|---|---|---|---|---|
| RIDGE10.TAKER.m1.primary | 802 | 0.0088 | -0.0414 | 0.0594 | 0.5046 | 0.5754 | 0.5704 | 0.6683 | -0.0009 | 0.0088 |
| RIDGE1.TAKER.m1.primary | 802 | 0.0088 | -0.0415 | 0.0594 | 0.5036 | 0.5754 | 0.5704 | 0.6676 | -0.0009 | 0.0088 |
| RIDGE10.MAKER.m1.all | 7225 | -0.0081 | -0.0484 | 0.0329 | -0.4047 | 0.4946 | 0.4986 | -0.6873 | -0.0193 | -0.0011 |
| RIDGE1.MAKER.m0.all | 10138 | -0.019 | -0.0493 | 0.0122 | -0.9477 | 0.4896 | 0.4991 | -2.144 | -0.0271 | -0.0122 |
| RIDGE10.MAKER.m0.all | 10140 | -0.0191 | -0.0493 | 0.0123 | -0.9517 | 0.4898 | 0.4993 | -2.155 | -0.0271 | -0.0123 |
| RIDGE1.MAKER.m1.all | 7219 | -0.0087 | -0.0495 | 0.0321 | -0.434 | 0.4943 | 0.4987 | -0.738 | -0.0199 | -0.0017 |
| BOOST.MAKER.m0.all | 10492 | -0.0238 | -0.0528 | 0.0038 | -1.168 | 0.4792 | 0.4909 | -2.828 | -0.0325 | -0.0169 |
| BOOST.MAKER.m1.all | 7128 | -0.0229 | -0.0624 | 0.0181 | -1.137 | 0.4845 | 0.4959 | -1.874 | -0.0352 | -0.0159 |
| ISO.MAKER.m0.all | 7797 | -0.0396 | -0.063 | -0.0163 | -1.875 | 0.4552 | 0.474 | -6.122 | -0.0476 | -0.0326 |
| LOGIT1.MAKER.m0.all | 9027 | -0.0404 | -0.063 | -0.0177 | -1.92 | 0.4559 | 0.4751 | -5.593 | -0.0477 | -0.0319 |
| LOGIT01.MAKER.m0.all | 9180 | -0.0415 | -0.064 | -0.0191 | -1.9 | 0.4387 | 0.4577 | -5.642 | -0.0491 | -0.0329 |
| LOGIT1.MAKER.m1.all | 7952 | -0.0391 | -0.064 | -0.015 | -1.932 | 0.4748 | 0.4942 | -5.256 | -0.047 | -0.0306 |

All 48 trials: trials_log.csv. Trials with any trade: 48.

## Feature importance (descriptive; drop in OOS correlation when shuffled)

| model | feature | corr_drop |
|---|---|---|
| RIDGE10 | wp_gap | 0.0163 |
| RIDGE10 | x_wpgap | 0.0134 |
| RIDGE10 | x_p_min | 0.0063 |
| RIDGE10 | mins_from_ko | 0.0052 |
| RIDGE10 | x_p_sec | 0.0029 |
| RIDGE10 | x_s1 | 0.0022 |
| RIDGE10 | sec_left | 0.0017 |
| RIDGE10 | score_diff | 0.0016 |
| RIDGE10 | dp15 | 0.0012 |
| RIDGE10 | q | 0.0009 |

| model | feature | corr_drop |
|---|---|---|
| BOOST (last 6 test weeks) | v15 | 0.0056 |
| BOOST (last 6 test weeks) | x_p_sd | 0.0025 |
| BOOST (last 6 test weeks) | x_p_min | 0.0018 |
| BOOST (last 6 test weeks) | n5 | 0.0016 |
| BOOST (last 6 test weeks) | mins_from_ko | 0.0015 |
| BOOST (last 6 test weeks) | period | 0.0004 |
| BOOST (last 6 test weeks) | own_poss | 0 |
| BOOST (last 6 test weeks) | x_pmgap | 0 |
| BOOST (last 6 test weeks) | x_wpgap | 0 |
| BOOST (last 6 test weeks) | x_p2 | 0 |

## Cumulative multiple-testing correction

Trials in correction: 363 (own 48; external: {"costside": {"trials": 168, "status": "daily P&L used", "with_daily": 166}, "search": {"trials": 54, "status": "daily P&L used", "with_daily": 50}, "maker": {"trials": 36, "status": "daily P&L used", "with_daily": 36}, "patterns": {"trials": 57, "status": "daily P&L used", "with_daily": 57}, "unsup": {"trials": 0, "status": "not found"}}).
Studentized Reality Check p (best by t: patterns:P3-08): 0.4175.
DSR of the best: 5.877011226110316e-26 (normal returns: 1.6301801077532054e-08).
Holm survivors at 0.05: [].
Candidate edges (CI lo > 0, RC p < 0.05, >= 100 trades, excl. top 5 > 0): [].

