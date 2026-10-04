# Post-hoc LLM (MLX LoRA) mispricing classifier: SPEC

**Label: post-hoc, exploratory; small LLM fine-tuned with LoRA on training snapshots; walk-forward on training only; holdout not run.**

Written 2026-10-04 06:16 ET, committed and pushed before any training or inference on real data.

## Question

Can a small instruct LLM (Llama 3.2 1B, 4-bit, Apple MLX), LoRA fine-tuned on text-serialised market and game
snapshots, tell when a Kalshi team price is too low by more than the cost of buying it, out of sample?

## Environment

- Apple M3, 16 GB RAM, about 13 GB free disk. A separate venv `.venv-mlx` (mlx 0.32.3, mlx-lm 0.32.0); never
  `.venv-run`.
- Model: `mlx-community/Llama-3.2-1B-Instruct-4bit` (public, no token). The 3B model is NOT run: 16 GB of RAM is
  shared with several concurrent agents (load average above 20 at 06:02 ET) and the disk has about 13 GB free. So
  the grid is 1B only.
- All training and inference under `nice -n 19`. Weights, adapters, venv and per-row predictions are gitignored.

## Data (training only, kickoff before 2026-08-01)

- Snapshot rows: `data/llm_cache/snapshots.parquet`, a byte copy of `../wt-regress/data/regress_cache/snapshots.parquet`
  (sha256 d723fdaf0c5a413f45825c072600491ae52d48418d766ba71b703574f4dc1da1), built by the posthoc-regress snapshot
  builder (`scripts/posthoc_regress.py` at a7cb8fb, spec 4b318d6). It has 46,469 rows, 25 ET weeks (0 to 24), and
  one row per team at kickoff - 30 min, kickoff - 5 min and every 10 min from kickoff + 20 min to + 3 h. Every
  feature is known at t, and ESPN only uses plays with wallclock <= t; defect games are flagged espn_ok = 0.
- Execution and metric helpers: `scripts/regress_common.py`, a copy of posthoc-regress a7cb8fb (itself copied from
  posthoc-costside 652c5e9).
- Kalshi own-market trades for fills: `staleline/data/raw/kalshi_only/<game_id>.parquet`, read-only.

## Prompt (input text), compact integer-cent formatting

One line of `key=value` fields, built only from these snapshot columns: league (nfl), preseason, pregame,
mins_from_ko, p (price, cents), q (other team price, cents), s (sum, cents), dp1/dp5/dp15 (cents), n5, n15,
imb5, age (s), pm_gap (cents, only if pm_ok), score_diff, period, sec_left (min), own_poss, wp (pct, only if
espn_ok), wp_gap (cents, only if espn_ok), nv_gap (cents, only if nv_ok). Missing sources are written as `na`.

The prompt NEVER contains pay, r, y, c, week, game_id, team, event, t_ns or any settlement field. A unit test plants
a future column and asserts the prompt is unchanged.

## Target (completion)

One class word, chosen from three single-token words (checked with the tokenizer): `under`, `fair`, `over`.

- under: r > c
- over: r < -c
- fair: otherwise

Here r = outcome - price (the snapshot's `r`) and c = the row's all-in taker cost (the snapshot's `c`: 1 c plus the
taker fee per contract). The target is anchored on price and cost, not on who wins.

Inference: one forward pass over the prompt plus the chat template. Read the logits at the answer position and
softmax over just the three class tokens, with no sampling (deterministic, temperature 0).

## Walk-forward folds (expanding window, by ET week)

| Fold | Train weeks | Test weeks |
|---|---|---|
| F1 | 0 to 5 | 6 to 9 |
| F2 | 0 to 9 | 10 to 14 |
| F3 | 0 to 14 | 15 to 18 |
| F4 | 0 to 18 | 19 to 24 |

The test weeks (6 to 24, 19 weeks) are the same as the other post-hoc agents. A fold never trains on its test
weeks or later (asserted).

## LoRA training (fixed, no tuning)

- mlx-lm LoRA, rank 8, on the top 8 layers, dropout 0.05, learning rate 1e-4, batch 8, prompt masked (loss on the
  answer only).
- Training rows per fold: a random subsample of at most 3,000 rows from the fold's train weeks (numpy seed 20261004).
- Iterations: min(375, rows / 8), so about 1 epoch. No early stopping on test weeks. A fold is cut to fewer
  iterations only if it would exceed about 15 minutes, and the count is reported.
- Validation file for mlx-lm: 200 rows from the last train week of the fold (never a test week).

## Trading rule and trials

- In each test week, for each snapshot in time order: if P(under) > q, buy 10 YES of that team as taker. The fill is
  the first own-market trade at or after t + 1 s within 5 min, plus 1 cent, capped at 0.99, and skipped at 0.99.
  Hold to settlement and pay the taker fee 0.07 x C x P(1-P), rounded up to the cent.
- Primary book: at most one trade per game, the first eligible snapshot.
- Trials, 3 in total:
  1. LLM1B.q50 (q = 0.5)
  2. LLM1B.q70 (q = 0.7)
  3. RIDGE.base: ridge (alpha 10) on the same snapshot features as posthoc-regress, fitted on the same fold train
     weeks; trade if predicted r > the taker break-even. This baseline trades, so it counts as a trial.
- Benchmarks, not trials: take every snapshot (first per game) and no trade.

## Metrics

- Classification on all test rows: accuracy; multi-class Brier for the LLM vs the class-frequency baseline from the
  fold's train weeks; Brier skill.
- A residual check: correlation of (P(under) - P(over)) with r, and the ridge out-of-sample R^2 vs r = 0.
- Per trial: trades, ROC with a game-bootstrap 95% CI (2,000 reps, seed 20261004), net c/contract, win rate vs
  break-even, Sharpe x365 on game days, max drawdown, ROC excluding the top 5 games.

## Multiple-testing correction, cumulative

Daily P&L of my 3 trials plus every committed trial so far:
- `../wt-costside/results/posthoc_costside/trials_log.csv` and `daily_pnl.csv` (posthoc-costside rounds, including
  the broad search and both helpers);
- the posthoc-unsup and posthoc-regress daily P&L files, if committed when I run.

Report the studentized Reality Check p (stationary bootstrap), Holm, and the DSR of the best (the
`regress_common.multiple_testing` function).

**Candidate edge** = ROC CI lower bound > 0 AND Reality Check p < 0.05 over the cumulative trials AND at least 100
trades AND ROC excluding the top 5 games > 0. If one is found, recommend ONE holdout test on Divi's exact phrase
"run llm holdout"; never run it here.

## Tests (synthetic)

- No future field enters a prompt (planted column).
- Fold boundaries: train weeks are strictly below the test weeks.
- Taker fee and fill correctness.
- Class-token readout is deterministic: same logits twice, and the three tokens are single tokens.

## Records

No `experiments/variants.csv` writes. This branch adds 3 trials.
