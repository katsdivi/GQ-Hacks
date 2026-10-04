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
