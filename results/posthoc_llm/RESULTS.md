# Post-hoc LLM (MLX LoRA) mispricing classifier: RESULTS (PARTIAL)

**Label: post-hoc, exploratory; small LLM fine-tuned with LoRA on training snapshots; walk-forward on training only; holdout not run. PARTIAL: the run was stopped by request at 06:49 ET (Divi's instruction, replaced by another agent).**

Spec: SPEC.md (b606242, committed and pushed before any training). Code and tests: 64b661f; 5 synthetic tests pass.

## What finished

- Fold data prepared for all 4 folds: 3,000 train rows and 200 validation rows each, from training weeks only.
- Fold 1 (train weeks 0 to 5) LoRA fit finished: 375 iterations in 1,539 s on an Apple M3 with 16 GB RAM, under
  nice -n 19 with other agents running. Training loss fell from about 0.39 at iteration 75 to about 0.14 to 0.16 at
  iterations 275 to 300. Validation loss lines: not printed. The adapter is on disk and gitignored.
- Folds 2 to 4 were capped at 225 iterations, a code change made before they ran, under the SPEC's 15-minute rule.
  They were never trained.

## What is incomplete

- Fold 1 test-week inference (weeks 6 to 9) was running when stopped. No predictions were written.
- Folds 2, 3 and 4: not trained, not inferred.
- No trial was evaluated. LLM1B.q50, LLM1B.q70 and RIDGE.base have no trades and no metrics, so there is no
  trials_log.csv or daily_pnl.csv, no classification diagnostics, and no multiple-testing correction.
- Verdict: none. Nothing on this branch is a result. If these trials are counted in experiments/variants.csv,
  record them as 3 trials planned and 0 evaluated.

## Environment

- Model: mlx-community/Llama-3.2-1B-Instruct-4bit, about 0.7 GB download, public.
- Separate venv .venv-mlx (mlx 0.32.3, mlx-lm 0.32.0), gitignored.
- The 3B model was not run (RAM and disk; see SPEC).
