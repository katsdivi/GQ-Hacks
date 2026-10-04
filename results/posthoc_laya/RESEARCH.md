# Laya / Jev: how people use it, and fine-tuning

Researched 2026-10-04 ~06:50 ET. Sources at the end. Several are secondary write-ups; the upstream repo
README is the primary source for the training workflow.

## What it is

Laya (Convai Innovations, upstream github.com/NandhaKishorM/laya) is a non-autoregressive "System 1"
decision model: ModernBERT encoder plus a decision Transformer and heads. It takes a state plus typed
questions and returns calibrated probabilities in one forward pass. It is the open counterpart of
TypeSafe AI's Jev. laya-mlx is an inference-only MLX port.

## Zero-shot is weak (matches what Divi heard)

On the upstream typed-decisions benchmark (2,000 decisions, four workflows), the base English checkpoint
scores 0.362 accuracy zero-shot, "only slightly above the random baseline". The fine-tuned
laya-typed-decisions checkpoint scores 0.766 on the same decisions. Every write-up stresses that the
value comes from specialising the model on a stable decision surface.

## Fine-tuning recipe (upstream, not in laya-mlx)

- Files: `notebooks/laya_finetune_typed_decisions_2xT4_kaggle.ipynb` (CUDA, 2x T4) and
  `notebooks/laya_finetune_typed_decisions_mps.py` (Apple Silicon MPS/CPU).
- Method: RLCD, training against strictly proper scoring rules (not plain cross-entropy), so outputs
  stay calibrated. Then per-option-count temperature fitting on held-out labelled data
  (`fit_abstention_thresholds()`), optional histogram-binning recalibration (`fit_binning_map()`), and
  export.
- Cost: "two free T4 GPUs for a few hours" for the published fine-tune. Requires PyTorch 2.14+.
- Data format: the state plus typed question, with the correct label per row, the same schema as inference.

## Question schemas

- `choice`: per-option probabilities (classification/routing).
- `score`: ordinal rubric, expected level.
- `noul`: P(true) for a yes/no proposition. This is the natural fit for "this team wins" or "this
  price is too low".
- No direct numeric regression output.

## Pitfalls reported upstream

- Position bias across option slots; validate `option_order` permutations.
- Accuracy degrades on long contexts (> ~4,000 preceding tokens on multilingual).
- Precision shifts probabilities (bf16 up to +-0.073, fp16 +-0.019); fit thresholds in the target dtype.
- The shipped calibration temperature for 11+ options is 0.10, which laya-mlx clamps to [0.5, 5.0].
- Confidence is not accuracy on a new task.

## Trading use found

- "Jev-Trader" uses Jev as a fast BUY/HOLD/SELL decision layer over structured market signals. It is an
  architecture experiment, with no published backtest or edge.
- No source reports a validated trading or prediction-market edge from Laya or Jev.
- Reddit and X returned nothing indexed.

## Implication for this test

A full RLCD fine-tune of the 421M model needs PyTorch (multi-GB install) and hours of GPU time. That does
not fit on this 16 GB M3, shared with other agents, before the 09:30 ET cap. The practical fine-tune arm,
as Divi allowed, is a frozen Laya encoder plus a trained head:
- mean-pooled ModernBERT embeddings via `laya_mlx.embed_fn_from_agent`;
- a logistic/ridge head fit on past weeks only.
Zero-shot `noul` is kept only as a reference baseline, given its documented weakness.

Sources:
- https://github.com/NandhaKishorM/laya
- https://themenonlab.blog/blog/laya-local-system-1-decision-model
- https://shop.zimaspace.com/blogs/tech-ai-hub/laya-open-source-decision-model-local-ai
- https://huggingface.co/team-od/laya-thai
- https://www.llmreference.com/model/laya-typed-decisions
- https://www.orcarouter.ai/it/blog/jev-vs-laya
- https://www.producthunt.com/posts/predict-with-jev
- https://aiidelist.com/blog/what-is-laya-mlx.md
