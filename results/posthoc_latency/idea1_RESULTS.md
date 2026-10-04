# IDEA 1 results, Kalshi complement lag. POST-HOC, EXPLORATORY (formed after seeing the holdout)

Spec: results/posthoc_latency/SPEC_idea1.md. One run on real data, no changes after output. Games: 88 (vultr, polymarket.com lead-test windows). Dollars; size cap 10 contracts per leg. CI: game-level bootstrap, 2,000 draws, seed 20261003, percentile 95%. No interpretation.

## Kalshi direct taker (primary)

| L (s) | opps YES | opps NO | attempts | executed | missed | contracts | net P&L | P&L 95% CI | trade mean | mean 95% CI | trade sd | Sharpe/trade | games w/ trade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 858 | 402 | 931 | 22 | 909 | 10.11 | -6.19 | [-9.04, -3.65] | -0.281 | [-0.356, -0.211] | 0.174 | -1.619 | 22 |
| 0.5 | 858 | 402 | 1000 | 16 | 984 | 6.07 | -5.17 | [-8.01, -2.71] | -0.323 | [-0.402, -0.241] | 0.161 | -2.002 | 16 |
| 1.0 | 858 | 402 | 1038 | 14 | 1024 | 12.03 | -3.75 | [-6.30, -1.26] | -0.268 | [-0.381, -0.121] | 0.247 | -1.085 | 14 |

| L (s) | paired size min/25/50/75/90/max | opp duration s min/25/50/75/90/max (censored) | fill delay s min/25/50/75/90/max | missed reasons | unsettled excluded |
|---|---|---|---|---|---|
| 0.25 | 1.05e-09/2.67e-09/0.01/0.01/1.01/6 | 0.000486/0.00479/0.0109/0.0184/0.0388/7.44e+03 (0) | 0.000259/0.00752/0.0829/0.236/0.77/12.9 | no snapshot at or after t+L in window: 1; side empty at t+L: 11; sum no longer clears at t+L: 897 | 0 |
| 0.5 | 1.05e-09/2e-09/0.005/0.01/0.01/6 | 0.000486/0.00479/0.0109/0.0184/0.0388/7.44e+03 (0) | 0.000264/0.0291/0.185/0.637/1.88/12.6 | no snapshot at or after t+L in window: 5; side empty at t+L: 11; sum no longer clears at t+L: 968 | 0 |
| 1.0 | 1.05e-09/1.95e-09/2.57e-08/0.01/1/10 | 0.000486/0.00479/0.0109/0.0184/0.0388/7.44e+03 (0) | 0.000418/0.0107/0.0869/0.614/1.29/12.1 | no snapshot at or after t+L in window: 6; side empty at t+L: 35; sum no longer clears at t+L: 983 | 0 |

## Webull $0.02/contract/leg

| L (s) | opps YES | opps NO | attempts | executed | missed | contracts | net P&L | P&L 95% CI | trade mean | mean 95% CI | trade sd | Sharpe/trade | games w/ trade |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 221 | 97 | 247 | 8 | 239 | 0.00 | -3.50 | [-6.00, -1.50] | -0.438 | [-0.500, -0.300] | 0.176 | -2.481 | 8 |
| 0.5 | 221 | 97 | 248 | 8 | 240 | 0.00 | -4.00 | [-7.00, -1.50] | -0.500 | [-0.533, -0.462] | 0.053 | -9.354 | 8 |
| 1.0 | 221 | 97 | 247 | 8 | 239 | 0.00 | -4.05 | [-7.05, -1.50] | -0.506 | [-0.536, -0.481] | 0.042 | -12.133 | 8 |

| L (s) | paired size min/25/50/75/90/max | opp duration s min/25/50/75/90/max (censored) | fill delay s min/25/50/75/90/max | missed reasons | unsettled excluded |
|---|---|---|---|---|---|
| 0.25 | 1.05e-09/1.71e-09/2.33e-09/2.96e-09/1.71e-08/4.86e-08 | 0.000486/0.00378/0.00787/0.0231/0.218/7.44e+03 (0) | 0.000458/0.0837/0.235/0.937/1.36/12.9 | side empty at t+L: 4; sum no longer clears at t+L: 235 | 0 |
| 0.5 | 1.05e-09/1.71e-09/2.33e-09/2.96e-09/1.71e-08/4.86e-08 | 0.000486/0.00378/0.00787/0.0231/0.218/7.44e+03 (0) | 0.0185/0.142/0.553/1.12/5.19/12.6 | side empty at t+L: 4; sum no longer clears at t+L: 236 | 0 |
| 1.0 | 1.05e-09/1.71e-09/2.33e-09/2.96e-09/1.71e-08/4.86e-08 | 0.000486/0.00378/0.00787/0.0231/0.218/7.44e+03 (0) | 0.00933/0.0843/0.58/1.28/6/12.1 | side empty at t+L: 12; sum no longer clears at t+L: 227 | 0 |

Variant count: 3 (one per L) added to the DSR total. Per-trade rows (our simulated trades only): results/posthoc_latency/idea1_trades.csv.
