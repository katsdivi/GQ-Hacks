"""Note figures that do not need the t17 merge. PNGs under paper/figs/, text 11 pt or larger.

  paper/figs/lag_distribution.png   lead test (pre-registered, holdout): per-game lag, real vs placebo, both venues,
                                    from results/holdout/lead_<test>_per_game.csv (qualifying, lag_s) and
                                    lead_<test>_placebo.csv (lag_s), with the run's decision from lead_decisions.json
  paper/figs/pmus_laggard_confirmed.png  Polymarket US laggard (exploratory, post-run): the run curve (mean net
                                    c/contract with game-bootstrap CI by latency) from results/holdout_diag/
                                    g_latency_curves.csv, and the partial (before 17:00 ET Oct 3) all-fills vs
                                    both-legs-confirmed results from h4_run_summary.csv; both read read-only via
                                    `git show 5c24dbe:<path>`

Usage: python scripts/note_figures.py
"""
from __future__ import annotations

import io
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "paper" / "figs"
DIAG = "5c24dbe"
BLUE, ORANGE = "#2a78d6", "#eb6834"                # categorical slots 1 and 2 (validated on the light surface)
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#898781", "#e6e5e1", "#fcfcfb"


def style() -> None:
    plt.rcParams.update({
        "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 11, "xtick.labelsize": 11, "ytick.labelsize": 11,
        "legend.fontsize": 11, "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "axes.grid.axis": "y",
        "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True, "legend.frameon": False})


def show(path: str, skip_banner: bool = False) -> pd.DataFrame:
    raw = subprocess.run(["git", "-C", str(ROOT), "show", f"{DIAG}:{path}"], check=True, capture_output=True).stdout
    return pd.read_csv(io.BytesIO(raw), skiprows=1 if skip_banner else 0)


def lag_distribution() -> Path:
    res = ROOT / "results" / "holdout"
    dec = json.loads((res / "lead_decisions.json").read_text())
    bins = np.arange(-15, 16)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), sharey=True)
    w = 0.42
    for ax, test in zip(axes, ("polymarket.com", "Polymarket US")):
        pg = pd.read_csv(res / f"lead_{test}_per_game.csv")
        real = pg.loc[pg["qualifying"].fillna(False).astype(bool), "lag_s"].dropna().round().to_numpy()
        pl = pd.read_csv(res / f"lead_{test}_placebo.csv")["lag_s"].dropna().round().to_numpy()
        ax.bar(bins - w / 2 - 0.01, [(real == b).mean() for b in bins], w, color=BLUE, label="Real games")
        ax.bar(bins + w / 2 + 0.01, [(pl == b).mean() for b in bins], w, color=ORANGE, label="Placebo (unrelated games)")
        ax.axvline(0, color=MUTED, lw=1)
        d = dec[test]
        ax.set_title(f"Kalshi vs {test}", loc="left")
        ax.text(0.02, 0.97, f"{d['result']}\nn real {d['n_qualifying']}, placebo {d['n_placebo']}\n"
                f"median lag {d['median_corrected_lag_s']:+.1f} s (placebo {d['placebo_median_s']:+.1f} s)\n"
                f"Mann-Whitney p {d['mann_whitney_p']:.3g} (Holm level {d['holm_level']:.3g})",
                transform=ax.transAxes, va="top", ha="left", color=INK2,
                bbox={"facecolor": SURF, "edgecolor": "none", "pad": 2})
        ax.set_xlabel("Lag (s), positive = Kalshi moves first")
        ax.set_xticks(np.arange(-15, 16, 5))
    axes[0].set_ylabel("Share of games")
    top = max(a.get_ylim()[1] for a in axes)
    axes[0].set_ylim(0, top * 1.35)
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper left", bbox_to_anchor=(0.01, 0.92), ncol=2)
    fig.suptitle("Lead test (pre-registered, holdout, book midpoints): per-game lag, real vs placebo", x=0.01,
                 ha="left", fontsize=13, color=INK)
    fig.text(0.01, 0.01, "Source: results/holdout/lead_*_per_game.csv, lead_*_placebo.csv, lead_decisions.json "
             "(RUN_COMMIT 872ff43).", fontsize=11, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.86))
    p = FIG / "lag_distribution.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def pmus_laggard_confirmed() -> Path:
    c = show("results/holdout_diag/g_latency_curves.csv")
    c = c[c["venue"] == "polymarket_us"].sort_values("latency_s")
    h4 = show("results/holdout_diag/h4_run_summary.csv", skip_banner=True)
    fig, ax = plt.subplots(figsize=(11, 5.4))
    ax.fill_between(c["latency_s"], c["edge_ci_low"], c["edge_ci_high"], color=BLUE, alpha=0.15, lw=0)
    ax.plot(c["latency_s"], c["edge_cents_mean"], color=BLUE, lw=2, marker="o", ms=6,
            label="Run's fills on polled quotes, all games (95% CI band)")
    for st, color, mk, lab in (("all subset fills", BLUE, "s", "Same rule, partial sample (before 17:00 ET)"),
                               ("both legs confirmed", ORANGE, "D", "Partial sample, both legs confirmed by a real trade")):
        x = h4[h4["set"] == st].sort_values("latency_s")
        y = x["mean_net_c_per_contract"].to_numpy()
        err = np.vstack([y - x["ci95_low"].to_numpy(), x["ci95_high"].to_numpy() - y])
        off = 0.08 if st.startswith("both") else -0.08
        ax.errorbar(x["latency_s"] + off, y, yerr=err, fmt=mk, ms=8, color=color, ecolor=color, elinewidth=2,
                    capsize=4, mfc=SURF if st.startswith("all") else color, mew=2, label=lab)
        for lat, v, n in zip(x["latency_s"], y, x["n_fills"]):
            ax.annotate(f"n {n}", (lat + off, v), xytext=(10, 0), textcoords="offset points", va="center", color=INK2)
    ax.axhline(0, color=MUTED, lw=1)
    ax.set_xlabel("Latency from decision to fill (s)")
    ax.set_ylabel("Net cents per contract")
    ax.set_title("Polymarket US laggard: polled-quote fills vs fills confirmed by real trades (exploratory, post-run)",
                 loc="left")
    ax.legend(loc="center right")
    fig.text(0.01, 0.01, f"Source: git show {DIAG}:results/holdout_diag/g_latency_curves.csv and h4_run_summary.csv "
             "(partial: before 17:00 ET Oct 3).", fontsize=11, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    p = FIG / "pmus_laggard_confirmed.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    style()
    for f in (lag_distribution, pmus_laggard_confirmed):
        print(f())


if __name__ == "__main__":
    main()
