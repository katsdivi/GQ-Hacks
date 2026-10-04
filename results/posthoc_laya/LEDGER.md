# Laya ledger (ET)

- 06:45 a782639 code review (clean; uv.lock mirror ignored)
- 06:46 60505f6 research (zero-shot 0.36 vs fine-tuned 0.77 upstream; fine-tune needs torch, so frozen encoder + head)
- 06:50 .venv-laya created (Python 3.13); mlx 0.32.3, numpy, huggingface-hub, tokenizers, pandas, pyarrow, scipy from pypi.org; laya-mlx 0.3.0 --no-deps -e from local clone ca5940a
- 06:51 weight download started: aac6fef/laya-mlx @ 20aed815 (846 MB); slow (about 50 MB/min)
- SPEC.md, script and 4 synthetic tests committed before any real data is encoded
- 07:04 weights complete (807 MB, 14.7 min); load 0.31 s; noul p50 26.8 ms, p95 29.0 ms; embed 8.1 ms/row
- 07:05 determinism: same batch identical; FP16 cross-batch diff max 0.013 (fixed sorted chunks keep reruns identical)
- 07:10 embed run: 17,610 unique texts, 18,565 candidates, 5.0 min
- 07:11 evaluate: H1 ROC -0.098 [-0.126, -0.068], H2 -0.078 [-0.132, -0.022]; corr(pred, net) about 0; no edge
