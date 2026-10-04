# Post-hoc cost-side search: results

**Label: post-hoc, exploratory; training only (walk-forward test weeks); every trial counted; holdout not run.**

## Round 1 (79 trials; run 2026-10-04 05:45 ET)

Bug disclosed: the first Round 1 run mapped no signals for Ideas 7 and 12 (their files store team as "home"/"away";
0 trades in those 8 trials). Fixed (mapped to Kalshi codes) and Round 1 rerun once; the first run's log and trials
table are kept on disk (data/costside_cache/*first_bugged*, gitignored). Verdict unchanged.

### Maker fill rate and adverse selection (win rate of filled vs unfilled signals)

| sig | cfg | mean_filled | mean_unfilled | count_filled | count_unfilled |
|---|---|---|---|---|---|
| A | A1.W300 | 0.903 | 0.929 | 124 | 156 |
| A | A1.W60 | 0.921 | 0.917 | 38 | 242 |
| A | A2.W300 | 0.909 | 0.919 | 22 | 258 |
| A | A2.W60 | 0.667 | 0.921 | 3 | 277 |
| I12 | A1.W300 | 0.483 | 0.607 | 689 | 150 |
| I12 | A1.W60 | 0.474 | 0.57 | 567 | 272 |
| I12 | A2.W300 | 0.469 | 0.583 | 573 | 266 |
| I12 | A2.W60 | 0.451 | 0.549 | 376 | 463 |
| I13 | A1.W300 | 0.368 | 0 | 19 | 1 |
| I13 | A1.W60 | 0.5 | 0.125 | 12 | 8 |
| I13 | A2.W300 | 0.385 | 0.286 | 13 | 7 |
| I13 | A2.W60 | 0 | 0.368 | 1 | 19 |
| I7 | A1.W300 | 0.5 | 0.545 | 8 | 11 |
| I7 | A1.W60 | 0.25 | 0.6 | 4 | 15 |
| I7 | A2.W300 |  | 0.526 |  | 19 |
| I7 | A2.W60 |  | 0.526 |  | 19 |
| I8 | A1.W300 | 0.531 | 0.506 | 420 | 245 |
| I8 | A1.W60 | 0.556 | 0.507 | 196 | 469 |
| I8 | A2.W300 | 0.479 | 0.529 | 94 | 571 |
| I8 | A2.W60 | 0.571 | 0.52 | 21 | 644 |
| I9 | A1.W300 | 0.421 | 0.553 | 560 | 161 |
| I9 | A1.W60 | 0.419 | 0.502 | 450 | 271 |
| I9 | A2.W300 | 0.415 | 0.519 | 478 | 243 |
| I9 | A2.W60 | 0.42 | 0.471 | 301 | 420 |

Makers get filled when they are wrong: Idea 9 filled signals win about 0.42 vs 0.47 to 0.55 unfilled; Strategy A
0.90 vs 0.92. Strategy A fill rates are low (1% to 44%).

### Top 10 Round 1 trials by ROC (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R1.A.I7.A1.W300 | 8 | 0.0619 | -0.7057 | 0.7463 | 2.913 | 0.0724 | 3.375 | -14.54 | 1.09 | 1 |
| R1.A.A.A2.W300 | 22 | 0.0607 | -0.0909 | 0.1735 | 5.2 | 0.0638 | 5.455 | 1.59 | 5.402 | 1 |
| R1.A.A.A1.W60 | 38 | 0.0583 | -0.0464 | 0.1385 | 5.074 | 0.0612 | 5.316 | 9.63 | 4.255 | 1 |
| R1.C4.b0.20-0.40 | 400 | 0.0452 | -0.1011 | 0.1924 | 1.47 | 0.0452 | 1.47 | 19.72 | 1.272 | 1 |
| R1.A.A.A1.W300 | 124 | 0.0316 | -0.0304 | 0.0838 | 2.768 | 0.0344 | 3 | 24.48 | 2.775 | 1 |
| R1.A.I13.A1.W60 | 12 | 0.0283 | -0.5343 | 0.569 | 1.375 | 0.0381 | 1.833 | -23.91 | 0.6293 | 1 |
| R1.A.I9.A2.W300 | 478 | 0.0222 | -0.0782 | 0.125 | 0.9025 | 0.0328 | 1.32 | -1.04 | 0.8958 | 1 |
| R1.A.I8.A1.W60 | 196 | 0.0189 | -0.0933 | 0.1312 | 1.032 | 0.0268 | 1.449 | -18.19 | 0.7161 | 1 |
| R1.C1.d0.05.s15.maker.settle | 764 | 0.0185 | -0.0364 | 0.0758 | 1.02 | 0.0258 | 1.412 | 32.23 | 1.103 | 1 |
| R1.A.I9.A2.W60 | 301 | 0.0092 | -0.1224 | 0.1331 | 0.3814 | 0.0195 | 0.804 | -31.49 | 0.3474 | 1 |

### Block summary

- A (maker execution of existing signals): best with >= 100 trades is Strategy A, limit at last trade, W 300 s:
  ROC +0.032 [-0.030, +0.084], 124 trades.
- B (fee bands, walk-forward): B1 -0.004 (100 trades); B2 13 trades.
- C1 (polymarket.com leads Kalshi): only maker + hold to settlement at d 0.05, s 15 is positive, +0.019
  [-0.036, +0.076], 764 trades; every H60/H300 exit is negative.
- C2 (CME): skipped, 1 mapped game.
- C3 (Kalshi own 5 c moves): every trial negative (best -0.025); no momentum or reversal edge.
- C4 (in-game band at kickoff + 20 min): longshot bias is strong below 0.20 (win 0.070 vs break-even 0.128,
  ROC -0.45); 0.20 to 0.40 is +0.045 [-0.101, +0.192]; 0.80 to 0.99 slightly negative.

### Correction after Round 1 (own 79 + broad search 54 = 133 trials; helpers not yet available)

Reality Check p for the best by t-stat (search:a_consensus_m3_pre_all): 0.361. DSR of that best:
3.78e-41 (project convention, report_book.deflated_sharpe; normal-returns version
3.72e-12; SR0 0.860 is inflated by consistently losing trials). Holm survivors:
none. Stop condition: not met.

IN-SAMPLE BEST, after 133 trials, not expected to persist: R1.A.I7.A1.W300, ROC 0.062
[-0.706, 0.746] on 8 trades.
