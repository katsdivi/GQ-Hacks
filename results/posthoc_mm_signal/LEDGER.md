# LEDGER posthoc-mm-signal

| time ET | event | commit |
|---|---|---|
| 07:28 | SPEC committed before any real-data run; 4 variants (2 venues x 2 latencies) + N baselines | this commit |
| 07:30 | simulator + 5 synthetic tests (pass) | 38da93d |
| 07:30 to 07:34 | single real-data run (CME 14 games, 3,660 Kalshi signals; polymarket.com 88 games, 9,600 signals) | b346230 |
| 07:35 | note: CME F1 had 0 fills (why rows are missing); no rerun | this commit |

Variants: 4 (polymarket.com S at L 0.25 and 1.0; CME S at L 0.25 and 1.0), plus N baselines. Verdict for all 4: "does not make sense on this data".
| 07:40 | N-maker descriptive check (N_CHECK.md, n_check.json): descriptive, post-hoc, not pre-registered, one day; per-fill rows verified against results.csv (428 fills, $46.53), no rerun; not a variant | this commit |
| 2026-10-04 07:40 ET | Data disclosure: the polymarket.com leg of this test (run b346230 and this check) used holdout-period data, the Oct 3 and Oct 4 Vultr feed for 88 games, on Divi's explicit instruction in his message launching this test. No committed file recorded this before; added at the independent verifier's request. | this commit |
| 2026-10-04 07:41 ET | Reading rule for the N maker (Divi, verbatim): "Plain maker N on polymarket.com is reported as a lead worth testing live ONLY if all hold: (1) game-bootstrap 95% CI of P&L per contract at +60 s is above zero; (2) the point estimate stays above zero excluding the top 5 games; (3) at least 55% of games are positive; (4) break-even maker fee is at least 0.5 cent per contract. Otherwise: not distinguishable from noise on one day." | this commit |
| 2026-10-04 07:41 ET | Disclosure: this rule was written at 07:41 ET, AFTER the N_CHECK results were committed (863eb69, 07:40 ET) and seen. | this commit |
