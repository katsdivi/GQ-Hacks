# Laya-MLX code review (before running anything)

Reviewed 2026-10-04 ~06:50 ET. Source: github.com/mizorewww/laya-mlx, cloned by Divi to
`/Users/divyamkataria/GQ HACKS/wt-laya-ext/laya-mlx`, HEAD `ca5940a` ("Sync upstream runtime fixes and
automate v0.3.0 releases"), package version 0.3.0. Nothing from the repo was executed for this review.

## Files read

README.md, pyproject.toml, uv.lock (sources only), LICENSE (Apache-2.0), NOTICE, .github/workflows
(ci.yml, release.yml), scripts/prepare_hub.py, and all of laya_mlx/ (agent, model, common, prepared,
tokenizer, convert, cli, router, presets, email, lang, shortlist, snake/*), scanned for network,
process, credential and serialisation calls.

## Findings

| Check | Result |
|---|---|
| Network calls | Only `huggingface_hub.snapshot_download` in `agent.resolve_model`, restricted by `allow_patterns` to `model.safetensors`, `rl_agent_config.json`, `encoder/config.json`, `tokenizer/*`, `mlx_config.json`. No requests/urllib/socket use anywhere in `laya_mlx/` or `scripts/`. |
| Telemetry | None in the library. The Snake demo sets `HF_HUB_DISABLE_TELEMETRY=1` and `HF_HUB_OFFLINE=1`. |
| Subprocess | Only in the Snake demo (not used here): `sysctl -n machdep.cpu.brand_string` for a hardware label, and `ffmpeg` for rendering a replay video. Neither is on the inference path. |
| Downloaded executables | None. Weights are safetensors loaded with `mx.load`; no pickle, no `trust_remote_code`, no `eval`/`exec`. |
| Credentials | `router.py` reads `HF_TOKEN` from the environment if set (normal Hub behaviour; only for gated repos). We set no token and use public repos only. No keychain or file credential access. |
| Install scripts | Pure hatchling build; no setup.py, no post-install hooks. |
| License | Apache-2.0 (code). Weights from Convai Innovations; model cards carry their own license. |

## One supply-chain flag (not malicious, but avoid)

`uv.lock` pins every dependency to a third-party PyPI mirror,
`https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/` (74 of 75 packages). That is a public
university mirror the author evidently used locally, but installing through it means trusting a mirror
instead of PyPI. Mitigation used here: do NOT run `uv sync` with this lock. Install with pip from the
official PyPI index into a separate venv: the four runtime dependencies (`mlx>=0.32.2,<0.33`,
`numpy`, `huggingface-hub`, `tokenizers`) are well-known packages, then install the local source
(`pip install --no-deps -e`) so no other code is pulled.

## Capability facts relevant to the test

- Inference only. README: "This repository provides inference and conversion; RLCD training and
  fine-tuning remain in the upstream project" (NandhaKishorM/laya). No adapter/LoRA training in laya-mlx.
- Question types: `choice` (probabilities over labels), `score` (ordinal rubric, expected level),
  `noul` (P(true) for a proposition). No free numeric output; a win probability has to be a `noul`.
- `embed_fn_from_agent(agent)` mean-pools the loaded ModernBERT encoder with no extra weights, so a
  frozen-encoder plus trained-head arm is possible entirely in MLX.
- Checkpoints (public Hugging Face, FP16 MLX conversions): `aac6fef/laya-mlx` (421M, ModernBERT-large,
  512 ctx), `aac6fef/laya-multilingual-mlx` (322M), `aac6fef/laya-typed-decisions-mlx` (421M, 1,024 ctx).

## Verdict

No suspicious behaviour found in the library. Safe to install from official PyPI plus local source, with
the mirror lockfile ignored. Only public weight downloads from Hugging Face will hit the network.
