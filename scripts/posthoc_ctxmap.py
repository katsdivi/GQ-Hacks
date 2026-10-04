"""Post-hoc context map: which idea-leg is right in which context, walk-forward by ET week, TRAINING only.

post-hoc, exploratory; context map over strategies already seen; walk-forward on training only; holdout not run.
Spec: results/posthoc_ctxmap/SPEC.md (7f9599e). Metrics helpers copied from posthoc-meta scripts/posthoc_meta.py
(3da957a): game_boot_ci, metrics.

Usage (cwd = repo root):
  python scripts/posthoc_ctxmap.py [--pool ../wt-meta/results/posthoc_meta/candidates.csv]
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

LABEL = "post-hoc, exploratory; context map over strategies already seen; walk-forward on training only; holdout not run"
POOL = Path("../wt-meta/results/posthoc_meta/candidates.csv")
OUT = Path("results/posthoc_ctxmap")
SEED, N_BOOT = 20261004, 2000
MIN_WEEKS = 6
NS = (20, 50)
BENCH_MIN = 20
ROUND_TRIP = ("B:", "I10:")      # not hold-to-settlement: excluded from win rate vs break-even
USED = ["cell", "game_id", "t_ns", "week", "date", "league", "min_from_ko", "fill", "pnl", "roc", "y", "breakeven"]


def load(path: Path) -> pd.DataFrame:
    c = pd.read_csv(path)
    c = c[USED].copy()                                   # only the spec's columns enter the map
    c["week"] = c["week"].astype(str)
    c["date"] = c["date"].astype(str)
    return add_context(c)


def phase(m: pd.Series) -> pd.Series:
    return np.where(m < 0, "pre", np.where(m <= 90, "early", "late"))


def band(p: pd.Series) -> pd.Series:
    return np.where(p < 0.35, "lo", np.where(p <= 0.65, "mid", "hi"))


def add_context(c: pd.DataFrame) -> pd.DataFrame:
    c = c.copy()
    c["ctx"] = c["league"].astype(str) + "|" + phase(c["min_from_ko"]) + "|" + band(c["fill"])
    c["cpc"] = c["pnl"] / 10 * 100                       # net cents per contract
    # one position per game per idea-leg: keep the earliest decision
    c = c.sort_values(["t_ns", "cell", "game_id"], kind="stable").drop_duplicates(["cell", "game_id"], keep="first")
    return c.reset_index(drop=True)


def eval_weeks(c: pd.DataFrame) -> list[str]:
    return sorted(c["week"].unique())[MIN_WEEKS:]


def choose(past: pd.DataFrame, n_min: int) -> dict[str, str]:
    """Best eligible idea-leg per context from past rows only. Tie: more trades, then cell name."""
    s = past.groupby(["ctx", "cell"])["cpc"].agg(score="mean", n="size").reset_index()
    s = s[(s["n"] >= n_min) & (s["score"] > 0)]
    if s.empty:
        return {}
    s = s.sort_values(["ctx", "score", "n", "cell"], ascending=[True, False, False, True], kind="stable")
    return dict(s.groupby("ctx").head(1)[["ctx", "cell"]].itertuples(index=False, name=None))


def walk_forward(c: pd.DataFrame, n_min: int) -> tuple[pd.DataFrame, dict]:
    taken, picks = [], {}
    for w in eval_weeks(c):
        past = c[c["week"] < w]
        assert (past["week"] < w).all()
        ch = choose(past, n_min)
        picks[w] = ch
        te = c[c["week"] == w]
        sel = te[[ch.get(x) == cell for x, cell in zip(te["ctx"], te["cell"])]]
        taken.append(sel.assign(chosen_week=w))
    e = pd.concat(taken) if taken else c.iloc[:0]
    return e, picks


def best_single(c: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for w in eval_weeks(c):
        s = c[c["week"] < w].groupby("cell")["cpc"].agg(["mean", "size"])
        s = s[s["size"] >= BENCH_MIN].sort_values(["mean", "size"], ascending=[False, False])
        if s.empty:
            continue
        rows.append(c[(c["week"] == w) & (c["cell"] == s.index[0])])
    return pd.concat(rows) if rows else c.iloc[:0]


def stability(picks: dict) -> tuple[int, int]:
    weeks = sorted(picks)
    changes = pairs = 0
    for a, b in zip(weeks, weeks[1:]):
        for x in set(picks[a]) & set(picks[b]):
            pairs += 1
            changes += picks[a][x] != picks[b][x]
    return changes, pairs


# ---------- metrics (copied from posthoc_meta.py, 3da957a) ----------

def game_boot_ci(e: pd.DataFrame) -> tuple[float, float]:
    if e["game_id"].nunique() < 2:
        return float("nan"), float("nan")
    g = e.groupby("game_id")["roc"].agg(["sum", "count"])
    s, n = g["sum"].to_numpy(), g["count"].to_numpy()
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(g), size=(N_BOOT, len(g)))
    m = s[idx].sum(1) / n[idx].sum(1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def metrics(e: pd.DataFrame, name: str, n_weeks: int) -> dict:
    out = {"label": LABEL, "book": name, "trades": len(e), "games": e["game_id"].nunique() if len(e) else 0}
    if len(e) == 0:
        return {**out, "share_weeks_traded": 0.0}
    lo, hi = game_boot_ci(e)
    daily = e.groupby("date")["pnl"].sum().sort_index()
    sd = daily.std(ddof=1) if len(daily) > 1 else float("nan")
    cum = np.concatenate([[0.0], daily.cumsum().to_numpy()])
    gp = e.groupby("game_id")["pnl"].sum().sort_values(ascending=False)
    keep = e[~e["game_id"].isin(gp.index[:5])]
    hs = e[~e["cell"].str.startswith(ROUND_TRIP)]
    out.update(roc_mean=float(e["roc"].mean()), roc_ci_lo=lo, roc_ci_hi=hi,
               net_c_per_contract=float(e["pnl"].sum() / (10 * len(e)) * 100), pnl_total=float(e["pnl"].sum()),
               hts_trades=len(hs), hts_win_rate=float(hs["y"].mean()) if len(hs) else float("nan"),
               hts_breakeven=float(hs["breakeven"].mean()) if len(hs) else float("nan"),
               game_days=len(daily),
               sharpe_daily=float(daily.mean() / sd) if sd == sd and sd > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()), worst_day=float(daily.min()),
               excl_top5_roc=float(keep["roc"].mean()) if len(keep) else float("nan"),
               excl_top5_pnl=float(keep["pnl"].sum()),
               share_weeks_traded=e["week"].nunique() / n_weeks)
    out["sharpe_x365"] = out["sharpe_daily"] * np.sqrt(365) if out["sharpe_daily"] == out["sharpe_daily"] else float("nan")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", type=Path, default=POOL)
    a = ap.parse_args()
    sha = hashlib.sha256(a.pool.read_bytes()).hexdigest()
    c = load(a.pool)
    weeks = eval_weeks(c)
    ev = c[c["week"].isin(weeks)]
    print(f"{LABEL}\npool {a.pool} sha256 {sha}; candidates {len(c)}; eval weeks {len(weeks)} "
          f"({weeks[0]} to {weeks[-1]}); eval candidates {len(ev)}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    rows, brk, stab, pick_rows = [], [], [], []
    for n in NS:
        e, picks = walk_forward(c, n)
        rows.append(metrics(e, f"context map N={n}", len(weeks)))
        if len(e):
            g = e.groupby(["ctx", "cell"]).agg(trades=("pnl", "size"), pnl_total=("pnl", "sum"),
                                               net_c_per_contract=("cpc", "mean"), mean_roc=("roc", "mean"))
            brk.append(g.reset_index().assign(book=f"N={n}", label=LABEL))
        ch, pr = stability(picks)
        stab.append({"book": f"N={n}", "choice_changes": ch, "consecutive_pairs": pr,
                     "contexts_ever_traded": len({x for p in picks.values() for x in p}), "label": LABEL})
        pick_rows += [{"book": f"N={n}", "week": w, "ctx": x, "cell": cl} for w, p in picks.items() for x, cl in p.items()]
    rows.append(metrics(ev, "take every candidate", len(weeks)))
    rows.append(metrics(best_single(c), "best single idea-leg, walk-forward", len(weeks)))
    rows.append({"label": LABEL, "book": "no trade", "trades": 0, "games": 0, "pnl_total": 0.0, "roc_mean": 0.0,
                 "share_weeks_traded": 0.0})
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / "walkforward_results.csv", index=False)
    (pd.concat(brk) if brk else pd.DataFrame()).to_csv(OUT / "breakdown_by_context.csv", index=False)
    pd.DataFrame(stab).to_csv(OUT / "stability.csv", index=False)
    pd.DataFrame(pick_rows).to_csv(OUT / "weekly_choices.csv", index=False)
    # DESCRIPTIVE ONLY: full-training map (in-sample)
    full = c.groupby(["ctx", "cell"])["cpc"].agg(c_per_contract="mean", trades="size").reset_index()
    best = (full.sort_values(["ctx", "c_per_contract", "trades"], ascending=[True, False, False])
            .groupby("ctx").head(1).assign(note="DESCRIPTIVE ONLY, in-sample on all training; not a result",
                                            label=LABEL))
    best.to_csv(OUT / "descriptive_full_training_map.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(tab.round(4).to_string(index=False))
    print(pd.DataFrame(stab).to_string(index=False))
    print(best.round(3).to_string(index=False))
    for b in brk:
        print(b.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
