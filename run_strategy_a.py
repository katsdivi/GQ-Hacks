"""Strategy A on TRAINING games only (HYPOTHESIS_v3.md with Amendments 1 to 3; v3 Amendment 3 committed d349e50).

Runs strategy_a.evaluate_game on every training game (kickoff < 2026-08-01; the holdout is never loaded), then
reports per theta and leg (favorite, underdog placebo):
  games evaluated; skips by reason; trades entered; capped fills; mean fill price; win rate (ties 0.5) and
  win rate minus mean fill; mean return on capital (Webull and Kalshi-direct lines) with a game-level bootstrap
  95% CI (2,000 resamples, seed 20261003); total P&L on both lines.
Also: the selected theta by the v3 rule (strategy_a.select_theta), costs x2 for the selected theta (fees x2 and
the 1 cent half-spread x2, v3 Amendment 1), primary vs no-NFL-preseason side by side, and the v3 pre-registered
extras: NFL vs CFB, the selected theta without its top 5 games by P&L, without the incidentally seen games (v3
Disclosure items 1 to 3: NFL games Jan 4 to Jan 25, 2026, ET), and daily P&L metrics (by ET kickoff date).
Nothing is tuned. Appends one experiments/variants.csv row per theta and leg (6 rows).

Usage: python run_strategy_a.py   (outputs under out/strategy_a/, gitignored)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

import strategy_a as A

GAMES = Path("data/raw/kalshi_only_games.csv")
META = Path("data/raw/kalshi_market_meta.csv")
TICKS = Path("data/raw/kalshi_only")
OUT = Path("out/strategy_a")
VARIANTS = Path("experiments/variants.csv")
SEED, N_BOOT = 20261003, 2000
SKIPS = [("stale", lambda s: s.str.startswith("stale")),
         ("no pre-decision price", lambda s: s.str.startswith("no pre-decision price")),
         ("equal prices", lambda s: s.str.startswith("no favorite")),
         ("below theta", lambda s: s == "below theta"),
         ("no post-decision trade", lambda s: s == "no post-decision trade"),
         ("missing market", lambda s: s.str.startswith("missing market")),
         ("non-ESPN kickoff", lambda s: s.str.startswith("kickoff not from ESPN")),
         ("unsettled", lambda s: s == "unsettled")]


def boot_ci(x: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    """Game-level bootstrap: each entered row is one game (one trade per game per theta and leg)."""
    if len(x) < 2:
        return float("nan"), float("nan")
    m = x[rng.integers(0, len(x), size=(N_BOOT, len(x)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def table(rows: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (th, pl), r in rows.groupby(["theta", "placebo"]):
        e = r[r["entered"].astype(bool)]
        sk = r["skip"].fillna("").astype(str)
        row = {"theta": th, "leg": "placebo (underdog)" if pl else "favorite", "games": len(r)}
        for name, f in SKIPS:
            row[f"skip_{name}"] = int(f(sk).sum())
        row["entered"] = len(e)
        row["capped"] = int(e["fill_capped"].sum()) if len(e) else 0
        if len(e):
            rng = np.random.default_rng(SEED)
            wr, fp = e["payout"].mean(), e["fill_price"].mean()
            row.update(mean_fill=fp, win_rate=wr, win_minus_fill=wr - fp)
            for line in ("webull", "direct"):
                x = e[f"roc_{line}"].to_numpy(float)
                lo, hi = boot_ci(x, rng)
                row.update({f"roc_{line}": x.mean(), f"roc_{line}_ci_lo": lo, f"roc_{line}_ci_hi": hi,
                            f"pnl_{line}_total": e[f"pnl_{line}"].sum()})
        out.append(row)
    return pd.DataFrame(out)


def costs_x2(e: pd.DataFrame) -> pd.DataFrame:
    """Fees x2 and half-spread 2 cents (fill = trade + 2 cents, same cap). Fill = trade + 1 cent unless capped,
    so trade + 2 cents = fill + 1 cent; a capped fill stays at the cap."""
    cap = 1 - A.DEFAULT_TICK                      # every training market has a 0.01 step (v3 Amendment 3 section 3)
    p2 = np.minimum((e["fill_price"] + 0.01).round(4), cap)
    fw = 2 * p2.map(A.fee_webull)
    fd = 2 * p2.map(A.fee_kalshi_direct)
    gross = (e["payout"] - p2) * A.QTY
    return e.assign(fill_price=p2, pnl_webull=gross - fw, pnl_direct=gross - fd,
                    roc_webull=(gross - fw) / (p2 * A.QTY + fw), roc_direct=(gross - fd) / (p2 * A.QTY + fd))


def daily(e: pd.DataFrame) -> dict:
    d = e.groupby("date")["pnl_webull"].sum().sort_index()
    cum = d.cumsum()
    return {"days": len(d), "daily_mean": d.mean(), "daily_sd": d.std(ddof=1),
            "sharpe_daily": d.mean() / d.std(ddof=1) if len(d) > 1 and d.std(ddof=1) > 0 else float("nan"),
            "max_drawdown": float((cum.cummax() - cum).max())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    games = A.load_games(GAMES, META, ticks_dir=TICKS)
    assert all(g.kickoff < A.SEAL for g in games), "training only"
    rows = []
    for g in games:
        tr = pd.read_parquet(TICKS / f"{g.game_id}.parquet")
        for r in A.evaluate_game(tr, g):
            r.update(kickoff=g.kickoff, date=g.kickoff.tz_convert("America/New_York").date().isoformat())
            rows.append(r)
    rows = pd.DataFrame(rows)
    rows.drop(columns=[c for c in rows.columns if c.startswith("_")], errors="ignore").to_parquet(OUT / "rows.parquet")
    rng = np.random.default_rng(SEED)

    primary = table(rows).assign(sample="primary")
    nopre = table(rows[~rows["preseason"].astype(bool)]).assign(sample="no NFL preseason")
    both = pd.concat([primary, nopre], ignore_index=True)
    both.to_csv(OUT / "summary.csv", index=False)
    sel = A.select_theta(A.summarize(rows))

    ent = rows[rows["entered"].astype(bool)]
    fav_sel = ent[(ent["theta"] == sel) & ~ent["placebo"].astype(bool)] if sel is not None else ent.iloc[:0]
    x2 = costs_x2(fav_sel)
    lines = []
    if sel is not None:
        for line in ("webull", "direct"):
            x = x2[f"roc_{line}"].to_numpy(float)
            lo, hi = boot_ci(x, np.random.default_rng(SEED))
            lines.append({"what": f"costs x2, theta {sel}, {line}", "n": len(x), "roc_mean": x.mean(),
                          "ci_lo": lo, "ci_hi": hi, "pnl_total": x2[f"pnl_{line}"].sum()})
        top5 = fav_sel.nlargest(5, "pnl_webull").index
        for name, sub in [("NFL", fav_sel[fav_sel["league"] == "NFL"]), ("CFB", fav_sel[fav_sel["league"] == "CFB"]),
                          ("without top 5 games by P&L", fav_sel.drop(top5)),
                          ("without incidentally seen games (NFL, Jan 4 to 25, 2026 ET)",
                           fav_sel[~((fav_sel["league"] == "NFL") & fav_sel["date"].between("2026-01-04", "2026-01-25"))])]:
            x = sub["roc_webull"].to_numpy(float)
            lo, hi = boot_ci(x, np.random.default_rng(SEED))
            lines.append({"what": f"theta {sel}, webull, {name}", "n": len(x), "roc_mean": x.mean() if len(x) else np.nan,
                          "ci_lo": lo, "ci_hi": hi, "pnl_total": sub["pnl_webull"].sum()})
    extra = pd.DataFrame(lines)
    extra.to_csv(OUT / "selected_theta_checks.csv", index=False)
    dm = daily(fav_sel) if len(fav_sel) else {}

    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    var = []
    for r in primary.itertuples():
        e = ent[(ent["theta"] == r.theta) & (ent["placebo"].astype(bool) == (r.leg != "favorite"))]
        cents = float(((e["payout"] - e["fill_price"]) * A.QTY - e["fee_webull"]).sum() / (A.QTY * len(e)) * 100) if len(e) else ""
        var.append({"ts_utc": now, "git_sha": sha, "game_set": f"strategy_a training ({len(games)} games)",
                    "jump_cents": "", "window_s": "", "entry_gap": "", "timeout_s": "", "latency_s": A.LATENCY_S,
                    "n_games": r.games, "n_trades": r.entered, "edge_cents_mean": cents,
                    "notes": f"Strategy A v3+A1-A3; theta {r.theta}; {r.leg}; edge = net cents per contract (Webull); "
                             f"roc_webull {getattr(r, 'roc_webull', float('nan')):.5f}; "
                             f"roc_direct {getattr(r, 'roc_direct', float('nan')):.5f}; selected theta {sel}"})
    pd.DataFrame(var).to_csv(VARIANTS, mode="a", header=False, index=False)

    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(f"games loaded {len(games)}; selected theta (v3 rule) = {sel}; variants rows appended {len(var)}")
    print(both.round(4).to_string(index=False))
    print(extra.round(4).to_string(index=False))
    print("daily P&L (selected theta, favorite, Webull, by ET kickoff date):", {k: round(v, 4) for k, v in dm.items()})


if __name__ == "__main__":
    main()
