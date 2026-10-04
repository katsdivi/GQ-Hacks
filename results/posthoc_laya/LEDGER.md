# Laya ledger (ET)

- 06:45 a782639 code review (clean; uv.lock mirror ignored)
- 06:46 60505f6 research (zero-shot 0.36 vs fine-tuned 0.77 upstream; fine-tune needs torch, so frozen encoder + head)
- 06:50 .venv-laya created (Python 3.13); mlx 0.32.3, numpy, huggingface-hub, tokenizers, pandas, pyarrow, scipy from pypi.org; laya-mlx 0.3.0 --no-deps -e from local clone ca5940a
- 06:51 weight download started: aac6fef/laya-mlx @ 20aed815 (846 MB); slow (about 50 MB/min)
- SPEC.md, script and 4 synthetic tests committed before any real data is encoded
