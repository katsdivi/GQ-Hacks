"""Render the tail of results/posthoc_mm_v4/demo.log to demo.png (matplotlib text; no screen capture available
to an agent). Paper-only demo."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WT = Path("/Users/divyamkataria/GQ HACKS/wt-mm-v4")
lines = (WT / "results/posthoc_mm_v4/demo.log").read_text().splitlines()
tail = lines[:1] + ["..."] + lines[-34:] if len(lines) > 36 else lines
fig = plt.figure(figsize=(16, 0.28 * len(tail) + 1))
fig.patch.set_facecolor("#111111")
fig.text(0.01, 0.99, "\n".join(tail), va="top", ha="left", family="monospace", fontsize=8.5, color="#e8e8e8")
fig.savefig(WT / "results/posthoc_mm_v4/demo.png", dpi=130, facecolor=fig.get_facecolor())
print("wrote demo.png,", len(tail), "lines")
