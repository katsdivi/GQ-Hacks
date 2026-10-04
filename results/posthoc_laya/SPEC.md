# Post-hoc Laya: frozen Laya encoder plus trained head over the meta candidate pool

**Label: post-hoc, exploratory, generative-model encoder; not part of the submitted strategies.**

Written and committed on branch posthoc-laya before any real data passes through the encoder. Code
review: CODE_REVIEW.md (a782639). Research: RESEARCH.md (60505f6). Runs only on this Mac, in MLX, under
nice -n 19. No PyTorch, no upstream laya repo, no Vultr. Stop at 08:00 ET whatever the state.

## Model

- Runtime: laya-mlx 0.3.0 (github.com/mizorewww/laya-mlx at ca5940a), installed with `pip --no-deps -e` from
  the local clone. Its 4 dependencies come from official PyPI (pypi.org/simple); the repo's uv.lock mirror
  is ignored. Venv: .venv-laya (Python 3.13, mlx 0.32.3). Never .venv-run.
- Checkpoint: Hugging Face `aac6fef/laya-mlx`, revision 20aed815fc6acde75733882e7ec0e3f28aeb9717
  (Apache-2.0, 846 MB, ModernBERT-large 421M, FP16). No token.
- Frozen encoder: `laya_mlx.embed_fn_from_agent(agent, max_length=128)`, mean-pooled hidden states, one
  vector per candidate. The decision heads and calibration are not used. No encoder weight changes.

## Candidates and walk-forward (identical to posthoc-meta)

- Pool: ../wt-meta/results/posthoc_meta/candidates.csv (gitignored), built by posthoc-meta script commit
  3da957a, results commit 07738c9; sha256
  a9ff5574a0457f79a557ea834a51e3821f991ba78e247dfa613216a64d108c33. 18,565 training candidates
  (kickoff < 2026-08-01) from 16 valid strategy cells. No holdout games.
- ET calendar week (Monday start, the file's `week` column). For each week w: fit the head on all
  candidates in weeks before w, predict week w. Start at the first week with at least 6 earlier weeks with
  candidates (the same 19 evaluation weeks as posthoc-meta).

## Inputs to the encoder, each with the timestamp proving it exists before decision time t

One short English text per candidate, built only from these candidates.csv columns:

| Field | Source column | Why it is known before t |
|---|---|---|
| strategy and leg | strategy, leg | fixed by the strategy design; the candidate exists at t |
| team side (home/away) | side | fixed when the market is listed, before kickoff - 2 h |
| league, NFL preseason | league, preseason | fixed by the schedule |
| minutes from kickoff to t | min_from_ko | t minus the scheduled ESPN kickoff, both known at t |
| ET weekday | dow | from t |
| signal strength | signal | computed by each base strategy from data with ts <= t (each base spec's no-lookahead rule) |
| same-team and opposite-team agreement counts | agree_same, agree_opp | other candidates with decision time strictly before t |
| strategy trailing win rate | trail_wr | candidates whose ET date is strictly before t's ET date (settled) |

Excluded, because they are not known before t: `fill` (first Kalshi trade at or after t + 1 s), `fee`,
`capital`, `breakeven` (all depend on fill), `pnl`, `roc`, `y`. Note: posthoc-meta used fill as a feature
and in its break-even rule. This spec is stricter: neither the encoder nor the decision rule uses fill.

Example text: "strategy I9 signal; side home; league CFB; preseason no; minutes from kickoff 70;
weekday Sat; signal 0.12; earlier agreeing candidates 1; earlier opposing candidates 0; strategy trailing
win rate 0.48".

## Target

Net P&L per contract in cents = pnl (dollars, 10 contracts, Kalshi direct fees, costs x1) / 10 x 100.
Not win/lose.

## Heads (2 settings = 2 variants)

- H1: ridge regression on the standardised embedding, alpha 10.
- H2: ridge regression on the standardised embedding, alpha 1000 (heavy shrinkage).
Standardisation is fit on the training weeks only. Decision rule (fixed): take the candidate if the
predicted net c/contract > 0.

## Benchmarks (same evaluation weeks)

No trade; take every candidate; posthoc-meta M1 logistic, taken from its committed results (07738c9,
results/posthoc_meta/results.csv), not recomputed.

## Report

Per head: trades; mean ROC (net / capital, capital as in posthoc-meta) with a game-bootstrap 95% CI
(2,000 reps, numpy default_rng seed 20261004, resampling games); net c/contract; correlation of the
prediction with realised net c/contract on the evaluation weeks; AUC of the prediction for y (reference
only); ROC excluding the top 5 games by P&L. No holdout. 2 variants, held for a later variants.csv commit
(no write here). Progress is logged in LEDGER.md.

## Tests (synthetic, before real data)

- The text builder reads no excluded column (a planted `fill`/`pnl` change leaves the text unchanged).
- The walk-forward never trains on week w or later.
- The encoder is deterministic (the same text gives the same vector).
- The decision rule does not use fill.
