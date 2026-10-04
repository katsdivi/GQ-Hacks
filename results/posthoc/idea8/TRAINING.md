# Post-hoc Idea 8: training results

**post-hoc, exploratory; selected on training only.** Spec: SPEC.md (856b5f9). Script and tests: 4217cce
(11 synthetic tests passed; that commit message says 12, a miscount). Full table: training_results.csv; trades:
training_trades.csv; console: training_run.log. Holdout not run (only on "run idea8 holdout").

Games 1,267; excluded 1 (A's exclusions); V < 500: 73; signal computed on 1,193. I (P_h / V) quantiles over
those: 5% -0.986, 25% -0.578, 50% -0.208, 75% +0.260, 95% +0.767 (taker flow leans to selling home / buying
away in P(home) terms).

Kalshi direct, costs x1 (ROC CI: game bootstrap, 2,000 reps, seed 20261004):

| x | leg | trades | ROC | 95% CI | c/contract | win rate | mean fill | mean I | Sharpe x365 | daily Sharpe | max DD $ | worst day $ | ROC excl top 5 | corr with A daily |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.2 | fade | 792 | -0.111 | [-0.181, -0.034] | -3.57 | 0.507 | 0.529 | -0.122 | -2.72 | -0.177 | 305.97 | -71.27 | -0.145 | -0.075 |
| 0.2 | placebo (follow) | 881 | -0.184 | [-0.261, -0.100] | -2.79 | 0.434 | 0.449 | -0.211 | -2.37 | -0.154 | 284.36 | -73.35 | -0.232 | 0.019 |
| 0.4 | fade | 540 | -0.156 | [-0.243, -0.062] | -5.64 | 0.493 | 0.536 | -0.150 | -3.42 | -0.249 | 310.14 | -74.63 | -0.206 | -0.047 |
| 0.4 | placebo (follow) | 626 | -0.174 | [-0.271, -0.068] | -0.89 | 0.431 | 0.428 | -0.267 | -0.65 | -0.047 | 198.88 | -35.36 | -0.242 | 0.010 |
| 0.6 | fade | 290 | -0.142 | [-0.271, -0.016] | -4.86 | 0.519 | 0.555 | -0.205 | -2.58 | -0.245 | 146.95 | -46.50 | -0.220 | 0.004 |
| 0.6 | placebo (follow) | 371 | -0.285 | [-0.409, -0.140] | -1.73 | 0.368 | 0.375 | -0.383 | -1.12 | -0.104 | 130.53 | -31.44 | -0.386 | -0.049 |

Costs x2, Kalshi direct, fade: x 0.2 ROC -0.155 [-0.220, -0.086]; x 0.4 -0.197 [-0.277, -0.110]; x 0.6 -0.183
[-0.302, -0.065].

Selected x by the training rule (highest fade ROC, Kalshi direct, x1, >= 100 trades): **0.2**. Its ROC is
negative with a CI entirely below zero; the fade has no edge on training at any x. Win rate is below mean fill at
every x on the fade leg (0.507 vs 0.529, 0.493 vs 0.536, 0.519 vs 0.555). The placebo also loses, so neither
side of the pre-kickoff taker imbalance pays after the 1 cent half-spread and fees. Correlation of daily P&L with
Strategy A (theta 0.80, favorite, Kalshi direct, out/strategy_a/rows.parquet) is near zero (-0.08 to 0.00).
