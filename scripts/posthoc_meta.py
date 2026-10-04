"""Post-hoc meta-model over base strategies, walk-forward by ET week, TRAINING only.

post-hoc, exploratory; meta-model over strategies already seen to fail on training; walk-forward on training only.
Spec: results/posthoc_meta/SPEC.md (92f29b6, committed before any real-data run).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_meta.py      reads the gitignored base trade files listed in SPEC.md, writes
                                      results/posthoc_meta/ (summary CSVs, RESULTS.md; candidates.csv untracked)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

LABEL = ("post-hoc, exploratory; meta-model over strategies already seen to fail on training; "
         "walk-forward on training only")
ROOT = Path("/Users/divyamkataria/GQ HACKS")
SL = ROOT / "staleline"
OUT = Path("results/posthoc_meta")
SEED, N_BOOT = 20261004, 2000
MIN_WEEKS = 6
NS = 1_000_000_000
ET = "America/New_York"
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
NFL_OPENER_2025 = pd.Timestamp("2025-09-04").date()
ROUND_TRIP = {"B", "I10"}
DOW = list(range(7))


# ---------- loading ----------

def kickoffs() -> dict[str, pd.Timestamp]:
    a = pd.read_csv(SL / "data/raw/kalshi_only_games.csv")
    b = pd.read_csv(SL / "out/strategy_b/b_games_espn.csv")
    ko = dict(zip(a["game_id"], pd.to_datetime(a["kickoff_utc_espn"], utc=True)))
    ko.update({g: k for g, k in zip(b["game_id"], pd.to_datetime(b["espn_kickoff"], utc=True)) if g not in ko})
    return ko


def _std(df: pd.DataFrame, strat: str, leg, t_ns, team, fill, signal, pnl, fee, league=None) -> pd.DataFrame:
    out = pd.DataFrame({"strategy": strat, "leg": leg, "game_id": df["game_id"].to_numpy(),
                        "t_ns": np.asarray(t_ns, dtype="int64"), "team": np.asarray(team, dtype=object),
                        "fill": np.asarray(fill, float), "signal": np.asarray(signal, float),
                        "pnl": np.asarray(pnl, float), "fee": np.asarray(fee, float)})
    if league is not None:
        out["league"] = np.asarray(league, dtype=object)
    return out


def load_candidates() -> tuple[pd.DataFrame, list[str]]:
    ko = kickoffs()
    frames, missing = [], []

    def csv(p):
        p = ROOT / p
        if not p.exists():
            missing.append(str(p))
            return None
        return pd.read_csv(p)

    a = pd.read_parquet(SL / "out/strategy_a/rows.parquet")
    a = a[(a["theta"] == 0.80) & (~a["placebo"].astype(bool)) & (a["entered"].astype(bool))]
    k = pd.to_datetime(a["kickoff"], utc=True)
    frames.append(_std(a, "A", "favorite", (k - pd.Timedelta(minutes=5)).astype("int64"), a["team"],
                       a["fill_price"], 0.0, a["pnl_direct"], a["fee_direct"], a["league"]))

    b = pd.read_parquet(SL / "out/strategy_b/trades.parquet")
    b = b[(b["k"] == 0.05) & (b["m"] == 10) & (b["T"] == 300) & (b["filled"].astype(bool))]
    side = np.where(b["direction"] > 0, "home", "away")
    fill = np.where(b["direction"] > 0, b["entry_px"], 1 - b["entry_px"])
    frames.append(_std(b, "B", "signal", b["entry_dec_ns"].astype("int64"), side, fill,
                       b["d_at_entry_cents"].abs() / 100, b["pnl_direct"], b["fee_direct"]))

    d = csv("wt-idea4/results/posthoc_idea4/training_trades.csv")
    if d is not None:
        d = d[d["theta"] == 0.90]
        frames.append(_std(d, "I4", d["leg"], d["t_ns"], d["team"], d["fill"], d["signal_px"], d["pnl_direct"],
                           d["fee_direct"], d["league"]))
    d = csv("wt-idea7/results/posthoc_idea7/training_trades.csv")
    if d is not None:
        d = d[(d["k"] == 0.02) & d["entered"].astype(bool)]
        frames.append(_std(d, "I7", d["leg"], d["t_ns"], d["team"], d["fill"], d["g"], d["pnl_direct"],
                           d["fee_direct"], d["league"]))
    d = csv("wt-idea8/results/posthoc_idea8/training_trades.csv")
    if d is not None:
        d = d[d["x"] == 0.2]
        frames.append(_std(d, "I8", d["leg"], d["t_ns"], d["team"], d["fill"], d["I"].abs(), d["pnl_direct"],
                           d["fee_direct"], d["league"]))
    d = csv("wt-idea9/results/posthoc_idea9/training_trades.csv")
    if d is not None:
        d = d[(d["k"] == 0.10) & (d["delay"] == 60)]
        frames.append(_std(d, "I9", d["leg"], d["t_ns"], d["team"], d["fill"], d["g"], d["pnl_direct"],
                           d["fee_direct"], d["league"]))
    d = csv("wt-idea10/results/posthoc_idea10/training_trades.csv")
    if d is not None:
        d = d[(d["s"] == 0.10) & d["entered"].astype(bool)]
        frames.append(_std(d, "I10", d["leg"], d["t_ns"], d["team"], d["entry"], d["m"], d["pnl_direct"],
                           d["fee_direct"], d["league"]))
    d = csv("wt-idea12/results/posthoc_idea12/training_trades.csv")
    if d is not None:
        d = d[(d["k"] == 0.03) & d["entered"].astype(bool)]
        team = d["market"].astype(str).str.split("-").str[-1]
        frames.append(_std(d, "I12", d["leg"], d["t_ns"], team, d["fill"], d["g"], d["pnl_direct"],
                           d["fee_direct"]))
    d = csv("wt-idea13/results/posthoc_idea13/training_trades.csv")
    if d is not None:
        d = d[(d["e"] == 0.02) & d["entered"].astype(bool)]
        frames.append(_std(d, "I13", d["leg"], d["t_ns"], d["team"], d["fill"], d["gap"], d["pnl_direct"],
                           d["fee_direct"], d["league"]))

    c = pd.concat(frames, ignore_index=True)
    if "league" not in c:
        c["league"] = None
    c["league"] = c["league"].fillna(c["game_id"].str.split("_").str[0].str.upper())
    c["kickoff_ns"] = c["game_id"].map(lambda g: ko[g].value if g in ko else np.nan)
    c = c[c["kickoff_ns"].notna()].copy()
    assert (c["kickoff_ns"] < SEAL.value).all(), "training only"
    c = c[c["pnl"].notna() & c["fill"].notna()].reset_index(drop=True)
    return c, missing


# ---------- features (each uses only data at or before the candidate's own t) ----------

def team_side(game_id: str, team) -> str:
    if team in ("home", "away"):
        return team
    parts = str(game_id).split("_")
    t = str(team).lower()
    if len(parts) >= 4 and t == parts[-1]:
        return "home"
    if len(parts) >= 4 and t == parts[-2]:
        return "away"
    return "unknown"


def agreement(c: pd.DataFrame) -> pd.DataFrame:
    """Counts of OTHER candidates in the same game with decision time strictly before t, same / opposite side."""
    same = np.zeros(len(c), int)
    opp = np.zeros(len(c), int)
    for _, g in c.groupby("game_id"):
        idx = g.index.to_numpy()
        ts = g["t_ns"].to_numpy()
        sd = g["side"].to_numpy()
        for j, i in enumerate(idx):
            if sd[j] == "unknown":
                continue
            earlier = ts < ts[j]
            known = sd != "unknown"
            same[i] = int((earlier & known & (sd == sd[j])).sum())
            opp[i] = int((earlier & known & (sd != sd[j])).sum())
    return pd.DataFrame({"agree_same": same, "agree_opp": opp}, index=c.index)


def trailing_winrate(c: pd.DataFrame) -> pd.Series:
    """Per strategy cell: (wins + 1) / (n + 2) over candidates with ET date strictly before this one's ET date."""
    out = pd.Series(0.5, index=c.index)
    for _, g in c.groupby("cell"):
        g = g.sort_values("date")
        win = (g["pnl"] > 0).astype(int)
        by_day = pd.DataFrame({"date": g["date"], "w": win}).groupby("date")["w"].agg(["sum", "count"])
        cum_w = by_day["sum"].cumsum().shift(1, fill_value=0)
        cum_n = by_day["count"].cumsum().shift(1, fill_value=0)
        rate = (cum_w + 1) / (cum_n + 2)
        out.loc[g.index] = g["date"].map(rate).to_numpy()
    return out


def add_features(c: pd.DataFrame) -> pd.DataFrame:
    c = c.copy()
    tet = pd.to_datetime(c["t_ns"], utc=True).dt.tz_convert(ET)
    c["date"] = tet.dt.date
    c["week"] = (tet.dt.tz_localize(None).dt.normalize()
                 - pd.to_timedelta(tet.dt.dayofweek, unit="D")).dt.date
    c["dow"] = tet.dt.dayofweek
    c["cell"] = c["strategy"] + ":" + c["leg"].astype(str)
    c["cfb"] = (c["league"].str.upper() == "CFB").astype(int)
    c["preseason"] = ((c["league"].str.upper() == "NFL") & (c["date"] < NFL_OPENER_2025)).astype(int)
    c["min_from_ko"] = (c["t_ns"] - c["kickoff_ns"]) / (60 * NS)
    c["side"] = [team_side(g, t) for g, t in zip(c["game_id"], c["team"])]
    c[["agree_same", "agree_opp"]] = agreement(c)
    c["trail_wr"] = trailing_winrate(c)
    c["breakeven"] = np.where(c["strategy"].isin(ROUND_TRIP), 0.5 + c["fee"] / 10, c["fill"] + c["fee"] / 10)
    c["capital"] = c["fill"] * 10 + c["fee"]
    c["roc"] = c["pnl"] / c["capital"]
    c["y"] = (c["pnl"] > 0).astype(int)
    return c


NUM = ["fill", "signal", "cfb", "preseason", "min_from_ko", "agree_same", "agree_opp", "trail_wr"]


def design(c: pd.DataFrame, cells: list[str]) -> np.ndarray:
    """Feature matrix: numeric allowed features + one-hot cell + one-hot day of week. Only these columns."""
    X = [c[NUM].to_numpy(float)]
    X.append(np.column_stack([(c["cell"] == k).to_numpy(float) for k in cells]))
    X.append(np.column_stack([(c["dow"] == d).to_numpy(float) for d in DOW]))
    return np.nan_to_num(np.hstack(X))


# ---------- models ----------

class Logit:
    """L2 logistic regression, C = 1.0 (penalty 1/(2C) ||w||^2, intercept unpenalized), standardized inputs."""

    def __init__(self, C: float = 1.0):
        self.C = C

    def fit(self, X, y):
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd == 0] = 1
        Z = (X - self.mu) / self.sd
        Z1 = np.hstack([np.ones((len(Z), 1)), Z])

        def f(w):
            z = Z1 @ w
            ll = np.sum(np.logaddexp(0, z) - y * z)
            pen = 0.5 / self.C * np.sum(w[1:] ** 2)
            g = Z1.T @ (1 / (1 + np.exp(-z)) - y)
            g[1:] += w[1:] / self.C
            return ll + pen, g

        self.w = minimize(f, np.zeros(Z1.shape[1]), jac=True, method="L-BFGS-B").x
        return self

    def predict_proba(self, X):
        Z = (X - self.mu) / self.sd
        return 1 / (1 + np.exp(-(self.w[0] + Z @ self.w[1:])))


class Tree:
    """Depth-3 Gini decision tree, min 30 samples per leaf, leaf value = mean y (deterministic)."""

    def __init__(self, depth: int = 3, min_leaf: int = 30):
        self.depth, self.min_leaf = depth, min_leaf

    def _build(self, X, y, d):
        node = {"p": float(y.mean()) if len(y) else 0.5}
        if d == 0 or len(y) < 2 * self.min_leaf or y.min() == y.max():
            return node
        best = None
        for j in range(X.shape[1]):
            xs = np.unique(X[:, j])
            if len(xs) < 2:
                continue
            cuts = (xs[:-1] + xs[1:]) / 2
            if len(cuts) > 32:
                cuts = np.unique(np.quantile(X[:, j], np.linspace(0.03, 0.97, 32)))
            for cut in cuts:
                L = X[:, j] <= cut
                nl = L.sum()
                if nl < self.min_leaf or len(y) - nl < self.min_leaf:
                    continue
                pl, pr = y[L].mean(), y[~L].mean()
                gini = nl * pl * (1 - pl) + (len(y) - nl) * pr * (1 - pr)
                if best is None or gini < best[0] - 1e-12:
                    best = (gini, j, cut, L)
        if best is None:
            return node
        _, j, cut, L = best
        node.update(j=j, cut=cut, l=self._build(X[L], y[L], d - 1), r=self._build(X[~L], y[~L], d - 1))
        return node

    def fit(self, X, y):
        self.root = self._build(X, y.astype(float), self.depth)
        return self

    def predict_proba(self, X):
        out = np.empty(len(X))
        for i, x in enumerate(X):
            n = self.root
            while "j" in n:
                n = n["l"] if x[n["j"]] <= n["cut"] else n["r"]
            out[i] = n["p"]
        return out


def ridge_pred(Xtr, ytr, Xte, alpha=1.0):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd[sd == 0] = 1
    Z = (Xtr - mu) / sd
    Z1 = np.hstack([np.ones((len(Z), 1)), Z])
    P = alpha * np.eye(Z1.shape[1])
    P[0, 0] = 0
    w = np.linalg.solve(Z1.T @ Z1 + P, Z1.T @ ytr)
    return w[0] + ((Xte - mu) / sd) @ w[1:]


# ---------- walk-forward ----------

def eval_weeks(c: pd.DataFrame) -> list:
    weeks = sorted(c["week"].unique())
    return weeks[MIN_WEEKS:]


def walk_forward(c: pd.DataFrame, make_model) -> pd.DataFrame:
    """For each eval week w: fit on weeks < w only, predict week w. Returns c rows of eval weeks with p, take."""
    cells = sorted(c["cell"].unique())
    rows = []
    for w in eval_weeks(c):
        tr, te = c[c["week"] < w], c[c["week"] == w]
        assert (tr["week"] < w).all() and len(te)
        m = make_model().fit(design(tr, cells), tr["y"].to_numpy())
        p = m.predict_proba(design(te, cells))
        rows.append(te.assign(p=p, take=p > te["breakeven"].to_numpy(), fit_n=len(tr)))
    return pd.concat(rows) if rows else c.iloc[:0].assign(p=[], take=[])


def walk_forward_ridge(c: pd.DataFrame) -> pd.DataFrame:
    cells = sorted(c["cell"].unique())
    rows = []
    for w in eval_weeks(c):
        tr, te = c[c["week"] < w], c[c["week"] == w]
        rows.append(te.assign(pred=ridge_pred(design(tr, cells), tr["pnl"].to_numpy(), design(te, cells))))
    return pd.concat(rows)


def best_cell_benchmark(c: pd.DataFrame, min_trades: int = 20) -> pd.DataFrame:
    rows = []
    for w in eval_weeks(c):
        tr = c[c["week"] < w]
        s = tr.groupby("cell")["roc"].agg(["mean", "count"])
        s = s[s["count"] >= min_trades]
        if s.empty:
            continue
        best = s.sort_values("mean", ascending=False).index[0]
        rows.append(c[(c["week"] == w) & (c["cell"] == best)].assign(chosen=best))
    return pd.concat(rows) if rows else c.iloc[:0]


# ---------- metrics ----------

def game_boot_ci(e: pd.DataFrame) -> tuple[float, float]:
    if e["game_id"].nunique() < 2:
        return float("nan"), float("nan")
    g = e.groupby("game_id")["roc"].agg(["sum", "count"])
    s, n = g["sum"].to_numpy(), g["count"].to_numpy()
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(g), size=(N_BOOT, len(g)))
    m = s[idx].sum(1) / n[idx].sum(1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def metrics(e: pd.DataFrame, name: str) -> dict:
    out = {"label": LABEL, "book": name, "trades": len(e), "games": e["game_id"].nunique() if len(e) else 0}
    if len(e) == 0:
        return out
    lo, hi = game_boot_ci(e)
    daily = e.groupby("date")["pnl"].sum().sort_index()
    sd = daily.std(ddof=1) if len(daily) > 1 else float("nan")
    cum = np.concatenate([[0.0], daily.cumsum().to_numpy()])
    gp = e.groupby("game_id")["pnl"].sum().sort_values(ascending=False)
    keep = e[~e["game_id"].isin(gp.index[:5])]
    out.update(roc_mean=float(e["roc"].mean()), roc_ci_lo=lo, roc_ci_hi=hi,
               net_c_per_contract=float(e["pnl"].sum() / (10 * len(e)) * 100), pnl_total=float(e["pnl"].sum()),
               hit_rate=float(e["y"].mean()), mean_breakeven=float(e["breakeven"].mean()),
               game_days=len(daily), sharpe_daily=float(daily.mean() / sd) if sd and sd == sd and sd > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()), worst_day=float(daily.min()),
               excl_top5_roc=float(keep["roc"].mean()) if len(keep) else float("nan"),
               excl_top5_pnl=float(keep["pnl"].sum()))
    out["sharpe_x365"] = out["sharpe_daily"] * np.sqrt(365) if out["sharpe_daily"] == out["sharpe_daily"] else float("nan")
    return out


def breakdown(e: pd.DataFrame, name: str, by: str = "cell") -> pd.DataFrame:
    if len(e) == 0:
        return pd.DataFrame()
    g = e.groupby(by).agg(trades=("pnl", "size"), hit_rate=("y", "mean"), mean_breakeven=("breakeven", "mean"),
                          mean_roc=("roc", "mean"), pnl_total=("pnl", "sum"))
    g["hit_minus_breakeven"] = g["hit_rate"] - g["mean_breakeven"]
    return g.reset_index().assign(book=name, label=LABEL)


def main() -> None:
    c, missing = load_candidates()
    c = add_features(c)
    OUT.mkdir(parents=True, exist_ok=True)
    c.to_csv(OUT / "candidates.csv", index=False)          # per-candidate, gitignored
    weeks = eval_weeks(c)
    ev = c[c["week"].isin(weeks)]
    print(f"{LABEL}\ncandidates {len(c)}; eval weeks {len(weeks)} ({weeks[0]} to {weeks[-1]}); missing {missing}",
          flush=True)
    m1 = walk_forward(c, lambda: Logit(1.0))
    print("M1 done", flush=True)
    m2 = walk_forward(c, lambda: Tree(3, 30))
    print("M2 done", flush=True)
    rg = walk_forward_ridge(c)
    bb = best_cell_benchmark(c)
    tab = pd.DataFrame([metrics(m1[m1["take"]], "M1 logistic"), metrics(m2[m2["take"]], "M2 tree depth 3"),
                        metrics(rg[rg["pred"] > 0], "secondary: ridge pred > 0"),
                        metrics(ev, "benchmark a: all candidates"),
                        metrics(bb, "benchmark b: best cell walk-forward"),
                        {"label": LABEL, "book": "benchmark c: no trade", "trades": 0, "pnl_total": 0.0}])
    tab.to_csv(OUT / "results.csv", index=False)
    picks = pd.concat([breakdown(m1[m1["take"]], "M1 logistic"), breakdown(m2[m2["take"]], "M2 tree depth 3"),
                       breakdown(bb, "benchmark b: best cell walk-forward")])
    picks.to_csv(OUT / "picks_by_cell.csv", index=False)
    who = pd.concat([breakdown(ev, "eval weeks, all candidates", "cell"),
                     breakdown(ev, "eval weeks, all candidates", "league")])
    who.to_csv(OUT / "what_gets_what_right.csv", index=False)
    corr = float(np.corrcoef(rg["pred"], rg["pnl"])[0, 1])
    auc = {}
    for nm, m in (("M1", m1), ("M2", m2)):
        pos, neg = m.loc[m["y"] == 1, "p"].to_numpy(), m.loc[m["y"] == 0, "p"].to_numpy()
        r = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
        auc[nm] = float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))
    extra = pd.DataFrame([{"label": LABEL, "candidates": len(c), "eval_candidates": len(ev), "eval_weeks": len(weeks),
                           "first_eval_week": str(weeks[0]), "last_eval_week": str(weeks[-1]),
                           "ridge_oos_corr": corr, "m1_oos_auc": auc["M1"], "m2_oos_auc": auc["M2"],
                           "best_cells_chosen": "; ".join(f"{k}:{v}" for k, v in
                                                          bb.groupby("week")["chosen"].first().value_counts().items()),
                           "missing_inputs": "; ".join(missing)}])
    extra.to_csv(OUT / "diagnostics.csv", index=False)
    c.groupby("cell").size().rename("candidates").to_csv(OUT / "candidates_per_cell.csv")
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(tab.round(4).to_string(index=False))
    print(extra.T.to_string())


if __name__ == "__main__":
    sys.exit(main())
