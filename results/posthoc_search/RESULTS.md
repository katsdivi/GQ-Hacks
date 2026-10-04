# Post-hoc broad search: results

**Label: post-hoc, exploratory; broad search over strategies already seen to fail on training; walk-forward on
training only; every grid point is a trial; holdout not run.**

Spec: SPEC.md (93f3ca6, 05:32:20 ET, before any real-data run). Script and tests: b8e5808 (7 synthetic tests
passed). One run, 2026-10-04 about 05:34 ET, `scripts/posthoc_search.py`. Pool: posthoc-meta candidates.csv
(sha256 a9ff5574...8c33), 18,565 candidates, 19 evaluation weeks (2025-09-08 to 2026-01-12), 17,216 evaluation
candidates on 112 dates. Kalshi direct fees, costs x1. 54 trials.

## Verdict

**No candidate edge.** No trial has a walk-forward ROC CI above 0 together with a Reality Check (Romano-Wolf
adjusted) p < 0.05. Nothing is recommended for a holdout test.

| Correction | Value |
|---|---|
| White Reality Check p (best trial by mean daily P&L: e_fine_I9_signal_sized) | 0.9905 |
| Hansen SPA p (studentized) | 0.621 |
| Romano-Wolf adjusted p, smallest over 54 trials | 0.9905 |
| Holm survivors (one-sided game-bootstrap ROC p) | 4, all artifacts: the m = 3 pre-game consensus books with 2 and 7 trades, every trade a win, so the bootstrap p is exactly 0 |
| Deflated Sharpe of the best trial by daily Sharpe (a_consensus_m3_pre_all, 7 trades), 54 trials | 0.0018 |
| Same, 131 trials (77 prior variants + 54) | 0.000045 |

Benchmark, all evaluation candidates: 17,216 trades, ROC -0.095 [-0.110, -0.080], -3.27 c/contract.

## Top 10 trials (walk-forward, ranked by ROC)

| Trial | Trades | ROC [95% CI] | c/contract | P&L | Sharpe x365 | ROC excl top 5 | RW p |
|---|---|---|---|---|---|---|---|
| e_fine_I9_signal_sized | 109 | +0.194 [-0.120, +0.549] | +2.43 | +$53.06 | 1.49 | -0.093 | 0.99 |
| e_fine_I9_signal | 109 | +0.193 [-0.120, +0.548] | +2.40 | +$26.20 | 1.48 | -0.094 | 1.00 |
| a_consensus_m3_pre_hyp | 2 | +0.145 [+0.139, +0.151] | +12.65 | +$2.53 | n/m | n/a | 1.00 |
| a_consensus_m3_pre_hyp_sized | 2 | +0.144 [+0.139, +0.149] | +12.60 | +$1.26 | n/m | n/a | 1.00 |
| a_consensus_m3_pre_all | 7 | +0.110 [+0.091, +0.132] | +9.87 | +$6.91 | n/m | +0.081 | 1.00 |
| a_consensus_m3_pre_all_sized | 7 | +0.108 [+0.093, +0.128] | +9.70 | +$4.85 | n/m | +0.080 | 1.00 |
| a_consensus_m2_pre_hyp | 118 | +0.021 [-0.049, +0.092] | +1.39 | +$16.39 | 1.58 | -0.010 | 1.00 |
| a_consensus_m2_pre_hyp_sized | 118 | +0.021 [-0.044, +0.080] | +1.49 | +$14.94 | 1.59 | +0.000 | 1.00 |
| c_price_ge080 | 88 | -0.011 [-0.105, +0.077] | -0.62 | -$5.43 | -0.56 | -0.040 | 1.00 |
| c_price_ge080_sized | 88 | -0.016 [-0.122, +0.076] | -1.12 | -$15.81 | -0.88 | -0.049 | 1.00 |

n/m: not meaningful (2 to 7 trades on 2 to 7 days). The full ranked table is trials.csv.

Readings:
- The finer I9 threshold is positive only because of its 5 best games: without them ROC is -0.09.
- Pre-game consensus of two hypothesis legs (m = 2) is the closest thing to a finding: 118 trades, +1.39 c per
  contract, CI from -0.049 to +0.092, and about zero without the top 5 games. Not significant after correction.
- The m = 3 pre-game books are tiny (2 and 7 trades). Their positive CIs come from every trade winning, not from
  a measurable edge.
- Hedge, Thompson, context x consensus, the low-price band and most finer thresholds lose, several with CIs
  entirely below 0.

## IN-SAMPLE BEST, after N = 512 combinations, not expected to persist

Cell I9:signal, |signal| at or above its 0.9 quantile (0.193), all prices, chosen and evaluated on the same 19
weeks: 73 trades, ROC +0.331, +5.55 c/contract, +$40.53. The walk-forward version of the same idea (e_fine_I9_signal)
drops to +0.193 with a CI from -0.12 to +0.55 and is negative without its top 5 games; after correction over 54
trials, Reality Check p 0.99. This number is the output of a search and is not a result.

## Caveats

- The candidate pool's base settings were chosen on all of training, which favours every trial here.
- Sized trials scale round-trip (B, I10) fees linearly; hold-to-settlement fees are recomputed exactly.
- The Reality Check uses non-studentized means, so it is dominated by high-variance books (e.g. Hedge with 6,220
  trades); the studentized SPA (p 0.62) is the fairer of the two and gives the same verdict.
- Four e-family trials have 0 trades (I7 signal and I13 signal have too few past trades above any cut).
- 54 trials for a later combined variants.csv commit.

Per-trade file trades.csv is gitignored. Regenerate: `PYTHONPATH=.:scripts python scripts/posthoc_search.py`
(needs ../wt-meta/results/posthoc_meta/candidates.csv).
