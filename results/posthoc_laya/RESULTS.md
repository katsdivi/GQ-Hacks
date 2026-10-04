# Post-hoc Laya: results (training, walk-forward)

**Label: post-hoc, exploratory, generative-model encoder; not part of the submitted strategies.**

Spec: SPEC.md (6d49919, committed before any real data). Run on 2026-10-04 07:10 ET with scripts/posthoc_laya.py
(embed, then evaluate), on Apple M3 / 16 GB under nice -n 19. Model: frozen aac6fef/laya-mlx @20aed815
(ModernBERT-large 421M, FP16, MLX), mean-pooled encoder embeddings (1,024 dimensions), ridge head on past weeks only.
Candidate pool: posthoc-meta candidates.csv (sha256 a9ff5574...), 18,565 candidates (17,610 unique texts),
19 evaluation weeks (2025-09-08 onward), 17,216 evaluation candidates in 1,023 games.

Sanity check: the take-all book matches posthoc-meta's benchmark exactly (17,216 trades, -$5,625.86).

## Feasibility

| Item | Value |
|---|---|
| Install | pip from pypi.org into .venv-laya; laya-mlx 0.3.0 --no-deps from local clone ca5940a; repo lockfile mirror ignored |
| Weights | 807 MB on disk (846 MB listed), downloaded in 14.7 min; load 0.31 s |
| One noul question | p50 26.8 ms, p95 29.0 ms on M3 with other agents running |
| Encoder embedding | 8.1 ms per row |
| Fine-tuning in laya-mlx | none (upstream RLCD needs PyTorch, out of scope by Divi's instruction) |
| Determinism | identical within a batch; FP16 differs slightly across batch composition (max 0.013 on a 0.45 scale); the script encodes in fixed sorted chunks, so reruns reproduce |

## Walk-forward results (Kalshi direct, costs x1; game-bootstrap 95% CI, 2,000 reps, seed 20261004)

| Book | Trades | Games | ROC [95% CI] | c/contract | P&L | ROC excl. top 5 | Corr(pred, net) | AUC (ref) |
|---|---|---|---|---|---|---|---|---|
| No trade | 0 | 0 | 0 | | $0 | | | |
| Take all | 17,216 | 1,023 | -0.095 [-0.110, -0.080] | -3.27 | -$5,625.86 | -0.098 | | |
| H1 ridge alpha 10 | 5,735 | 979 | -0.098 [-0.126, -0.068] | -3.48 | -$1,996.95 | -0.111 | -0.013 | 0.508 |
| H2 ridge alpha 1000 | 3,066 | 934 | -0.078 [-0.132, -0.022] | -3.27 | -$1,003.28 | -0.098 | -0.009 | 0.525 |
| posthoc-meta M1 logistic (07738c9) | 2,463 | 938 | -0.121 [-0.222, -0.019] | -1.79 | -$440.12 | -0.161 | | |

## Verdict

No edge. Both heads lose, with CIs wholly below zero. Laya's frozen embedding carries no information about
net P&L: the out-of-sample correlation of prediction with realised net c/contract is about zero (and slightly
negative), and AUC is about 0.51 to 0.53. That is weaker than posthoc-meta's hand-built features, mainly
because this spec excludes the fill price, which was M1's strongest input and a post-t quantity. Under the
stop condition (CI lower bound > 0, Reality Check p < 0.05 cumulative, at least 100 trades, excl. top 5 > 0)
nothing qualifies, so a cumulative correction would not change the verdict and was not recomputed. No
holdout run. 2 variants (H1, H2), not written to variants.csv.

Latency note: at about 27 ms per decision on this Mac, Laya is fast enough to be a live decision layer for
the Kalshi-to-CME test (CME lags Kalshi by about 6.5 s). As a predictor on this data, it adds nothing.
