# IDEA 2 results, polymarket.com sub-second lead. POST-HOC, EXPLORATORY (formed after seeing the holdout)

Exploratory only; formed after the holdout was seen; confirms nothing. Spec: SPEC_idea2.md (first commit
4ec43cc at 03:33:01 ET; amended 2b73091 at 03:40:05 ET before the real-data run). Script
scripts/posthoc_idea2.py at 2b73091, run once 03:40 to 03:45 ET, exit 0, no code or parameter changes after.
No interpretation is given here.

## Inputs

- Games: 88 usable polymarket rows of data/live/holdout_windows.csv (qualifying, no exclusion flag), all vultr;
  0 skipped for machine. Vultr recordings only.
- src_ts_ns coverage in the loaded windows (book rows, including the load margin): Kalshi 1,898 null of
  9,154,124 (0.02%, dropped); polymarket.com 0 null of 6,512,743. Resolution: 1 ms on both (see SPEC).
- P(home) check: sample books agree in level across venues (Kalshi 0.90/0.91 vs polymarket.com 0.91/0.92;
  0.55/0.56 on both).

## Lag test, 100 ms venue-time grid, lags -3.0 to +3.0 s (positive = Kalshi first)

| | n | median lag (s) | share > 0 | share < 0 |
|---|---|---|---|---|
| real | 88 | 0.1 | 0.966 | 0.011 |
| placebo (Kalshi of A vs polymarket.com of B) | 83 | -0.4 | | |

Mann-Whitney p (real vs placebo, two-sided) = 0.0365. xcorr_lead.decide label with min lead 1.0 s:
"neither venue leads consistently" (printed for description only).

Real lag distribution (s: games): -1.2: 1, 0.0: 2, 0.1: 80, 0.2: 2, 0.3: 2, 0.7: 1.

Placebo lag distribution: spread across -3.0 to +3.0 s (46 distinct values, none with more than 5 games);
full list in idea2_lag_distribution.csv.

## Trade rule (3 trading variants, one per L; added to the DSR total)

Net c/contract, Kalshi direct fees primary, Webull line below. CI = game bootstrap (laggard.game_bootstrap_ci,
2,000 draws, seed 20261003). Share of games positive: denominator = games with at least one trade at that L
(80). Sharpe per trade, not annualized. "ex top 5" = after dropping the 5 games with the largest per-game sum.

| L (s) | fee line | trades | games | mean net c | 95% CI | share games > 0 | Sharpe/trade | mean gross c | ex top 5 trades | ex top 5 mean net c | ex top 5 Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | Kalshi direct | 2488 | 80 | -13.16 | [-15.08, -11.56] | 0.050 | -0.383 | -3.42 | 2450 | -13.38 | -0.387 |
| 0.25 | Webull | 2488 | 80 | -7.42 | [-8.11, -6.68] | 0.013 | -1.235 | -3.42 | 2476 | -7.46 | -1.244 |
| 0.50 | Kalshi direct | 2486 | 80 | -12.52 | [-14.28, -10.95] | 0.025 | -0.385 | -3.43 | 2454 | -12.68 | -0.389 |
| 0.50 | Webull | 2486 | 80 | -7.43 | [-8.13, -6.70] | 0.013 | -1.253 | -3.43 | 2474 | -7.47 | -1.262 |
| 1.00 | Kalshi direct | 2475 | 80 | -12.50 | [-14.32, -10.94] | 0.025 | -0.387 | -3.42 | 2469 | -12.53 | -0.388 |
| 1.00 | Webull | 2475 | 80 | -7.42 | [-8.10, -6.71] | 0.013 | -1.256 | -3.42 | 2463 | -7.46 | -1.264 |

Signals: 22,269 in total. Skips per L (0.25 / 0.5 / 1.0): ignored while holding 19,749 / 19,751 / 19,757; no
quote at fill 10 / 10 / 15; no exit snapshot 22 / 22 / 22; in cut 0; after window end 0.

Descriptive, from idea2_trades.csv (L = 0.25 / 0.5 / 1.0):
- trigger receipt delay recv_ns - src_ts_ns, percentiles 50/90/99 (s): 0.053/0.586/10.97 (similar at all L).
- fill wait = first Kalshi snapshot receipt minus order time, 50/90/99 (s): 0.12/2.11/13.9; 0.15/2.36/14.2;
  0.18/2.61/14.4.
- trades with quantity < 10 (displayed size cap bound): 945 / 928 / 919. Long share about 0.49.
- Kalshi direct fees on small fractional quantities round up to the cent per order, which is large per contract
  when the quantity is small; this is the rule as written.

## Files

- idea2_lag_distribution.csv: kind (real / placebo), game_id, game_b, lag_s.
- idea2_results.csv: the trading table above.
- idea2_trades.csv: one row per round trip (derived; entry and exit quote, quantity, gross and net).
- idea2_skips.csv: signals and skip counts per game and L.
