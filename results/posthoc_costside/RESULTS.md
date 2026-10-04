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


## Round 2

Run 2026-10-04 05:39 ET. (The Round 2 spec header says 05:58 ET; that was a typo, the spec commit 2d0c0e0 is at
05:38 ET, before this run.)

- ARB: when the two Kalshi markets' last trades sum to <= 0.95 or 0.97, buying both at trade + 1 c loses -0.058 and
  -0.060 ROC (CIs below 0): the sum is a stale artifact of last trades, and both legs pay the spread and fees.
  Pairs filled 98%; orphans 24 and 41.
- CONS (search consensus + maker): small samples (4 to 64 trades); best with >= 50 trades A1 W300 +0.044
  [-0.041, +0.125].
- VOL: the polymarket.com lead with maker entry in LOW Kalshi volatility is the best own trial so far: ROC +0.050
  [-0.008, +0.107], 687 trades, excl. top 5 +$147; the high-volatility half is flat to negative. The CI still
  includes 0.
- TP: take-profit exits hurt every entry (all ROC <= 0; tp 0.03 clearly negative): cutting winners early gives
  up the settlement payoff while losers still run.
- External trials now include the maker helper (36) and patterns helper (57), both finished, daily P&L used.

### All Round 2 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R2.CONS.A2.W300 | 17 | 0.1352 | -0.075 | 0.349 | 9.806 | 0.1401 | 10.12 | -2.73 | 6.056 | 1 |
| R2.CONS.A1.W60 | 26 | 0.1243 | -0.0049 | 0.2522 | 10.21 | 0.1278 | 10.46 | 7.74 | 8.201 | 1 |
| R2.VOL.low.maker | 687 | 0.0505 | -0.0084 | 0.107 | 2.789 | 0.0577 | 3.17 | 147 | 3.513 | 1 |
| R2.CONS.A1.W300 | 64 | 0.0444 | -0.0413 | 0.1247 | 3.786 | 0.0472 | 4.016 | 5.33 | 3.719 | 1 |
| R2.VOL.low.taker | 756 | 0.0063 | -0.046 | 0.0613 | 0.3675 | 0.0063 | 0.3675 | -16.05 | 0.5956 | 1 |
| R2.TP.I12.tp0.06 | 689 | -0.0021 | -0.0341 | 0.0285 | -0.101 | 0.0062 | 0.2939 | -46.5 | -0.2788 | 1 |
| R2.VOL.high.maker | 449 | -0.0047 | -0.0832 | 0.0745 | -0.2648 | 0.0028 | 0.1581 | -54.05 | -0.231 | 1 |
| R2.TP.I9.tp0.06 | 478 | -0.0063 | -0.0454 | 0.0329 | -0.2544 | 0.0041 | 0.1632 | -45.45 | -0.5555 | 1 |
| R2.TP.C1.tp0.06 | 764 | -0.0298 | -0.0606 | -0.0005 | -1.642 | -0.0229 | -1.25 | -157.7 | -3.45 | 1 |
| R2.TP.I9.tp0.03 | 478 | -0.0357 | -0.0634 | -0.0073 | -1.45 | -0.0257 | -1.033 | -95.94 | -4.365 | 1 |
| R2.TP.I12.tp0.03 | 689 | -0.0374 | -0.0635 | -0.0133 | -1.797 | -0.0294 | -1.402 | -157.3 | -5.34 | 1 |
| R2.TP.C1.tp0.03 | 764 | -0.0416 | -0.0647 | -0.02 | -2.29 | -0.0347 | -1.898 | -205.2 | -5.773 | 1 |
| R2.ARB.S0.95 | 1492 | -0.0578 | -0.0639 | -0.0517 | -3.057 | -0.0578 | -3.057 | -485.9 | -13.05 | 1 |
| R2.ARB.S0.97 | 1733 | -0.0597 | -0.0656 | -0.0536 | -3.143 | -0.0597 | -3.143 | -579.8 | -11.98 | 1 |
| R2.VOL.high.taker | 469 | -0.0655 | -0.1362 | 0.0068 | -3.877 | -0.0655 | -3.877 | -221.2 | -3.439 | 1 |
| R2.CONS.A2.W60 | 4 | -0.3223 | -1 | 0.0965 | -23.77 | -0.3197 | -23.5 | 0 | -10.74 | 1 |

### Cumulative correction after Round 2

Trials: own 95 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 242. Reality Check p for the best by t-stat
(patterns:P3-08): 0.324. DSR of that best: 2.17e-32 (project convention;
normal-returns version 2.43e-10). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 242 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.


## Round 3

Run 2026-10-04 05:41 ET.

- PAIR: of 9,558 slots with a fill, 5,067 filled both legs (pairs) and 4,491 only one (orphans). Pairs made
  +$891.96 (about +1.8 c per contract-pair after maker175 fees); orphans lost -$1,694.06 even with an immediate
  taker hedge. Orphan adverse selection: orphans win 0.393 vs mean fill 0.461 (a one-sided fill means the price
  moved against it). All three orphan treatments are negative with CIs below 0 (HEDGENOW -0.009, HEDGEDL -0.033,
  CUT -0.040). This confirms the maker helper's lead: the pair economics are positive, the orphans destroy them.
- FEE: 100-contract orders barely change anything (VOL low maker +0.050 to +0.051); fee rounding is not the
  constraint.
- FAV: favourites 0.80 to 0.90 with maker entry +0.031 [-0.056, +0.111] on 87 trades (below 100).
- VOLX: the calm filter does NOT generalise: I12 is worse in calm markets (-0.012) than in volatile ones (+0.017);
  I9 calm +0.092 on 118 trades with a wide CI.

### All Round 3 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R3.VOLX.I9.low | 118 | 0.0916 | -0.1033 | 0.2849 | 3.769 | 0.1021 | 4.161 | 1.8 | 3.752 | 1 |
| R3.FEE.R2.VOL.low.maker | 687 | 0.0514 | -0.0074 | 0.108 | 2.84 | 0.0577 | 3.17 | 150.5 | 3.574 | 1 |
| R3.FEE.R1.A.A.A1.W300 | 124 | 0.0321 | -0.03 | 0.0843 | 2.807 | 0.0344 | 3 | 24.94 | 2.813 | 1 |
| R3.FAV | 87 | 0.031 | -0.0563 | 0.1112 | 2.629 | 0.0343 | 2.897 | 13.02 | 1.861 | 1 |
| R3.FEE.R1.C1.d0.05.s15.maker.settle | 764 | 0.0195 | -0.0355 | 0.0768 | 1.072 | 0.0258 | 1.412 | 36.15 | 1.158 | 1 |
| R3.VOLX.I12.high | 382 | 0.017 | -0.079 | 0.1114 | 0.8387 | 0.0259 | 1.264 | -9.92 | 0.7014 | 1 |
| R3.VOLX.I9.high | 360 | -0.0009 | -0.1143 | 0.1206 | -0.0369 | 0.0097 | 0.3889 | -43.89 | -0.0303 | 1 |
| R3.PAIR.HEDGENOW | 9558 | -0.0087 | -0.012 | -0.0053 | -0.8392 | -0.0032 | -0.303 | -1020 | -5.687 | 1 |
| R3.VOLX.I12.low | 307 | -0.0115 | -0.107 | 0.0916 | -0.5326 | -0.0038 | -0.1759 | -60.44 | -0.5006 | 1 |
| R3.PAIR.HEDGEDL | 9558 | -0.0327 | -0.0363 | -0.0287 | -3.14 | -0.0273 | -2.604 | -3224 | -9.964 | 1 |
| R3.PAIR.CUT | 9558 | -0.0403 | -0.0435 | -0.037 | -2.975 | -0.0332 | -2.439 | -2901 | -11.04 | 1 |

### Cumulative correction after Round 3

Trials: own 106 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 253. Reality Check p for the best by t-stat
(patterns:P3-08): 0.327. DSR of that best: 1.15e-32 (project convention;
normal-returns version 2.03e-10). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 253 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.
