# Post-hoc training-positive book: results

**Label: post-hoc, exploratory; cells chosen by training ROC after all results were seen.** Spec: SPEC.md (5d568e4).

## 1. Cell scan (2026-10-04 05:07 ET, written before any holdout number was computed)

Rule: TRAINING ROC (Kalshi direct, costs x1, net) > 0 and >= 20 trades. Any leg counts.

### Included (2)

| Cell | Leg | Training ROC direct | Trades | Source (file, column) |
|---|---|---|---|---|
| Strategy A taker, theta 0.80 (pre-registered) | favorite | +0.00736 | 302 | docs/results/maker_vs_taker.csv roc_direct (row "A taker, favorite"); same value in results/numbers.json A.roc_direct and experiments/variants.csv row 12 notes |
| Strategy A-maker, theta 0.80 (pre-registered, v3 A5) | favorite | +0.0618 (direct = taker fee formula, upper bound) | 25 fills | docs/results/maker_vs_taker.csv roc_direct (row "A-maker, favorite") |

### Excluded

| Cell(s) | Reason |
|---|---|
| Strategy A theta 0.70, 0.90 (favorite), all A placebos | training ROC direct <= 0 (-0.0193, -0.0091; placebos -0.34 to -0.67; experiments/variants.csv notes) |
| A-maker underdog placebo | ROC -1.0 (docs/results/maker_vs_taker.csv) |
| Strategy B, all 8 settings and 8 placebo settings | no ROC column (c/contract only; experiments/variants.csv) |
| Laggard (pre-registered) | no committed training result with ROC (holdout-only test) |
| Post-hoc T&S laggard | no ROC column (c/contract only, results/posthoc/tns/results.csv); also run on holdout-period data |
| Ideas 1, 2, 3, 11 | run on holdout-period (Oct 3) data, no training ROC; Idea 3 and Idea 11 original execution also INVALID |
| Idea 4, all thetas and legs | training ROC <= 0 (results/posthoc/idea4/training_results.csv roc_mean) |
| Idea 6 winner leg, D 60 (+0.375, 20 trades) | excluded-invalid: winner leg INVALID (bad ESPN end-marker wallclocks, lookahead); D 180 and 600 also < 20 trades |
| Idea 6 placebo | ROC -1.0 |
| Idea 7 placebo k 0.05 (+0.701) | 1 trade (< 20); all other Idea 7 cells ROC < 0 or 0 trades |
| Idea 8, 9, 12, all cells | training ROC < 0 (training_results.csv roc_mean) |
| Idea 10 | no ROC column (c/contract only) |
| Idea 13 placebo e 0.04 (+0.032) | 6 trades (< 20); other Idea 13 cells ROC < 0 or 0 trades |

Subsets (Idea 7 and 12 "excl_flagged", "excl_stale12") give the same signs; the "all" rows were scanned.

## 2. Holdout book (2026-10-04 05:09 ET)

Both included cells have committed holdout outputs (results/holdout/strategy_a_rows.parquet, results/holdout/strategy_a_maker_rows.parquet), so the book was computed from those files only; no strategy was run. 10 contracts per trade as run, no reweighting, Kalshi direct (A-maker: taker fee formula, upper bound, as in its committed output). Script: scripts/posthoc_positive_book.py; output: metrics.json.

| Metric | Value |
|---|---|
| Trades | 272 (A taker 263, A-maker 9; 263 games) |
| Total P&L | -$45.40 |
| ROC (mean per trade) [game-bootstrap 95% CI, 2,000 reps, seed 20261004] | -0.0188 [-0.0604, +0.0215] |
| Net cents per contract | -1.67 |
| Game days | 19 |
| Daily Sharpe (game days) | -0.204 |
| Sharpe x365 (daily Sharpe x sqrt(365), game days) | -3.90 |
| Max drawdown | $45.40 |
| Worst day | -$34.34 (2026-10-03) |

Reading: the only two training-positive cells with >= 20 trades are both Strategy A theta 0.80 favorite variants (taker and maker). Their combined holdout book loses money; the ROC CI includes 0. The A taker part is the pre-registered Strategy A holdout result (ROC direct -0.0147); A-maker adds 9 fills.

## 3. Bookkeeping

- experiments/variants.csv: 1 row appended (74 rows). Divi's message expected 77, which assumed the 3 T&S laggard rows were added first; they were not added here (a separate change).
- Deflated Sharpe rerun at 74 trials (scripts/posthoc_dsr.py), kept next to the 22 (pre-registered) and 73 lines; see results/posthoc/SUMMARY.md and dsr_posthoc.json.
- Keys: posthoc_posbook_* in results/posthoc/numbers_posthoc.json; paper/numbers.tex regenerated.
