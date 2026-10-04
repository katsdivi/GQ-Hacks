# Post-hoc leadlag2 results

Label: post-hoc, exploratory; training only; walk-forward test weeks; holdout not run.

## Round 1 (spec 55d151c, code 62b43e8): information share, polymarket.com vs Kalshi, training

Data: 962 B training games with polymarket.com ticks loaded; windows with >= 50 price changes on both venues enter the
VECM. Per-game shares: r1_game_shares.csv (lags and shares only, no prices).

Descriptive (positive lag = polymarket.com leads; IS = Hasbrouck information share of polymarket.com, midpoint of
both orderings; GG = Gonzalo-Granger component share of polymarket.com):

| window | games | IS median [IQR] | IS >= 0.6 | IS <= 0.4 | GG median | xcorr lag median | lag > 0 | lag < 0 |
|---|---|---|---|---|---|---|---|---|
| in-game (ko + 20 min to + 4 h) | 779 | 0.037 [0.013, 0.105] | 0.9% | 97.0% | 0.156 | -10 s | 10.1% | 86.3% |
| pre-game (ko - 2 h to ko - 5 min) | 260 | 0.668 [0.558, 0.780] | 66.2% | 5.0% | 0.769 | -10 s | 40.4% | 56.2% |
| early in-game (ko + 20 to + 80 min) | 509 | 0.046 | 0.2% | 98.4% | 0.175 | -10 s | | |
| late in-game (ko + 80 min to + 4 h) | 668 | 0.030 | 0.9% | 96.7% | 0.131 | -10 s | | |

- In-game, Kalshi carries about 96% of price discovery and polymarket.com follows by about 10 s (VECM: polymarket.com
  error-correction coefficient median -0.115 per 5 s, Kalshi +0.024). CFB and NFL alike (in-game IS 0.043 and 0.030).
- Pre-game (last 2 h), the reverse: polymarket.com carries about two thirds of price discovery (IS 0.668, GG 0.769) on
  the 260 games with enough pre-game activity on both venues. The xcorr argmax lag is still -10 s, so the leadership is
  in the slow error-correction, not in the fastest moves.
- Signed flow: Kalshi flow predicts later polymarket.com price changes (median corr 0.016 at 10 s); polymarket.com flow
  does not predict Kalshi (0.001).
- Predictability (D4): within game, early vs late in-game IS Spearman 0.229 (475 games); walk-forward league mean IS
  vs game IS Spearman 0.056 (743 games), league means range 0.049 to 0.135, never near 0.6.

Trading (24 trials, test weeks only). Gates E and W almost never open, because polymarket.com almost never leads
in-game (gate E: 1 game; gate W: 0). The placebo gate (Kalshi leads, IS <= 0.4) opens in most games:

| trial | trades | games | roc | roc_lo | roc_hi | c_per_contract | alt_roc | excl5_roc | holm_p |
|---|---|---|---|---|---|---|---|---|---|
| LL2.R1.P.g4.maker.settle | 441 | 441 | -0.0125 | -0.0855 | 0.0678 | -0.6451 | -0.0052 | -0.031 | 1 |
| LL2.R1.P.g4.taker.settle | 446 | 446 | -0.016 | -0.0899 | 0.0562 | -0.8904 | -0.016 | -0.0326 | 1 |
| LL2.R1.P.g2.taker.settle | 480 | 480 | -0.0335 | -0.1054 | 0.0361 | -1.775 | -0.0335 | -0.0508 | 1 |
| LL2.R1.P.g2.maker.settle | 477 | 477 | -0.0362 | -0.1078 | 0.0383 | -1.823 | -0.0292 | -0.0547 | 1 |
| LL2.R1.P.g2.maker.H300 | 7670 | 477 | -0.0524 | -0.0569 | -0.0478 | -2.785 | -0.0463 | -0.0539 | 1 |
| LL2.R1.P.g4.maker.H300 | 4490 | 441 | -0.061 | -0.0676 | -0.0538 | -3.111 | -0.054 | -0.0634 | 1 |
| LL2.R1.P.g2.taker.H300 | 8249 | 480 | -0.0761 | -0.0805 | -0.0718 | -4.127 | -0.0761 | -0.0775 | 1 |
| LL2.R1.P.g4.taker.H300 | 4823 | 446 | -0.0851 | -0.0918 | -0.078 | -4.492 | -0.0851 | -0.0871 | 1 |
| LL2.R1.E.g2.taker.H300 | 1 | 1 | -0.7273 |  |  | -2.4 | -0.7273 |  | 1 |
| LL2.R1.E.g2.maker.H300 | 1 | 1 | -0.7805 |  |  | -3.2 | -0.775 |  | 1 |
| LL2.R1.E.g2.maker.settle | 1 | 1 | -1 |  |  | -4.1 | -1 |  | 1 |
| LL2.R1.E.g2.taker.settle | 1 | 1 | -1 |  |  | -3.3 | -1 |  | 1 |
| LL2.R1.E.g4.taker.H300 | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.E.g4.taker.settle | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.E.g4.maker.H300 | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.E.g4.maker.settle | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.W.g2.taker.H300 | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.W.g2.taker.settle | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.W.g2.maker.H300 | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.W.g2.maker.settle | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.W.g4.taker.H300 | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.W.g4.taker.settle | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.W.g4.maker.H300 | 0 | 0 |  |  |  |  |  |  | 1 |
| LL2.R1.W.g4.maker.settle | 0 | 0 |  |  |  |  |  |  | 1 |

Cumulative correction (correction.json): 463 trials (439 earlier + 24 here), Reality Check p =
0.4585 (best by t: patterns:P3-08), DSR 1.54e-26 (normal returns 1.11e-08),
Holm survivors: none. Stop condition: not met.

Verdict R1: there is no in-game polymarket.com lead to trade on Kalshi; Kalshi is the in-game leader. The only window
where polymarket.com leads is pre-game, which Round 2 tests.

## Round 3 (spec a815df2): CME vs Kalshi in-game, descriptive only

Data: CME map from branch data-cme-train 2126c45 (10 NFL playoff games, Jan 10 to 18, 2026, the only training
games with both CME quotes and Kalshi trades); CME 1 s BBO mids, Kalshi last trades, 1 s grid, in-game window
[kickoff + 20 min, kickoff + 4 h] clipped to the CME data start (LA at CAR: 51 min of overlap; CME trades start
mid-game). 10 games < 30, so by the spec there are no trading trials and no trials are added. Per-game table:
r3_cme_games.csv; placebo pairs: r3_cme_placebo.csv (lags and shares only, no prices).

| measure | result |
|---|---|
| xcorr argmax lag (positive = CME leads), median | -4 s; CME leads in 1 of 10 games, Kalshi in 9 |
| unrelated-game placebo pairs (88, aligned on time since kickoff), median lag | -1 s (51% negative); Mann-Whitney real vs placebo p = 0.16 |
| CME Hasbrouck information share (VECM, 1 s), median | 0.030 (GG component share 0.194) |
| Kalshi response to CME 3 c jumps (660 jumps), median of game medians | 0.5 s, 64% covered within 60 s |
| CME response to Kalshi 3 c jumps (1,449 jumps), median of game medians | 6.5 s, 53% covered |
| price changes on the 1 s grid | CME 6,609, Kalshi 40,676 |

Reading: on the training games where both exist, Kalshi leads CME, not the reverse. Kalshi has about 6 times as
many price changes, about 97% of the information share, and responds to CME jumps within about a second, while CME
takes about 6.5 s to follow Kalshi's. One game (SF at SEA) leans the other way (CME IS 0.48, lag +9 s). The
pre-registered hypothesis direction (CME leads Kalshi) is not supported on training, with the caveat of 10 games.


## Round 2 (spec 5a02d77, fallback amendment dd7ab60, code f2d3b69): pre-game lead-lag, existing files

Run 07:18 ET on the existing files (the data-fullhist marker never appeared before this agent's 08:00 stop), so
W = 30 min only, 16 trials, test weeks only. 962 B training games; both venues trade over a median 2.0 h before
kickoff (p10 1.6 h).

| trial | trades | games | roc | roc_lo | roc_hi | c_per_contract | alt_roc | excl5_roc | holm_p |
|---|---|---|---|---|---|---|---|---|---|
| LL2.R2.pm.W30.d4.maker.settle | 11 | 11 | 0.6093 | -0.0427 | 1.269 | 27.54 | 0.626 | -0.0161 | 1 |
| LL2.R2.pm.W30.d4.taker.settle | 22 | 22 | 0.0868 | -0.3163 | 0.5463 | 4.354 | 0.0868 | -0.236 | 1 |
| LL2.R2.k.W30.d2.maker.settle | 498 | 498 | 0.0174 | -0.0582 | 0.0953 | 0.8759 | 0.0258 | 0.0001 | 1 |
| LL2.R2.pm.W30.d2.maker.settle | 387 | 387 | -0.0264 | -0.1142 | 0.0577 | -1.315 | -0.0182 | -0.0476 | 1 |
| LL2.R2.k.W30.d2.taker.settle | 574 | 574 | -0.0268 | -0.0956 | 0.039 | -1.429 | -0.0268 | -0.0409 | 1 |
| LL2.R2.pm.W30.d4.maker.ko | 11 | 11 | -0.0473 | -0.065 | -0.0294 | -2.136 | -0.0374 | -0.0665 | 1 |
| LL2.R2.pm.W30.d2.maker.ko | 387 | 387 | -0.0536 | -0.0567 | -0.0504 | -2.674 | -0.0457 | -0.0549 | 1 |
| LL2.R2.k.W30.d4.maker.ko | 18 | 18 | -0.0567 | -0.0715 | -0.0424 | -3.139 | -0.0485 | -0.0714 | 1 |
| LL2.R2.k.W30.d2.maker.ko | 498 | 498 | -0.0609 | -0.0646 | -0.0573 | -3.06 | -0.0532 | -0.0625 | 1 |
| LL2.R2.pm.W30.d2.taker.settle | 490 | 490 | -0.0692 | -0.1474 | 0.0045 | -3.61 | -0.0692 | -0.085 | 1 |
| LL2.R2.pm.W30.d2.taker.ko | 490 | 490 | -0.0877 | -0.0917 | -0.084 | -4.577 | -0.0877 | -0.0886 | 1 |
| LL2.R2.pm.W30.d4.taker.ko | 22 | 22 | -0.0892 | -0.1034 | -0.0766 | -4.477 | -0.0892 | -0.1017 | 1 |
| LL2.R2.k.W30.d4.taker.ko | 25 | 25 | -0.0913 | -0.1037 | -0.08 | -5.352 | -0.0913 | -0.1009 | 1 |
| LL2.R2.k.W30.d2.taker.ko | 574 | 574 | -0.0929 | -0.0965 | -0.0893 | -4.945 | -0.0929 | -0.0937 | 1 |
| LL2.R2.k.W30.d4.maker.settle | 18 | 18 | -0.3973 | -0.7863 | -0.0093 | -21.98 | -0.3921 | -0.8568 | 1 |
| LL2.R2.k.W30.d4.taker.settle | 25 | 25 | -0.4542 | -0.7329 | -0.1484 | -26.63 | -0.4542 | -0.7436 | 1 |

- pm-leads (polymarket.com moved >= d over 30 min while Kalshi moved < d/2): at d = 2 c, 387 to 490 trades, all four
  cells negative (-1.3 to -4.6 c per contract); at d = 4 c only 11 to 22 trades (pre-game, the two venues rarely
  disagree by 4 c), point estimates +0.09 and +0.61 ROC held to settlement with CIs from -0.32 and -0.04.
- The Kalshi-leads placebo is no worse at d = 2 c (maker, settle +0.017). Exits at kickoff - 5 min lose 2 to 5 c per
  contract in every cell (spread and fees on a round trip in a slowly drifting pre-game market).

Cumulative correction (correction.json): 479 trials (439 + 24 R1 + 16 R2), Reality Check p =
0.468 (best by t: patterns:P3-08), DSR 1.53e-27 (normal 5.78e-09),
Holm survivors: none. Stop condition: not met.

Rounds not run: the full-history version of R2 (W 120 min, 32 trials) did not run, and Round 4 was cancelled by
Divi (no news/line data purchase). Round 3 stayed descriptive (10 to 14 games < 30), and the Kalshi-leads-CME test
moved to branch posthoc-kalshi-cme.
