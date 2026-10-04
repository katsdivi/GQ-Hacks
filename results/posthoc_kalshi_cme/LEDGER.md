# Ledger: posthoc-kalshi-cme

| time (ET) | step | detail |
|---|---|---|
| 06:46 | SPEC committed | Stage 1 design, gate and Stage 2 rule; CME fee source CME 25-466 Appendix D ($0.01/contract Globex) |
| 06:48 | Stage 1 run | 14 games, 28 contracts; 18 cells; profit per contract after CME fee -1.5 to -6.6 c in every cell; real minus placebo CI > 0 in 4 of 18 cells (60 s exit, J 4 to 5 c, L 1 to 2 s) |
| 06:48 | Gate | selected cell J 5 c, L 5 s, settle (1,625 trades): real -1.47 c [-5.78, +1.81], diff +1.86 c [-2.44, +5.17]; gate FAILED (real <= 0 and diff CI includes 0) |
| 06:48 | Stage 2 | not run; no 2026 CME data downloaded; Databento spend for this branch $0 |
| 06:58 | Amendment 1 committed | CME maker variant (J 5 c, W 5/30 s, strict trade-through fills), descriptive; CME trade prints on disk for all 28 contracts, no purchase |
| 06:59 | Amendment 1 results | 2,449 attempts; fill rate 0.45% (W 5 s) and 6.7% (W 30 s); W 30 s: settle -1.6 c [-9.2, +5.7], 60 s exit -5.3 c [-7.3, -3.4]; real minus placebo CI includes 0; no purchase, $0 |
