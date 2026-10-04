# LEDGER posthoc-mm-signal

| time ET | event | commit |
|---|---|---|
| 07:28 | SPEC committed before any real-data run; 4 variants (2 venues x 2 latencies) + N baselines | this commit |
| 07:30 | simulator + 5 synthetic tests (pass) | 38da93d |
| 07:30 to 07:34 | single real-data run (CME 14 games, 3,660 Kalshi signals; polymarket.com 88 games, 9,600 signals) | b346230 |
| 07:35 | note: CME F1 had 0 fills (why rows are missing); no rerun | this commit |

Variants: 4 (polymarket.com S at L 0.25 and 1.0; CME S at L 0.25 and 1.0), plus N baselines. Verdict for all 4: "does not make sense on this data".
