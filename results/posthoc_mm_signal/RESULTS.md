# Kalshi-signal market making on the slow venue: results (post-hoc, exploratory; historical local files only)

Spec 6098d5c. One run, unedited. P&L in dollars (10-contract quotes); pnl60 = marked to slow-venue mid at fill + 60 s (primary), pnlset = held to settlement. S minus N = sum over games, game-bootstrap 95% CI (2,000, seed 20261004). Adverse selection as10/as60 = mean side x mid move after fill (negative = against us).

Notes: {"cme_games": 14, "cme_signals": 3660, "pm_games": 88, "pm_signals": 9600, "pm_settle_fallback": 4}

| venue | rule | L | N_fills | N_contracts | N_pnl60 | N_pnlset | N_pnl60_pc | N_pnlset_pc | N_as10 | N_as60 | S_fills | S_contracts | S_pnl60 | S_pnlset | S_pnl60_pc | S_pnlset_pc | S_as10 | S_as60 | SminusN_pnl60 | SminusN_pnl60_lo | SminusN_pnl60_hi | SminusN_pnlset | SminusN_pnlset_lo | SminusN_pnlset_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CME | F2 | 0.25 | 23 | 214 | -0.75 | 1.4 | -0.003505 | 0.006542 | -0.001053 | -0.01194 | 16 | 144 | 0.95 | -11.1 | 0.006597 | -0.07708 | 1.281e-17 | 0.001818 | 1.7 | 0.2 | 3.45 | -12.5 | -33.91 | 9.105 |
| CME | F2 | 1 | 23 | 214 | -0.75 | 1.4 | -0.003505 | 0.006542 | -0.001053 | -0.01194 | 16 | 144 | 0.95 | -11.1 | 0.006597 | -0.07708 | 1.281e-17 | 0.001818 | 1.7 | 0.2 | 3.45 | -12.5 | -33.91 | 9.105 |
| polymarket.com | F1 | 0.25 | 428 | 4280 | 46.53 | 114 | 0.01087 | 0.02664 | -0.003455 | -0.004032 | 293 | 2930 | 30.83 | 24.19 | 0.01052 | 0.008256 | -0.005197 | -0.002554 | -15.7 | -55.61 | 16.48 | -89.84 | -208.4 | 19.04 |
| polymarket.com | F1 | 1 | 428 | 4280 | 46.53 | 114 | 0.01087 | 0.02664 | -0.003455 | -0.004032 | 320 | 3200 | 35.52 | 25.06 | 0.0111 | 0.007831 | -0.006066 | -0.002404 | -11.01 | -51.85 | 20.04 | -88.97 | -201.3 | 12.23 |

## Verdicts (pre-fixed reading rule, primary +60 s mark; settlement shown for reference)

- polymarket.com, L 0.25 s: does not make sense on this data (settlement mark: does not make sense on this data)
- polymarket.com, L 1.0 s: does not make sense on this data (settlement mark: does not make sense on this data)
- CME, L 0.25 s: does not make sense on this data (no F1 result) (settlement mark: does not make sense on this data (no F1 result))
- CME, L 1.0 s: does not make sense on this data (no F1 result) (settlement mark: does not make sense on this data (no F1 result))
