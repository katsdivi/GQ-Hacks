"""Post-hoc broad search over existing strategies, 54-trial fixed grid, walk-forward on TRAINING only, with
White's Reality Check, Hansen SPA, Romano-Wolf, Holm and deflated Sharpe corrections.

post-hoc, exploratory; broad search over strategies already seen to fail on training; walk-forward on training
only; every grid point is a trial; holdout not run. Spec: results/posthoc_search/SPEC.md (93f3ca6).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_search.py   reads ../wt-meta/results/posthoc_meta/candidates.csv (gitignored; regenerate
                                     with scripts/posthoc_meta.py on branch posthoc-meta), writes
                                     results/posthoc_search/ (summary CSVs, RESULTS.md; trades.csv untracked)
"""
from __future__ import annotations

import hashlib
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

LABEL = ("post-hoc, exploratory; broad search over strategies already seen to fail on training; walk-forward on "
         "training only; every grid point is a trial; holdout not run")
POOL = Path("/Users/divyamkataria/GQ HACKS/wt-meta/results/posthoc_meta/candidates.csv")
POOL_SHA = "a9ff5574a0457f79a557ea834a51e3821f991ba78e247dfa613216a64d108c33"
OUT = Path("results/posthoc_search")
SEED, N_BOOT, BLOCK = 20261004, 2000, 5
MIN_WEEKS = 6
N_PRIOR_VARIANTS = 77
IDEAS = ["A", "B", "I4", "I7", "I8", "I9", "I10", "I12", "I13"]
HYP_LEGS = {"A:favorite", "B:signal", "I4:favorite", "I7:signal", "I8:fade", "I9:signal", "I10:fade",
            "I12:signal", "I13:signal"}
ROUND_TRIP = {"B", "I10"}
FINE_CELLS = [f"{s}:{l}" for s, ls in (("I7", ("signal", "placebo")), ("I8", ("fade", "placebo")),
                                       ("I9", ("signal", "placebo")), ("I12", ("signal", "placebo")),
                                       ("I13", ("signal", "placebo"))) for l in ls]
QUANTS = [0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
BANDS = {"ge080": (0.80, 1.01), "le020": (-0.01, 0.20), "040to060": (0.40, 0.60)}


# ---------- data ----------

def load(path: Path = POOL, check_sha: bool = True) -> pd.DataFrame:
    if check_sha:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == POOL_SHA, "candidate pool changed"
    c = pd.read_csv(path)
    return prep(c)


def prep(c: pd.DataFrame) -> pd.DataFrame:
    c = c.copy()
    c["cell"] = c["strategy"] + ":" + c["leg"]
    c["pre"] = c["min_from_ko"] <= 0
    c["size"] = 10
    c = c.sort_values(["t_ns", "game_id", "cell"], kind="stable").reset_index(drop=True)
    c["uid"] = np.arange(len(c))
    return c


def eval_weeks(c: pd.DataFrame) -> list:
    return sorted(c["week"].unique())[MIN_WEEKS:]


def c_per_contract(df: pd.DataFrame) -> float:
    return float(df["pnl"].sum() / (10 * len(df)) * 100) if len(df) else float("nan")


# ---------- a) consensus ----------

def consensus(c: pd.DataFrame, m: int, pre_only: bool, legs: str) -> pd.DataFrame:
    """First candidate per (game, team) at which >= m distinct ideas have a candidate with t <= its t."""
    d = c[c["cell"].isin(HYP_LEGS)] if legs == "hyp" else c
    if pre_only:
        d = d[d["pre"]]
    out = []
    for _, g in d.groupby(["game_id", "team"], sort=False):
        g = g.sort_values(["t_ns", "uid"])
        seen = set()
        for r in g.itertuples():
            seen.add(r.strategy)
            if len(seen) >= m:
                out.append(r.uid)
                break
    return c[c["uid"].isin(out)]


# ---------- b) online weighting ----------

def daily_rewards(c: pd.DataFrame, cells: list) -> pd.DataFrame:
    r = c.groupby(["date", "cell"])["roc"].mean().clip(-1, 1).unstack().reindex(columns=cells)
    return r.sort_index()


def hedge(c: pd.DataFrame, eta: float) -> pd.DataFrame:
    cells = sorted(c["cell"].unique())
    R = daily_rewards(c, cells)
    logw = np.zeros(len(cells))
    take_dates = {}
    for d in R.index:                      # weights at start of date d use dates < d only
        w = np.exp(logw - logw.max())
        w /= w.sum()
        take_dates[d] = {cells[i] for i in range(len(cells)) if w[i] > 1 / len(cells) + 1e-12}
        logw = logw + eta * np.nan_to_num(R.loc[d].to_numpy(), nan=0.0)
    mask = [r.cell in take_dates.get(r.date, set()) for r in c.itertuples()]
    return c[np.array(mask, dtype=bool)]


def thompson(c: pd.DataFrame) -> pd.DataFrame:
    cells = sorted(c["cell"].unique())
    rng = np.random.default_rng(SEED)
    wins = dict.fromkeys(cells, 0)
    losses = dict.fromkeys(cells, 0)
    be_sum = dict.fromkeys(cells, 0.0)
    be_n = dict.fromkeys(cells, 0)
    take = set()
    for d, day in c.groupby("date", sort=True):
        draw = {k: rng.beta(1 + wins[k], 1 + losses[k]) for k in cells}
        for k in cells:
            be = be_sum[k] / be_n[k] if be_n[k] else 0.5
            if draw[k] > be:
                take.update(day.loc[day["cell"] == k, "uid"])
        for r in day.itertuples():         # update after the date (settled)
            wins[r.cell] += int(r.y)
            losses[r.cell] += 1 - int(r.y)
            be_sum[r.cell] += r.breakeven
            be_n[r.cell] += 1
    return c[c["uid"].isin(take)]


# ---------- c) price filters ----------

def in_band(df: pd.DataFrame, band: str) -> pd.Series:
    lo, hi = BANDS[band]
    return (df["fill"] >= lo) & (df["fill"] <= hi)


def price_filter(c: pd.DataFrame, band: str, min_n: int = 20) -> pd.DataFrame:
    out = []
    for w in eval_weeks(c):
        past = c[(c["week"] < w) & in_band(c, band)]
        s = past.groupby("cell")["pnl"].agg(["mean", "count"])
        ok = s[(s["count"] >= min_n) & (s["mean"] > 0)].index
        cur = c[(c["week"] == w) & in_band(c, band) & c["cell"].isin(ok)]
        out.append(cur)
    return pd.concat(out) if out else c.iloc[:0]


# ---------- d) context x consensus ----------

def contexts(df: pd.DataFrame) -> pd.Series:
    ph = np.where(df["min_from_ko"] <= 0, "pre", np.where(df["min_from_ko"] <= 90, "early", "late"))
    pb = np.where(df["fill"] < 0.35, "lo", np.where(df["fill"] <= 0.65, "mid", "hi"))
    return pd.Series(df["league"].astype(str).to_numpy() + "|" + ph + "|" + pb, index=df.index)


def with_agreement(c: pd.DataFrame) -> pd.Series:
    """Number of OTHER distinct ideas with a candidate on the same game and team at or before t."""
    n = pd.Series(0, index=c.index)
    for _, g in c.groupby(["game_id", "team"], sort=False):
        g = g.sort_values(["t_ns", "uid"])
        seen = []
        for idx, r in zip(g.index, g.itertuples()):
            seen.append(r.strategy)
            n[idx] = len(set(seen) - {r.strategy})
    return n


def ctx_consensus(c: pd.DataFrame, n_min: int) -> pd.DataFrame:
    d = c[c["agree_other"] >= 1].copy()
    d["ctx"] = contexts(d)
    out = []
    for w in eval_weeks(c):
        past, cur = d[d["week"] < w], d[d["week"] == w]
        if past.empty or cur.empty:
            continue
        s = past.groupby(["ctx", "cell"])["pnl"].agg(["mean", "count"]).reset_index()
        s = s[(s["count"] >= n_min) & (s["mean"] > 0)]
        s = s.sort_values(["ctx", "mean", "count", "cell"], ascending=[True, False, False, True])
        best = s.drop_duplicates("ctx").set_index("ctx")["cell"]
        out.append(cur[cur["ctx"].map(best).eq(cur["cell"])])
    return pd.concat(out) if out else c.iloc[:0]


# ---------- e) finer thresholds ----------

def fine_threshold(c: pd.DataFrame, cell: str, min_n: int = 20) -> pd.DataFrame:
    d = c[c["cell"] == cell].assign(a=lambda x: x["signal"].abs())
    out = []
    for w in eval_weeks(c):
        past, cur = d[d["week"] < w], d[d["week"] == w]
        if past.empty or cur.empty:
            continue
        best = None
        for q in QUANTS:
            cut = float(np.quantile(past["a"], q))
            sel = past[past["a"] >= cut]
            if len(sel) < min_n:
                continue
            m = sel["pnl"].mean()
            if best is None or m > best[0]:
                best = (m, cut)
        if best is None or best[0] <= 0:
            continue
        out.append(cur[cur["a"] >= best[1]])
    return (pd.concat(out) if out else d.iloc[:0]).drop(columns="a")


# ---------- f) sizing ----------

def fee_direct(p: float, s: int) -> float:
    raw = Decimal("0.07") * Decimal(s) * Decimal(str(round(p, 4))) * (1 - Decimal(str(round(p, 4))))
    return float(raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def sized(c: pd.DataFrame, book: pd.DataFrame) -> pd.DataFrame:
    if book.empty:
        return book
    parts = []
    for w, cur in book.groupby("week"):
        past = c[c["week"] < w].groupby("cell")["pnl"].mean().sort_values()
        cells = list(past.index)
        k = len(cells)
        size = {}
        for i, cell in enumerate(cells):      # bottom k//3 cells 5, next k//3 cells 10, the rest 20 (16 -> 5, 5, 6)
            size[cell] = 5 if i < k // 3 else (10 if i < 2 * (k // 3) else 20)
        s = cur["cell"].map(size).fillna(10).astype(int)
        cur = cur.assign(size=s)
        parts.append(cur)
    b = pd.concat(parts)
    rt = b["strategy"].isin(ROUND_TRIP)
    new_fee = np.array([fee_direct(p, s) for p, s in zip(b["fill"], b["size"])])
    gross10 = b["pnl"] + b["fee"]
    pnl = np.where(rt, b["pnl"] * b["size"] / 10, gross10 * b["size"] / 10 - new_fee)
    fee = np.where(rt, b["fee"] * b["size"] / 10, new_fee)
    cap = b["capital"] * b["size"] / 10 - b["fee"] * b["size"] / 10 + fee
    return b.assign(pnl=pnl, fee=fee, capital=cap, roc=pnl / cap)


# ---------- metrics ----------

def boot_roc(e: pd.DataFrame) -> tuple[float, float, float]:
    """Contract-weighted mean ROC, game bootstrap CI and one-sided p = P(mean <= 0)."""
    if e["game_id"].nunique() < 2:
        return float("nan"), float("nan"), float("nan")
    g = e.assign(wr=e["roc"] * e["size"]).groupby("game_id").agg(s=("wr", "sum"), n=("size", "sum"))
    s, n = g["s"].to_numpy(), g["n"].to_numpy()
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(g), size=(N_BOOT, len(g)))
    m = s[idx].sum(1) / n[idx].sum(1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)), float((m <= 0).mean())


def daily_series(e: pd.DataFrame, cal: pd.Index) -> pd.Series:
    return e.groupby("date")["pnl"].sum().reindex(cal, fill_value=0.0) if len(e) else pd.Series(0.0, index=cal)


def metrics(e: pd.DataFrame, name: str, family: str, cal: pd.Index) -> dict:
    out = {"label": LABEL, "trial": name, "family": family, "trades": len(e),
           "contracts": int(e["size"].sum()) if len(e) else 0, "games": e["game_id"].nunique() if len(e) else 0}
    if len(e) == 0:
        return out
    lo, hi, p = boot_roc(e)
    gd = e.groupby("date")["pnl"].sum().sort_index()
    sd = gd.std(ddof=1) if len(gd) > 1 else float("nan")
    cum = np.concatenate([[0.0], gd.cumsum().to_numpy()])
    gp = e.groupby("game_id")["pnl"].sum().sort_values(ascending=False)
    keep = e[~e["game_id"].isin(gp.index[:5])]
    cs = daily_series(e, cal)
    out.update(roc=float((e["roc"] * e["size"]).sum() / e["size"].sum()), roc_ci_lo=lo, roc_ci_hi=hi, p_boot=p,
               net_c_per_contract=float(e["pnl"].sum() / e["size"].sum() * 100), pnl_total=float(e["pnl"].sum()),
               game_days=len(gd), sharpe_daily=float(gd.mean() / sd) if sd == sd and sd > 0 else float("nan"),
               cal_sharpe_daily=float(cs.mean() / cs.std(ddof=1)) if cs.std(ddof=1) > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()), worst_day=float(gd.min()),
               excl_top5_roc=float((keep["roc"] * keep["size"]).sum() / keep["size"].sum()) if len(keep) else float("nan"),
               excl_top5_pnl=float(keep["pnl"].sum()))
    out["sharpe_x365"] = out["sharpe_daily"] * np.sqrt(365) if out["sharpe_daily"] == out["sharpe_daily"] else float("nan")
    return out


# ---------- multiple testing ----------

def stationary_bootstrap_idx(n: int, reps: int, block: float, rng: np.random.Generator) -> np.ndarray:
    idx = np.empty((reps, n), dtype=int)
    p = 1.0 / block
    for b in range(reps):
        i = rng.integers(n)
        for t in range(n):
            if t > 0 and rng.random() < p:
                i = rng.integers(n)
            elif t > 0:
                i = (i + 1) % n
            idx[b, t] = i
    return idx


def reality_check(D: np.ndarray, reps: int = N_BOOT, block: float = BLOCK, seed: int = SEED) -> dict:
    """D: n dates x K trials of daily P&L (benchmark zero). White RC, Hansen SPA_c, Romano-Wolf stepdown."""
    n, K = D.shape
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_idx(n, reps, block, rng)
    mu = D.mean(0)
    mub = D[idx].mean(1)                                   # reps x K
    dev = np.sqrt(n) * (mub - mu)
    v = np.sqrt(n) * mu
    rc_p = float((dev.max(1) >= v.max()).mean())
    # Hansen SPA (consistent): studentized, poor trials recentred
    om = dev.std(0, ddof=1)
    om = np.where(om > 0, om, np.inf)
    t = v / om
    keep = mu >= -om / np.sqrt(n) * np.sqrt(2 * np.log(np.log(n)))
    gc = np.where(keep, mu, 0.0)
    tb = (np.sqrt(n) * (mub - mu + gc)) / om
    spa_p = float((np.maximum(tb.max(1), 0) >= max(t.max(), 0)).mean())
    # Romano-Wolf stepdown on non-studentized statistics
    order = np.argsort(-v)
    adj = np.empty(K)
    remaining = list(order)
    prev = 0.0
    for k in order:
        mx = dev[:, remaining].max(1)
        pk = max(float((mx >= v[k]).mean()), prev)
        adj[k] = pk
        prev = pk
        remaining.remove(k)
    return {"rc_p": rc_p, "spa_p": spa_p, "rw_p": adj, "best": int(order[0])}


def holm(p: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    m = len(p)
    order = np.argsort(p)
    rej = np.zeros(m, dtype=bool)
    for i, k in enumerate(order):
        if np.isnan(p[k]) or p[k] > alpha / (m - i):
            break
        rej[k] = True
    return rej


def deflated(r: np.ndarray, trial_srs: list, n_trials: int) -> float:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import report_book as RB
    return RB.deflated_sharpe(r, trial_srs, n_trials)


# ---------- in-sample best ----------

def in_sample_best(ev: pd.DataFrame, min_n: int = 30) -> dict:
    best = None
    n = 0
    for cell, d in ev.groupby("cell"):
        a = d["signal"].abs()
        for q in QUANTS:
            cut = float(np.quantile(a, q))
            for band in ("all", *BANDS):
                n += 1
                sel = d[(a >= cut) & (in_band(d, band) if band != "all" else True)]
                if len(sel) < min_n:
                    continue
                r = sel["roc"].mean()
                if best is None or r > best["roc"]:
                    best = {"cell": cell, "quantile": q, "cut": cut, "band": band, "trades": len(sel), "roc": float(r),
                            "net_c_per_contract": c_per_contract(sel), "pnl_total": float(sel["pnl"].sum())}
    best["n_combinations"] = n
    return best


# ---------- run ----------

def all_books(c: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    ev_weeks = set(eval_weeks(c))
    c = c.assign(agree_other=with_agreement(c))
    base = []
    for m in (2, 3):
        for pre in (False, True):
            for legs in ("hyp", "all"):
                base.append((f"a_consensus_m{m}_{'pre' if pre else 'allphase'}_{legs}", "a",
                             consensus(c, m, pre, legs)))
    for eta in (0.1, 0.5):
        base.append((f"b_hedge_eta{eta}", "b", hedge(c, eta)))
    base.append(("b_thompson", "b", thompson(c)))
    for band in BANDS:
        base.append((f"c_price_{band}", "c", price_filter(c, band)))
    for nm in (20, 50):
        base.append((f"d_ctx_consensus_N{nm}", "d", ctx_consensus(c, nm)))
    fine = []
    for cell in FINE_CELLS:
        b = fine_threshold(c, cell)
        fine.append(b)
        base.append((f"e_fine_{cell.replace(':', '_')}", "e", b))
    base.append(("e_fine_union", "e", pd.concat(fine) if fine else c.iloc[:0]))
    base = [(n, f, b[b["week"].isin(ev_weeks)]) for n, f, b in base]
    sized_books = [(n + "_sized", "f", sized(c, b)) for n, f, b in base]
    return base + sized_books


def main() -> None:
    c = load()
    ev = c[c["week"].isin(eval_weeks(c))]
    cal = pd.Index(sorted(ev["date"].unique()))
    print(f"{LABEL}\npool {len(c)}; eval weeks {len(eval_weeks(c))}; eval candidates {len(ev)}; dates {len(cal)}",
          flush=True)
    books = all_books(c)
    assert len(books) == 54, len(books)
    rows, D = [], []
    for name, fam, b in books:
        rows.append(metrics(b, name, fam, cal))
        D.append(daily_series(b, cal).to_numpy())
        print(f"  {name}: {len(b)} trades", flush=True)
    tab = pd.DataFrame(rows)
    D = np.column_stack(D)
    rc = reality_check(D)
    tab["rw_adj_p"] = rc["rw_p"]
    tab["holm_reject"] = holm(tab["p_boot"].to_numpy(float))
    tab["candidate_edge"] = (tab["roc_ci_lo"] > 0) & (tab["rw_adj_p"] < 0.05)
    srs = [s for s in tab["cal_sharpe_daily"] if s == s]
    bi = int(tab["cal_sharpe_daily"].fillna(-np.inf).idxmax())
    r_best = D[:, bi]
    dsr54 = deflated(r_best, srs, 54) if r_best.std() > 0 else float("nan")
    dsr131 = deflated(r_best, srs, N_PRIOR_VARIANTS + 54) if r_best.std() > 0 else float("nan")
    bench_all = metrics(ev, "benchmark: all candidates", "bench", cal)
    isb = in_sample_best(ev)
    OUT.mkdir(parents=True, exist_ok=True)
    tab = tab.sort_values("roc", ascending=False, na_position="last")
    tab.to_csv(OUT / "trials.csv", index=False)
    summ = {"label": LABEL, "trials": 54, "rc_p_best": rc["rc_p"], "spa_p": rc["spa_p"],
            "rc_best_trial": rows[rc["best"]]["trial"], "best_by_sharpe": rows[bi]["trial"],
            "dsr_best_54": dsr54, f"dsr_best_{N_PRIOR_VARIANTS + 54}": dsr131,
            "holm_survivors": int(tab["holm_reject"].sum()), "candidate_edges": int(tab["candidate_edge"].sum()),
            **{f"insample_{k}": v for k, v in isb.items()}}
    pd.Series(summ).to_csv(OUT / "summary.csv", header=["value"])
    pd.DataFrame([bench_all]).to_csv(OUT / "benchmark.csv", index=False)
    pd.concat([b.assign(trial=n) for n, _, b in books]).to_csv(OUT / "trades.csv", index=False)  # gitignored
    pd.set_option("display.width", 250, "display.max_columns", 30)
    cols = ["trial", "trades", "roc", "roc_ci_lo", "roc_ci_hi", "net_c_per_contract", "pnl_total", "sharpe_x365",
            "max_drawdown", "excl_top5_roc", "rw_adj_p", "holm_reject", "candidate_edge"]
    print(tab[cols].round(4).to_string(index=False))
    print(pd.Series(summ).to_string())
    print(pd.Series(bench_all)[["trades", "roc", "roc_ci_lo", "roc_ci_hi", "net_c_per_contract"]].to_string())


if __name__ == "__main__":
    main()
