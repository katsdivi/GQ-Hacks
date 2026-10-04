"""Lead test figure: real vs placebo lag distributions per venue test, from the ONE holdout run's outputs.

Reads only what scripts/final_test_run.py wrote (never recomputes): <results>/lead_<test>_per_game.csv (qualifying
games, column lag_s), <results>/lead_<test>_placebo.csv (column lag_s) and <results>/lead_decisions.json, for
the two tests "polymarket.com" and "Polymarket US". One panel per test: share of games at each lag (whole
seconds, positive = Kalshi first), real games vs the unrelated-games placebo, with the run's own decision text.

Do not run before the holdout run exists: with the default --results results/holdout it refuses if that folder
is missing. Tested on fake inputs only (tests/test_fig_lead_test.py, --results <tmp>).

Usage: python scripts/fig_lead_test.py [--results results/holdout] [--out figures/lead_test_real_vs_placebo.png]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_figures as MF  # noqa: E402  (shared style and palette)

TESTS = ("polymarket.com", "Polymarket US")
MAX_LAG = 15


def load(results: Path, test: str) -> tuple[np.ndarray, np.ndarray]:
    pg = pd.read_csv(results / f"lead_{test}_per_game.csv")
    q = pg["qualifying"].fillna(False).astype(bool) if "qualifying" in pg else pd.Series(False, index=pg.index)
    real = pd.to_numeric(pg.loc[q, "lag_s"], errors="coerce").dropna().to_numpy(float)
    pl = pd.to_numeric(pd.read_csv(results / f"lead_{test}_placebo.csv")["lag_s"], errors="coerce").dropna()
    return real, pl.to_numpy(float)


def shares(x: np.ndarray, bins: np.ndarray) -> np.ndarray:
    return np.array([(np.round(x) == b).mean() if len(x) else 0.0 for b in bins])


def describe(d: dict) -> str:
    def f(k, fmt):
        v = d.get(k)
        return fmt.format(v) if isinstance(v, (int, float)) and v == v else "n/a"
    return (f"Result: {d.get('result', 'n/a')}\n"
            f"n real {d.get('n_qualifying', 'n/a')}, n placebo {d.get('n_placebo', 'n/a')}\n"
            f"median lag {f('median_corrected_lag_s', '{:+.1f}')} s (placebo {f('placebo_median_s', '{:+.1f}')} s)\n"
            f"Mann-Whitney p {f('mann_whitney_p', '{:.3g}')} (Holm level {f('holm_level', '{:.3g}')})")


def make(results: Path, out: Path) -> Path:
    MF.style()
    dec = json.loads((results / "lead_decisions.json").read_text())
    bins = np.arange(-MAX_LAG, MAX_LAG + 1)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharey=True)
    w = 0.42
    for ax, test in zip(axes, TESTS):
        real, pl = load(results, test)
        ax.bar(bins - w / 2 - 0.01, shares(real, bins), w, color=MF.BLUE, label="Real games")
        ax.bar(bins + w / 2 + 0.01, shares(pl, bins), w, color=MF.ORANGE, label="Placebo (unrelated games)")
        ax.axvline(0, color=MF.MUTED, lw=1)
        ax.set_title(f"Kalshi vs {test}", loc="left")
        ax.set_xlabel("Lag (s), positive = Kalshi moves first")
        ax.set_xticks(np.arange(-MAX_LAG, MAX_LAG + 1, 5))
        ax.text(0.02, 0.97, describe(dec.get(test, {})), transform=ax.transAxes, va="top", ha="left",
                fontsize=11, color=MF.INK2, bbox={"facecolor": MF.SURF, "edgecolor": "none", "pad": 2})
    axes[0].set_ylabel("Share of games")
    axes[0].set_ylim(0, max(0.05, max(a.get_ylim()[1] for a in axes)) * 1.45)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper left", bbox_to_anchor=(0.01, 0.92), ncol=2)
    fig.suptitle("Lead test (holdout, book midpoints): real vs placebo lag per game", x=0.01, ha="left",
                 fontsize=13, color=MF.INK)
    src = results if not results.is_absolute() else Path(results.name)
    fig.text(0.01, 0.01, f"Source: {src}/lead_*_per_game.csv, lead_*_placebo.csv, lead_decisions.json "
             "(scripts/final_test_run.py).", fontsize=11, color=MF.MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.86))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=Path("results/holdout"))
    ap.add_argument("--out", type=Path, default=Path("figures/lead_test_real_vs_placebo.png"))
    a = ap.parse_args(argv)
    if not (a.results / "lead_decisions.json").exists():
        print(f"{a.results}/lead_decisions.json not found: run only after the holdout run has written its outputs")
        return 1
    print(make(a.results, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
