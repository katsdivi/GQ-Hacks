# IDEA 3 results, Kalshi reversal after large taker trades. POST-HOC, EXPLORATORY (formed after seeing the holdout)

Spec: results/posthoc_latency/SPEC_idea3.md (commit 4e60e8c). One run on real data, no changes after output. Games: 88 (vultr). Net c/contract after Kalshi direct fees on both legs. CI: laggard.game_bootstrap_ci on per-game sums (2,000 draws, seed 20261003), games with >= 1 trade. The 95th percentile threshold uses the whole game window (lookahead in the threshold, a property of the given rule). No interpretation.

| L (s) | trades | games w/ trades | mean gross c | mean fees c | mean net c | 95% CI | share games + | Sharpe/trade | ex top 5: trades | ex top 5: mean net c | ex top 5: Sharpe |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 79 | 36 | -2.25 | 5.30 | -7.55 | [-13.52, -4.01] | 0.11 | -0.340 | 73 | -8.49 | -0.374 |
| 0.5 | 80 | 36 | -2.26 | 5.20 | -7.46 | [-13.43, -3.87] | 0.11 | -0.337 | 74 | -8.44 | -0.373 |
| 1.0 | 80 | 36 | -2.71 | 5.18 | -7.89 | [-13.76, -4.58] | 0.08 | -0.361 | 74 | -8.65 | -0.383 |

Print receipt lag (recv_ns - ts) of traded prints, and skips:

| L (s) | lag p50 s | lag p90 s | lag max s | traded prints lag > 5 s | execution skips |
|---|---|---|---|---|---|
| 0.25 | 4.91 | 16.83 | 82.13 | 38 | busy: 50; no_quote: 2 |
| 0.5 | 4.89 | 16.69 | 82.13 | 38 | busy: 50; no_quote: 1 |
| 1.0 | 4.89 | 16.69 | 82.13 | 38 | busy: 50; no_quote: 1 |

Signal stage counts (all games): big_prints: 46763, book_rows_null_src: 4950, mid_undefined: 1836, move_lt_2c: 44286, no_pre_book: 2, post_book_not_received: 508; signals: 131.

Variant count: 3 (one per L) added to the DSR total. Per-trade rows (our simulated trades only): results/posthoc_latency/idea3_trades.csv.
Run: script commit d13e473, single real-data run 03:48:12 to 03:48:40 ET on Oct 4, exit 0, no crash, no code change after output.

