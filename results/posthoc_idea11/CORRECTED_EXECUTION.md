# Idea 11 (b): corrected execution (2026-10-04 04:40 ET)

**Post-run correction: original execution model conditioned on the second leg clearing in the future.**

post-hoc, exploratory; market-efficiency measurement; polymarket.com is not available to US persons; not a strategy available to the authors.

Re-priced from the committed detection output (opportunities.csv of the run in 9d06979; settlements as fixed in fc95b81). Detection unchanged, SPEC.md unchanged. Script: scripts/posthoc_idea11_corrected.py. Model: independent IOC limit orders at the detected best asks a_K, a_P; book state at a fill time = latest snapshot with venue timestamp <= that time; Kalshi leg at t + L, polymarket.com leg at t + L + delay (1 s for every game); fill price = best ask then, size = min(10, displayed size); hedged = min of the two fills; the rest is naked. Primary: naked held to settlement. Secondary: naked unwound at that venue's best bid at failure time + 1 s with its fee, failure time = the naked leg's own fill time (if that bid side is empty, held to settlement and counted). Fees per order at executed size (Kalshi rounded up to the cent; polymarket.com rounded half-up to 5 decimals); each order's fee is split between hedged and naked contracts by quantity.

Per contract = P&L / sum over attempts of the larger leg fill. Game bootstrap 95% CI, 2,000 reps, seed 20261004. Excluding top 5 = the 5 games with the highest P&L under that treatment.

## Fill outcomes per L (all detected attempts)

| L (s) | attempts | both filled | Kalshi only | polymarket.com only | neither | unsettled excluded | hedged contracts | naked contracts |
|---|---|---|---|---|---|---|---|---|
| 0.25 | 3039 | 733 | 1434 | 449 | 423 | 1 | 2977.25 | 20131.81 |
| 0.5 | 3039 | 692 | 1435 | 470 | 442 | 1 | 2746.29 | 20346.49 |
| 1.0 | 3039 | 613 | 1466 | 536 | 424 | 1 | 2485.32 | 20518.59 |

## P&L, Primary: naked held to settlement

| L (s) | total $ | 95% CI | per attempt $ | 95% CI | per contract $ | 95% CI | ex top 5 total $ | ex top 5 per contract $ |
|---|---|---|---|---|---|---|---|---|
| 0.25 | -348.04 | [-1170.93, 411.70] | -0.1146 | [-0.3711, 0.1437] | -0.0151 | [-0.0515, 0.0192] | -847.10 | -0.0432 |
| 0.5 | -346.09 | [-1217.38, 464.55] | -0.1139 | [-0.3819, 0.1475] | -0.0150 | [-0.0522, 0.0197] | -853.71 | -0.0434 |
| 1.0 | -361.48 | [-1227.53, 436.82] | -0.1190 | [-0.3886, 0.1496] | -0.0157 | [-0.0539, 0.0198] | -884.90 | -0.0459 |

## P&L, Secondary: naked unwound at best bid, failure time + 1 s

| L (s) | total $ | 95% CI | per attempt $ | 95% CI | per contract $ | 95% CI | ex top 5 total $ | ex top 5 per contract $ |
|---|---|---|---|---|---|---|---|---|
| 0.25 | -697.18 | [-941.94, -476.26] | -0.2295 | [-0.2737, -0.1837] | -0.0302 | [-0.0372, -0.0231] | -709.40 | -0.0314 |
| 0.5 | -702.21 | [-946.93, -479.46] | -0.2311 | [-0.2747, -0.1854] | -0.0304 | [-0.0373, -0.0231] | -713.70 | -0.0315 |
| 1.0 | -724.96 | [-986.61, -488.36] | -0.2386 | [-0.2847, -0.1893] | -0.0315 | [-0.0386, -0.0237] | -735.15 | -0.0325 |

## Hedged vs naked split ($)

| L (s) | hedged | naked, held | naked, unwound | unwind bid side empty (held instead) | unwind bid size < naked qty |
|---|---|---|---|---|---|
| 0.25 | 22.66 | -370.70 | -719.84 | 60 | 493 |
| 0.5 | 24.06 | -370.14 | -726.27 | 62 | 499 |
| 1.0 | 26.29 | -387.77 | -751.25 | 56 | 425 |

## Original model (fc95b81, for comparison; conditioned on the second leg clearing)

| L (s) | executed | total $ | per contract $ |
|---|---|---|---|
| 0.25 | 517 | 58.48 | 0.0152 |
| 0.5 | 543 | 63.56 | 0.0167 |
| 1.0 | 453 | 54.01 | 0.0165 |

Per-attempt rows: corrected_attempts.csv (untracked; regenerate with the command in README.md).
