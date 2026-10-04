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

## Disclosure (added 03:51 ET, Oct 4 2026, after the run; no rerun, no new fills)

Rule text said size = min(10, displayed size on each leg); implemented per leg independently, so most trades left about 10 contracts unhedged on one leg; P&L mostly measures unwind cost. Exact numbers from idea1_trades.csv: Kalshi direct, 44 of 52 trades (84.6%) left more than 5 contracts unhedged and 40 of 52 (76.9%) left 9 or more; Webull, 23 of 24 (95.8%) left more than 5 and 21 of 24 (87.5%) left 9 or more; all 76 trades, 67 (88.2%) more than 5.

## Matched-quantity diagnostic (diagnostic, not a variant). POST-HOC, EXPLORATORY

From the existing trade log only (scripts/posthoc_idea1_diag.py; output idea1_diagnostic_matched.csv). Per trade: q = min(q_home, q_away); P&L = q x 1 - q x (price_home + price_away) - fee(price_home, q) - fee(price_away, q), excluding the unwind. The log has no fee column, so fees on q were recomputed with the same function (costs.fee). Kalshi direct rounds each leg's fee up to the cent even for tiny q. Game bootstrap over 88 games (0 for games with no trade), 2,000 draws, seed 20261003, 95% percentile CI.

| fee path | L (s) | trades | matched contracts | median matched size | matched P&L total | 95% CI | mean per trade | 95% CI |
|---|---|---|---|---|---|---|---|---|
| direct | 0.25 | 22 | 10.11 | 0.01 | -0.1676 | [-0.3054, -0.0194] | -0.007618 | [-0.01303, -0.001179] |
| direct | 0.5 | 16 | 6.07 | 0.005 | -0.1086 | [-0.2181, 0.0106] | -0.006787 | [-0.0132, 0.0005343] |
| direct | 1.0 | 14 | 12.03 | 2.566e-08 | 0.3807 | [-0.1187, 1.35] | 0.02719 | [-0.008767, 0.1067] |
| webull | 0.25 | 8 | 6.358e-08 | 2.33e-09 | 3.865e-09 | [1.56e-10, 1.083e-08] | 4.832e-10 | [3.324e-11, 1.415e-09] |
| webull | 0.5 | 8 | 6.358e-08 | 2.33e-09 | 3.819e-09 | [1.436e-10, 1.074e-08] | 4.774e-10 | [2.843e-11, 1.407e-09] |
| webull | 1.0 | 8 | 6.358e-08 | 2.33e-09 | 3.819e-09 | [1.436e-10, 1.074e-08] | 4.774e-10 | [2.843e-11, 1.407e-09] |

Opportunity durations. The existing outputs hold only quantiles, so the opportunity runs were recomputed with the committed signal functions (signal_table, runs) on the same data: signal only, no fills, no attempts, no P&L. The recomputed counts, medians and p90s match idea1_results.csv.

| fee path | opportunities | median duration s | p90 duration s | share >= 0.25 s | share >= 0.5 s | share >= 1.0 s |
|---|---|---|---|---|---|---|
| direct | 1260 | 0.01087 | 0.03878 | 0.0373 (47) | 0.0294 (37) | 0.0262 (33) |
| webull | 318 | 0.007866 | 0.2177 | 0.1006 (32) | 0.0943 (30) | 0.0881 (28) |
