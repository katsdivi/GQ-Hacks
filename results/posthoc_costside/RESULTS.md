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


## Round 4

Run 2026-10-04 05:43 ET.

- Calm slots make pairs WORSE: in calm markets the second leg rarely fills (h 0.02: 216 pairs vs 613 orphans), so
  orphans dominate (ROC -0.036, CI below 0, both h).
- Passive orphan completion lifts pairs from 5,067 to 6,437 (+$962), but the orphans that still fail are the ones
  the market ran away from, and hedging them at the deadline costs more: orphans -$3,004 on 3,121; ROC -0.022, CI
  below 0. With calm slots too: -0.045.
- Lesson: the orphan is the adverse-selection signal itself; any rule that waits makes it worse, and any rule that
  avoids moves also avoids the fills that complete pairs.

### All Round 4 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R4.REQUOTE | 9558 | -0.0222 | -0.0257 | -0.0183 | -2.137 | -0.0163 | -1.559 | -2248 | -8.807 | 1 |
| R4.PAIRCALM.h0.03 | 674 | -0.0361 | -0.0582 | -0.015 | -3.063 | -0.0323 | -2.725 | -282.7 | -8.984 | 1 |
| R4.PAIRCALM.h0.02 | 829 | -0.0364 | -0.0578 | -0.0144 | -2.983 | -0.0325 | -2.654 | -349.8 | -8.129 | 1 |
| R4.REQUOTECALM | 829 | -0.045 | -0.0623 | -0.028 | -3.755 | -0.0409 | -3.392 | -362.7 | -8.953 | 1 |

### Cumulative correction after Round 4

Trials: own 110 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 257. Reality Check p for the best by t-stat
(patterns:P3-08): 0.328. DSR of that best: 2.81e-32 (project convention;
normal-returns version 2.61e-10). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 257 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.


## Round 5

Run 2026-10-04 05:44 ET.

- Pre-game pairs lose even when both legs fill (h 0.01: 267 pairs -$24; orphans -$333): Kalshi's two markets
  carry about a 1 cent overround pre-game, so a pair bought 1 cent under each last trade still costs about 0.99
  plus maker fees. h 0.02 almost never fills.
- Stop-loss exits hurt both entries (all CIs below 0, worse at the tighter stop): prices that fall 10 to 20 cents
  after a fill recover often enough that cutting them sells low.
- polymarket.com-anchored one-sided maker quotes: -0.045 [-0.112, +0.028]; the fills are adversely selected like
  every other in-game maker fill.

## Search stopped (2026-10-04 05:45 ET): out of genuinely new mechanisms

Every mechanism on Divi's list has now been tried by this branch, the two helpers or the broad search: maker
execution of every signal, two-sided spread capture (maker helper) and pairs with three orphan treatments,
passive completion and calm filters, closing-line and pre-game drift, longshot bias by band, phase and league,
slate correlation and time-slot liquidity (patterns helper), polymarket.com leadership by volatility regime, fee
bands and fee rounding, take-profit and stop-loss exits, consensus and online weighting (broad search),
two-market complement arbitrage and polymarket.com-anchored quoting. CME leadership could not be tested (1 mapped
training game). Remaining variations would be the same grids made finer, which the brief rules out.

**Final: 5 rounds, 117 own trials, 264 cumulative trials (own 117 + broad search 54 + maker helper 36 + patterns
helper 57). No trial meets the stop condition. Reality Check p for the best of all 264 (patterns P3-08) = 0.33;
Holm survivors: none.** Best own trial with >= 100 trades: R2.VOL.low.maker (polymarket.com lead, maker entry,
calm Kalshi markets), ROC +0.050 [-0.008, +0.107], 687 trades; the same fills with 100-contract orders +0.051
[-0.007, +0.108]. Neither clears 0, and against 264 trials neither is distinguishable from the best of noise.

What it implies: on the training data, Kalshi football prices already reflect the information in every source we
have (polymarket.com, sportsbook lines, ESPN, taker flow, own price history) to within the cost of trading, and
passive execution does not escape that cost because the fills it gets are adversely selected. There is no
recommendation for a holdout test ("run costside holdout" not warranted).

### All Round 5 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R5.PAIRPRE.h0.01 | 1705 | -0.0218 | -0.0301 | -0.0131 | -2.095 | -0.0169 | -1.616 | -432.5 | -8.37 | 1 |
| R5.PAIRPRE.h0.02 | 155 | -0.0315 | -0.0556 | -0.0035 | -3.061 | -0.0272 | -2.632 | -77.33 | -5.205 | 1 |
| R5.ANCHOR | 695 | -0.0454 | -0.1116 | 0.0276 | -2.14 | -0.0374 | -1.748 | -194 | -2.56 | 1 |
| R5.SL.R2.VOL.low.maker.sl0.2 | 687 | -0.0482 | -0.0882 | -0.0061 | -2.665 | -0.0416 | -2.284 | -227.7 | -3.67 | 1 |
| R5.SL.R1.A.I12.A1.W300.sl0.2 | 689 | -0.0554 | -0.1026 | -0.0059 | -2.659 | -0.0475 | -2.264 | -227.9 | -3.458 | 1 |
| R5.SL.R1.A.I12.A1.W300.sl0.1 | 689 | -0.088 | -0.1214 | -0.052 | -4.226 | -0.0804 | -3.831 | -335.9 | -7.676 | 1 |
| R5.SL.R2.VOL.low.maker.sl0.1 | 687 | -0.0917 | -0.1206 | -0.0632 | -5.071 | -0.0854 | -4.69 | -392.3 | -7.921 | 1 |

### Cumulative correction after Round 5

Trials: own 117 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 264. Reality Check p for the best by t-stat
(patterns:P3-08): 0.330. DSR of that best: 1.29e-31 (project convention;
normal-returns version 4.02e-10). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 264 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.


## Round 6

Run 2026-10-04 05:50 ET.

- BIG prints: neither following nor fading the first large print (> p99 and >= 1,000 contracts) has edge; all
  four CIs include or sit below 0, win rate below break-even in every trial.
- IMB: following trailing aggressor imbalance loses at every horizon (taker CIs below 0 at 10, 60, 120 s); fading
  it also loses. Aggressor flow in-game carries no information beyond the price at these horizons.
- GAP: price moves after long no-trade gaps are rare (4 to 58 trades) and negative.
- Kalshi in-game microstructure (size, aggressor side, gaps) is ruled out as a signal source on this data.

### All Round 6 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R6.BIG.follow.maker | 611 | -0.0302 | -0.1074 | 0.0456 | -1.428 | -0.0223 | -1.049 | -131.6 | -1.573 | 1 |
| R6.BIG.fade.maker | 626 | -0.0371 | -0.0993 | 0.0286 | -1.921 | -0.0299 | -1.538 | -163.5 | -2.003 | 1 |
| R6.IMB.fade.w60.taker | 904 | -0.0401 | -0.087 | 0.0027 | -2.412 | -0.0401 | -2.412 | -261.4 | -2.957 | 1 |
| R6.BIG.follow.taker | 908 | -0.0407 | -0.0989 | 0.0139 | -2.023 | -0.0407 | -2.023 | -228.3 | -2.791 | 1 |
| R6.IMB.follow.w10.maker | 633 | -0.0515 | -0.1279 | 0.0286 | -2.241 | -0.0431 | -1.863 | -186.7 | -2.626 | 1 |
| R6.IMB.follow.w60.maker | 622 | -0.0571 | -0.1392 | 0.028 | -2.324 | -0.0484 | -1.95 | -190.1 | -2.635 | 1 |
| R6.IMB.fade.w60.maker | 639 | -0.0652 | -0.1247 | -0.0079 | -3.809 | -0.0591 | -3.432 | -286.4 | -3.733 | 1 |
| R6.BIG.fade.taker | 890 | -0.066 | -0.1208 | -0.0137 | -3.559 | -0.066 | -3.559 | -361.9 | -4.425 | 1 |
| R6.IMB.follow.w120.maker | 609 | -0.0671 | -0.148 | 0.0187 | -2.639 | -0.0584 | -2.276 | -205.6 | -2.713 | 1 |
| R6.IMB.follow.w10.taker | 948 | -0.0786 | -0.1383 | -0.0197 | -3.548 | -0.0786 | -3.548 | -381.3 | -4.499 | 1 |
| R6.IMB.follow.w60.taker | 950 | -0.0792 | -0.1392 | -0.02 | -3.425 | -0.0792 | -3.425 | -370.1 | -4.946 | 1 |
| R6.GAP.g300.taker | 16 | -0.0856 | -0.4771 | 0.3452 | -4.681 | -0.0856 | -4.681 | -28.77 | -3.92 | 1 |
| R6.IMB.follow.w120.taker | 949 | -0.1012 | -0.1682 | -0.0337 | -4.121 | -0.1012 | -4.121 | -435.4 | -5.067 | 1 |
| R6.GAP.g120.taker | 58 | -0.1522 | -0.3781 | 0.0694 | -7.738 | -0.1522 | -7.738 | -82.34 | -6.058 | 1 |
| R6.GAP.g120.maker | 24 | -0.1913 | -0.5062 | 0.0552 | -9.858 | -0.1863 | -9.542 | -40.74 | -9.064 | 1 |
| R6.GAP.g300.maker | 4 | -0.3311 | -1 | 0.4032 | -12.38 | -0.3243 | -12 | 0 | -6.725 | 1 |

### Cumulative correction after Round 6

Trials: own 133 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 280. Reality Check p for the best by t-stat
(patterns:P3-08): 0.342. DSR of that best: 6.32e-30 (project convention;
normal-returns version 1.21e-09). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 280 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.


## Round 7

Run 2026-10-04 05:51 ET. Strict ESPN defect rule dropped 549 of 1,024 test-week games (any play outside
[kickoff, kickoff + 6 h] or more than 5 min out of order); 475 games used; 0 mapping failures.

- TO (INT, fumble, turnover on downs, missed FG): fading a >= 3 c Kalshi reaction loses (taker -0.128, CI below
  0); buying the gaining team after a small reaction is flat to negative (-0.024 [-0.094, +0.044], win 0.608 vs
  break-even 0.623). Kalshi prices possession changes correctly within a minute.
- HALF (>= 10 c 2nd-quarter swing): following loses (-0.087 / -0.124); fading is +0.065 [-0.222, +0.350] on 95
  trades taker, but the maker version is negative and the sample is small. No edge.
- ESPN non-scoring game state is ruled out as a signal at a 60 s known-time delay.

### All Round 7 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R7.HALF.fade.taker | 95 | 0.0645 | -0.2223 | 0.3502 | 1.849 | 0.0645 | 1.849 | -25.2 | 1.439 | 1 |
| R7.TO.follow.taker | 301 | -0.0238 | -0.0938 | 0.0441 | -1.483 | -0.0238 | -1.483 | -85.25 | -1.228 | 1 |
| R7.TO.follow.maker | 204 | -0.0374 | -0.1351 | 0.0546 | -2.283 | -0.0323 | -1.961 | -86.93 | -1.739 | 1 |
| R7.HALF.follow.taker | 90 | -0.0866 | -0.2018 | 0.0241 | -6.428 | -0.0866 | -6.428 | -86.32 | -4.787 | 1 |
| R7.TO.fade.maker | 278 | -0.0913 | -0.2167 | 0.0297 | -3.595 | -0.0829 | -3.234 | -143.3 | -3.327 | 1 |
| R7.HALF.fade.maker | 56 | -0.0948 | -0.4554 | 0.2508 | -2.618 | -0.0838 | -2.286 | -51.06 | -2.027 | 1 |
| R7.HALF.follow.maker | 73 | -0.1236 | -0.2592 | 0.0085 | -8.89 | -0.1194 | -8.548 | -90.85 | -6.165 | 1 |
| R7.TO.fade.taker | 332 | -0.1284 | -0.2354 | -0.0203 | -5.212 | -0.1284 | -5.212 | -215.6 | -5.125 | 1 |

### Cumulative correction after Round 7

Trials: own 141 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 288. Reality Check p for the best by t-stat
(patterns:P3-08): 0.353. DSR of that best: 2.75e-29 (project convention;
normal-returns version 1.84e-09). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 288 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.


## Round 8

Run 2026-10-04 05:52 ET.

- A team's recent Kalshi closing errors carry at most a weak signal: buying against a team Kalshi OVERPRICED in
  its last 3 games, with maker entry, is +0.068 [-0.024, +0.155] on 299 trades (win 0.600 vs break-even 0.562);
  the taker version is +0.015 and k 1 is negative. "Under" (buy the recently underpriced team) is flat to
  negative. CIs all include 0.

### All Round 8 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R8.PRIOR.over.k3.maker | 299 | 0.0675 | -0.0239 | 0.1551 | 3.797 | 0.0753 | 4.204 | 74.42 | 2.573 | 1 |
| R8.PRIOR.under.k3.maker | 322 | 0.0248 | -0.0542 | 0.1055 | 1.414 | 0.0322 | 1.82 | 6.72 | 1.317 | 1 |
| R8.PRIOR.over.k3.taker | 476 | 0.0153 | -0.0503 | 0.0843 | 0.8935 | 0.0153 | 0.8935 | 1.53 | 0.7229 | 1 |
| R8.PRIOR.over.k1.taker | 618 | -0.0075 | -0.0707 | 0.0562 | -0.421 | -0.0075 | -0.421 | -69.33 | -0.3565 | 1 |
| R8.PRIOR.under.k3.taker | 492 | -0.0158 | -0.0798 | 0.0464 | -0.9311 | -0.0158 | -0.9311 | -85.35 | -0.9928 | 1 |
| R8.PRIOR.under.k1.taker | 637 | -0.0327 | -0.0905 | 0.0267 | -1.901 | -0.0327 | -1.901 | -160.3 | -1.739 | 1 |

### Cumulative correction after Round 8

Trials: own 147 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 294. Reality Check p for the best by t-stat
(patterns:P3-08): 0.367. DSR of that best: 3.57e-29 (project convention;
normal-returns version 1.99e-09). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 294 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.


## Round 9

Run 2026-10-04 05:53 ET.

- Every independent filter keeps R2.VOL.low.maker in the same +0.04 to +0.08 range with a CI that still includes
  0 (best: ESPN-calm subset +0.077 [-0.024, +0.180] on 243 trades). The filters only shrink the sample; none
  separates winners from losers. These are subsets of the same fills, so they are not independent evidence.
- polymarket.com agreement makes the Round 8 prior signal worse (-0.036 on 112 trades).

### All Round 9 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R9.VOLLOW.espncalm | 243 | 0.0769 | -0.0239 | 0.1798 | 4.201 | 0.0846 | 4.593 | 59.21 | 3.714 | 1 |
| R9.VOLLOW.prior | 365 | 0.0539 | -0.0244 | 0.1248 | 3.099 | 0.0609 | 3.474 | 71.97 | 2.991 | 1 |
| R9.VOLLOW.imb | 559 | 0.049 | -0.0175 | 0.1139 | 2.672 | 0.0563 | 3.054 | 105.1 | 3.38 | 1 |
| R9.VOLLOW.regular | 651 | 0.0416 | -0.0185 | 0.1025 | 2.292 | 0.0488 | 2.671 | 104.6 | 3.015 | 1 |
| R9.PRIOR.pm | 112 | -0.0361 | -0.1884 | 0.1081 | -1.939 | -0.029 | -1.545 | -59.53 | -1.071 | 1 |

### Cumulative correction after Round 9

Trials: own 152 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 299. Reality Check p for the best by t-stat
(patterns:P3-08): 0.380. DSR of that best: 1.70e-29 (project convention;
normal-returns version 1.61e-09). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 299 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.


## Round 10

Run 2026-10-04 05:54 ET.

- Elo strength from past outcomes disagrees with Kalshi mostly on underdogs (mean fill about 0.26 to 0.30) and
  loses on every line: taker -0.067 / -0.070, maker -0.039 / -0.041, win rate below break-even in all four. Kalshi
  pre-game prices already contain everything a results-only rating knows.

## Search status after Round 10 (2026-10-04 05:55 ET): new mechanisms exhausted on the available data

The Round 5 "Search stopped" section above was superseded when Divi resumed the search; this section replaces it.

10 rounds, 156 own trials; cumulative 303 trials (own 156 + broad search 54 + maker helper 36 + patterns helper
57). No trial meets the stop condition. Reality Check p for the best of all 303 (patterns P3-08) = 0.38; Holm
survivors: none; DSR of the best: 3.6e-29 (project convention), 2.0e-09 (normal returns).

Every mechanism in the brief's list has been tested here or in another branch, except those the data cannot
support. Further rounds would be finer grids or re-filtered subsets of the same fills (which the scoreboard
penalises and which would not be independent evidence). To go further, these data would be needed:

1. **CME event-contract trades/quotes for the training games** (only 1 of 32 training CME games maps to Kalshi
   ticks): needed for CME-leads-Kalshi, the project's original hypothesis, on training data.
2. **Full Kalshi order-book depth (not trades only) for training games**: queue position and resting size are
   required to model maker fills honestly; the trade-through rule cannot separate queue luck from adverse selection,
   which is what kills every maker strategy here.
3. **Kalshi markets from listing, not from kickoff - 2 h**: the first-hour-after-open and long-horizon pre-game
   drift tests need the early life of each market.
4. **Timestamped news and injury reports (and line-move timestamps from a sportsbook feed)**: the only information
   source plausibly faster than Kalshi pre-game; nflverse lines carry no timestamps (Idea 13).
5. **Clean in-game event timestamps** (official play-by-play with reliable wallclocks): 549 of 1,024 test-week
   games fail the ESPN defect rule, so in-game state tests run on half the sample.
6. **Kalshi's first-party maker fee schedule and any volume rebates**: the maker lines here bracket it (0 and
   0.0175 x C x P(1-P)); a rebate would change the passive-pair economics (pairs alone make +1.8 c per pair).

### All Round 10 trials (primary line; alt = maker0 for maker trials, else same)

| trial | trades | roc | roc_lo | roc_hi | c_per_contract | alt_roc | alt_c_per_contract | excl5_pnl | sharpe_x365 | holm_p |
|---|---|---|---|---|---|---|---|---|---|---|
| R10.ELO.e0.05.maker | 436 | -0.039 | -0.17 | 0.0986 | -1.142 | -0.0262 | -0.7569 | -91.94 | -1.207 | 1 |
| R10.ELO.e0.1.maker | 341 | -0.0412 | -0.1993 | 0.1312 | -1.065 | -0.0276 | -0.7038 | -78.49 | -1.041 | 1 |
| R10.ELO.e0.05.taker | 691 | -0.0668 | -0.1743 | 0.0387 | -2.003 | -0.0668 | -2.003 | -182.8 | -2.497 | 1 |
| R10.ELO.e0.1.taker | 544 | -0.0703 | -0.1966 | 0.0601 | -1.855 | -0.0703 | -1.855 | -145.2 | -2.405 | 1 |

### Cumulative correction after Round 10

Trials: own 156 + external (search 54 (daily P&L used); maker 36 (daily P&L used); patterns 57 (daily P&L used)) = 303. Reality Check p for the best by t-stat
(patterns:P3-08): 0.382. DSR of that best: 3.62e-29 (project convention;
normal-returns version 1.99e-09). Holm survivors at 0.05: none.
Stop candidates (own trials meeting CI > 0, >= 100 trades, excl. top 5 > 0): none.
Stop condition met: False.

IN-SAMPLE BEST (own trials), after 303 trials, not expected to persist: R2.CONS.A2.W300, ROC
0.135 [-0.075, 0.349] on 17 trades.
