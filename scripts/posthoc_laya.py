"""Post-hoc Laya: frozen Laya encoder (MLX) plus ridge head over the posthoc-meta candidate pool.

post-hoc, exploratory, generative-model encoder; not part of the submitted strategies.
Spec: results/posthoc_laya/SPEC.md. Run (cwd = repo root, .venv-laya, nice -n 19):
  python scripts/posthoc_laya.py embed     # encode texts -> data/laya_cache/emb.npy
  python scripts/posthoc_laya.py evaluate  # walk-forward heads, results to results/posthoc_laya/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CAND = Path("../wt-meta/results/posthoc_meta/candidates.csv")
CAND_SHA = "a9ff5574a0457f79a557ea834a51e3821f991ba78e247dfa613216a64d108c33"
META_RESULTS = Path("../wt-meta/results/posthoc_meta/results.csv")
MODEL = Path("models/laya-mlx")
CACHE = Path("data/laya_cache")
OUT = Path("results/posthoc_laya")
LABEL = "post-hoc, exploratory, generative-model encoder; not part of the submitted strategies"
SEED, N_BOOT = 20261004, 2000
ALPHAS = {"H1": 10.0, "H2": 1000.0}
MIN_HIST_WEEKS = 6
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
TEXT_COLS = ["strategy", "leg", "side", "league", "preseason", "min_from_ko", "dow", "signal",
             "agree_same", "agree_opp", "trail_wr"]   # only pre-t columns (SPEC table)


def to_text(r) -> str:
    return (f"strategy {r['strategy']} {r['leg']}; side {r['side']}; league {r['league']}; "
            f"preseason {'yes' if int(r['preseason']) else 'no'}; minutes from kickoff {float(r['min_from_ko']):.0f}; "
            f"weekday {DOW[int(r['dow']) % 7]}; signal {float(r['signal']):.2f}; "
            f"earlier agreeing candidates {int(r['agree_same'])}; earlier opposing candidates {int(r['agree_opp'])}; "
            f"strategy trailing win rate {float(r['trail_wr']):.2f}")


def texts(c: pd.DataFrame) -> list[str]:
    return [to_text(r) for r in c[TEXT_COLS].to_dict("records")]


def target_cents(c: pd.DataFrame) -> np.ndarray:
    return c["pnl"].to_numpy(float) / 10 * 100


def eval_weeks(c: pd.DataFrame) -> list[str]:
    wk = sorted(c["week"].unique())
    return wk[MIN_HIST_WEEKS:]


def ridge_fit_predict(Xtr, ytr, Xte, alpha):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-8
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    ym = ytr.mean()
    w = np.linalg.solve(A.T @ A + alpha * np.eye(A.shape[1]), A.T @ (ytr - ym))
    return B @ w + ym


def walk_forward(c: pd.DataFrame, X: np.ndarray, alpha: float) -> np.ndarray:
    y = target_cents(c)
    pred = np.full(len(c), np.nan)
    weeks = c["week"].to_numpy()
    for w in eval_weeks(c):
        tr, te = weeks < w, weeks == w
        assert not np.any(tr & te)
        if te.any():
            pred[te] = ridge_fit_predict(X[tr], y[tr], X[te], alpha)
    return pred


def boot_ci(df: pd.DataFrame) -> tuple[float, float]:
    g = df.groupby("game_id")["roc"].agg(["sum", "count"])
    if len(g) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(g), size=(N_BOOT, len(g)))
    s, n = g["sum"].to_numpy()[idx].sum(1), g["count"].to_numpy()[idx].sum(1)
    m = s / n
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def auc(score, y) -> float:
    from scipy.stats import rankdata
    r = rankdata(score)
    n1, n0 = int((y == 1).sum()), int((y == 0).sum())
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def book(c: pd.DataFrame, take: np.ndarray, name: str, pred=None) -> dict:
    e = c[take]
    out = {"book": name, "label": LABEL, "trades": int(len(e)), "games": int(e["game_id"].nunique())}
    if len(e):
        lo, hi = boot_ci(e)
        top5 = e.groupby("game_id")["pnl"].sum().nlargest(5).index
        k = e[~e["game_id"].isin(top5)]
        daily = e.groupby("date")["pnl"].sum()
        out.update(roc_mean=float(e["roc"].mean()), roc_ci_lo=lo, roc_ci_hi=hi,
                   c_per_contract=float(e["pnl"].sum() / (10 * len(e)) * 100), pnl_total=float(e["pnl"].sum()),
                   excl_top5_roc=float(k["roc"].mean()) if len(k) else float("nan"),
                   sharpe_daily=float(daily.mean() / daily.std()) if len(daily) > 1 and daily.std() > 0 else float("nan"))
    if pred is not None:
        m = ~np.isnan(pred)
        y = target_cents(c)[m]
        out.update(corr_pred_net=float(np.corrcoef(pred[m], y)[0, 1]),
                   auc_ref=auc(pred[m], c["y"].to_numpy()[m]))
    return out


def load_candidates() -> pd.DataFrame:
    import hashlib
    assert hashlib.sha256(CAND.read_bytes()).hexdigest() == CAND_SHA, "candidate pool changed"
    c = pd.read_csv(CAND)
    assert (c["kickoff_ns"] < pd.Timestamp("2026-08-01", tz="UTC").value).all(), "training only"
    return c.reset_index(drop=True)


def cmd_embed():
    import laya_mlx as laya
    c = load_candidates()
    agent = laya.load(str(MODEL), dtype="float16")
    emb = laya.embed_fn_from_agent(agent, max_length=128, batch_size=64)
    T = texts(c)
    uniq = sorted(set(T))
    E = np.concatenate([np.asarray(emb(uniq[i:i + 256])) for i in range(0, len(uniq), 256)])
    pos = {t: i for i, t in enumerate(uniq)}
    X = E[[pos[t] for t in T]].astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(CACHE / "emb.npy", X)
    print(f"embedded {len(uniq)} unique texts for {len(T)} candidates, dim {X.shape[1]}", flush=True)


def cmd_evaluate():
    c = load_candidates()
    X = np.load(CACHE / "emb.npy")
    ev = c["week"].isin(eval_weeks(c)).to_numpy()
    rows = [book(c, np.zeros(len(c), bool), "no trade"), book(c, ev, "take all")]
    preds = {}
    for h, a in ALPHAS.items():
        p = walk_forward(c, X, a)
        preds[h] = p
        rows.append(book(c, ev & (np.nan_to_num(p, nan=-1e9) > 0), f"{h} ridge alpha {a:g}", p))
    res = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    res.to_csv(OUT / "results.csv", index=False)
    meta = pd.read_csv(META_RESULTS) if META_RESULTS.exists() else None
    json.dump({"eval_weeks": eval_weeks(c), "n_eval": int(ev.sum())}, open(OUT / "run_meta.json", "w"), indent=1)
    pd.set_option("display.width", 250)
    print(res.round(4).to_string(index=False))
    if meta is not None:
        print(meta.round(4).to_string(index=False))


if __name__ == "__main__":
    {"embed": cmd_embed, "evaluate": cmd_evaluate}[sys.argv[1]]()
