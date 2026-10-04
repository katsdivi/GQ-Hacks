# Idea 11 (b), settled. market-efficiency measurement; polymarket.com is not available to US persons; not a strategy available to the authors

Settlement step only (settle_only), run after the one real-data run (9d06979): that run cached empty polymarket.com resolutions because the Gamma query lacked closed=true, so its P&L was all NaN (printed as 0) and every game showed as a disagreement. Opportunities, fills, sizes, prices and fees below are the run's saved executions.csv, unchanged.

Opportunities: 3039 in 84 games (home leg 1600, away leg 1439). Duration median 0.051 s, p90 1.343 s. Share lasting >= 0.25 / 0.5 / 1.0 / 2.0 s: 0.320 / 0.231 / 0.129 / 0.078. Median executable size at t: 7.25.

| L (s) | attempts | executed | missed | no book / side empty | games executed | contracts | total P&L $ | 95% CI | per contract $ | 95% CI | ex top 5 total $ | ex top 5 per contract $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 3039 | 517 | 2488 | 34 | 61 | 3841.78 | 58.48 | [31.60, 94.67] | 0.0152 | [0.0100, 0.0213] | 26.57 | 0.0093 |
| 0.5 | 3039 | 543 | 2464 | 32 | 59 | 3797.77 | 63.56 | [34.13, 103.25] | 0.0167 | [0.0103, 0.0245] | 28.20 | 0.0097 |
| 1.0 | 3039 | 453 | 2554 | 32 | 57 | 3272.75 | 54.01 | [28.46, 89.74] | 0.0165 | [0.0107, 0.0227] | 24.28 | 0.0104 |

Settlement check: 63 games with an executed opportunity at any L; disagreements 0: none.
Executed rows without a usable settlement (excluded from P&L): L 0.25: 0, L 0.5: 0, L 1.0: 0.
Sources: Kalshi data/holdout_raw/settlements.csv (settlement_value_dollars); polymarket.com Gamma API markets?condition_ids=..&closed=true outcomePrices (cached data/pm_resolution/, gitignored).
