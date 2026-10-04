"""Training and simulation figures (holdout never read). PNGs under figures/, text 11 pt or larger.

  figures/synthetic_bias.png    trade xcorr vs book-mid xcorr on simulated games (no market prices): share of
                                studies where the rule declares a false "Kalshi leads" when the true lag is 0,
                                and the median measured lag, at about 5 and about 1 trades/min
                                (out/activity_bias_report.csv, out/activity_bias_quotes_report.csv;
                                docs/results/activity_bias.md)
  figures/a_theta_plateau.png   Strategy A ROC (Webull) with 95% CIs at theta 0.70 / 0.80 / 0.90, favorite vs
                                underdog placebo (out/strategy_a/summary.csv, sample "primary")
  figures/b_settings_plateau.png  Strategy B net cents per contract with 95% CIs, 8 settings, Webull and Kalshi
                                direct (out/strategy_b/summary.csv)

Reads existing outputs only; recomputes nothing. Usage: python scripts/make_figures.py
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

FIG = Path("figures")
BLUE, ORANGE = "#2a78d6", "#eb6834"           # categorical slots 1 and 2 (validated, light surface)
INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#898781", "#e6e5e1", "#fcfcfb"
SELECTED_THETA = 0.80
SELECTED_B = (0.05, 10, 300)


def style() -> None:
    plt.rcParams.update({
        "font.size": 11, "axes.titlesize": 13, "axes.labelsize": 11, "xtick.labelsize": 11, "ytick.labelsize": 11,
        "legend.fontsize": 11, "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
        "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
        "legend.frameon": False})


def pct(s: str) -> float:
    return float(re.match(r"\s*([\d.]+)%", s).group(1))


def synthetic_bias() -> Path:
    tr = pd.read_csv("out/activity_bias_report.csv")
    qu = pd.read_csv("out/activity_bias_quotes_report.csv")
    tr0, qu0 = tr[tr["case"] == "zero_lag"], qu[qu["case"] == "zero_lag"]
    # rows in file order: polymarket.com-like (about 5 trades/min, quotes streamed), then Polymarket-US-like
    # (about 1 trade/min, quotes polled once a second)
    assert tr0["pair"].iloc[0].endswith("5/min") and tr0["pair"].iloc[1].endswith("1/min")
    assert "polymarket.com" in qu0["pair"].iloc[0] and "1 s polled" in qu0["pair"].iloc[1]
    groups = ["about 5 trades/min\n(polymarket.com-like)", "about 1 trade/min\n(Polymarket-US-like)"]
    fp_t = [pct(s) for s in tr0["rule_says_kalshi_leads"]]
    fp_q = [pct(s) for s in qu0["rule_says_kalshi_leads"]]
    lag_t, lag_q = tr0["median_lag_s"].to_list(), qu0["median_lag_s"].to_list()

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    x, w = np.arange(2), 0.36
    for ax, (vt, vq), ylab, fmt, top in (
            (axes[0], (fp_t, fp_q), "False 'Kalshi leads' (% of 10 studies)", "{:.0f}%", 110),
            (axes[1], (lag_t, lag_q), "Median measured lag (s)", "{:+.0f} s", 6.5)):
        b1 = ax.bar(x - w / 2 - 0.01, vt, w, color=BLUE, label="Trade prices (3 s median)")
        b2 = ax.bar(x + w / 2 + 0.01, vq, w, color=ORANGE, label="Book midpoints")
        for bars, vals in ((b1, vt), (b2, vq)):
            for r, v in zip(bars, vals):
                ax.annotate(fmt.format(v), (r.get_x() + r.get_width() / 2, v), xytext=(0, 3),
                            textcoords="offset points", ha="center", va="bottom", color=INK2)
        ax.set_xticks(x, groups)
        ax.set_ylabel(ylab)
        ax.set_ylim(0, top)
    axes[0].set_title("False lead declared, true lag = 0", loc="left")
    axes[1].set_title("Measured lag, true lag = 0", loc="left")
    axes[0].legend(loc="upper left")
    fig.suptitle("Trade-based lead/lag is biased by trading activity; book midpoints are not (simulated, 400 games "
                 "per case)", x=0.01, ha="left", fontsize=12, color=INK)
    fig.text(0.01, 0.01, "Kalshi trades about 390/min in both cases. Source: out/activity_bias_report.csv and "
             "out/activity_bias_quotes_report.csv.", fontsize=11, color=MUTED)
    fig.tight_layout(rect=(0, 0.05, 1, 0.94))
    p = FIG / "synthetic_bias.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def a_theta_plateau() -> Path:
    s = pd.read_csv("out/strategy_a/summary.csv")
    s = s[s["sample"] == "primary"].copy()
    s["theta"] = s["theta"].round(2)
    fig, ax = plt.subplots(figsize=(9, 5))
    for leg, color, dx, label in (("favorite", BLUE, -0.006, "Favorite (the strategy)"),
                                  ("placebo (underdog)", ORANGE, 0.006, "Underdog (placebo)")):
        d = s[s["leg"] == leg].sort_values("theta")
        y = d["roc_webull"].to_numpy()
        err = np.vstack([y - d["roc_webull_ci_lo"].to_numpy(), d["roc_webull_ci_hi"].to_numpy() - y])
        ax.errorbar(d["theta"] + dx, y, yerr=err, fmt="o", ms=8, color=color, ecolor=color, elinewidth=2,
                    capsize=5, capthick=2, label=label, markeredgecolor=SURF, markeredgewidth=2)
        for th, v, n in zip(d["theta"], y, d["entered"]):
            ax.annotate(f"{v:+.3f}\n(n {n})", (th + dx, v), xytext=(14 if dx > 0 else -14, 0),
                        textcoords="offset points", ha="left" if dx > 0 else "right", va="center", color=INK2)
    ax.axhline(0, color=MUTED, lw=1)
    ax.axvspan(SELECTED_THETA - 0.02, SELECTED_THETA + 0.02, color=GRID, alpha=0.6, lw=0, zorder=0)
    ax.annotate("selected on training", (SELECTED_THETA, ax.get_ylim()[0]), xytext=(0, 6),
                textcoords="offset points", ha="center", va="bottom", color=MUTED)
    ax.set_xticks([0.70, 0.80, 0.90], ["0.70", "0.80", "0.90"])
    ax.set_xlim(0.64, 0.96)
    ax.set_xlabel("Theta (enter if the favorite's price is at least theta)")
    ax.set_ylabel("Return on capital per trade, Webull costs")
    ax.set_title("Strategy A on training: ROC by theta with 95% CIs (game bootstrap)", loc="left")
    ax.legend(loc="lower left")
    fig.text(0.01, 0.01, "10 contracts per trade, Webull $0.02/contract. Source: out/strategy_a/summary.csv "
             "(sample primary).", fontsize=11, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    p = FIG / "a_theta_plateau.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def b_settings_plateau() -> Path:
    s = pd.read_csv("out/strategy_b/summary.csv")
    assert len(s) == 8, f"expected 8 B settings, got {len(s)}"
    s = s.sort_values(["k", "m", "T"]).reset_index(drop=True)
    labels = [f"k {k * 100:.0f}c\nm {m:.0f}s\nT {T:.0f}s" for k, m, T in zip(s["k"], s["m"], s["T"])]
    x = np.arange(len(s))
    fig, ax = plt.subplots(figsize=(11, 5.2))
    for col, color, dx, label in (("edge_webull", BLUE, -0.12, "Webull ($0.02/contract per fill)"),
                                  ("edge_direct", ORANGE, 0.12, "Kalshi direct (taker fee)")):
        y = s[f"{col}_cents"].to_numpy()
        err = np.vstack([y - s[f"{col}_ci_lo"].to_numpy(), s[f"{col}_ci_hi"].to_numpy() - y])
        ax.errorbar(x + dx, y, yerr=err, fmt="o", ms=8, color=color, ecolor=color, elinewidth=2, capsize=4,
                    capthick=2, label=label, markeredgecolor=SURF, markeredgewidth=2)
    sel = int(s.index[(s["k"].round(2) == SELECTED_B[0]) & (s["m"] == SELECTED_B[1]) & (s["T"] == SELECTED_B[2])][0])
    ax.axvspan(sel - 0.4, sel + 0.4, color=GRID, alpha=0.6, lw=0, zorder=0)
    ax.axhline(0, color=MUTED, lw=1)
    ax.set_ylim(-6, 0.8)
    ax.annotate("selected", (sel, 0.8), xytext=(0, -4), textcoords="offset points", ha="center", va="top",
                color=MUTED)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Net cents per contract")
    ax.set_title("Strategy B on training: net edge for all 8 settings, with 95% CIs", loc="left")
    ax.legend(loc="center left", ncol=1)
    fig.text(0.01, 0.01, "Every setting nets about -5 c (Webull) / -3.7 c (direct): roughly the cost of trading. "
             "Source: out/strategy_b/summary.csv.", fontsize=11, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    p = FIG / "b_settings_plateau.png"
    fig.savefig(p, dpi=200)
    plt.close(fig)
    return p


def main() -> None:
    FIG.mkdir(exist_ok=True)
    style()
    for f in (synthetic_bias, a_theta_plateau, b_settings_plateau):
        print(f())


if __name__ == "__main__":
    main()
