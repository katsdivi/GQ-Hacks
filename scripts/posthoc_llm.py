"""Post-hoc LLM (MLX LoRA) mispricing classifier on training snapshots.

post-hoc, exploratory; small LLM fine-tuned with LoRA on training snapshots; walk-forward on training only; holdout
not run. Rules: results/posthoc_llm/SPEC.md (b606242, committed before any training on real data).

Usage (cwd = repo root, venv .venv-mlx, PYTHONPATH=.:scripts):
  python scripts/posthoc_llm.py prep            fold jsonl files under data/llm_cache/fold_k/
  python scripts/posthoc_llm.py train K         LoRA fit for fold K (1 to 4)
  python scripts/posthoc_llm.py infer K         class probabilities on fold K test weeks
  python scripts/posthoc_llm.py evaluate        ridge baseline, trades, metrics, cumulative correction, RESULTS.md
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

LABEL = "post-hoc, exploratory; small LLM fine-tuned with LoRA on training snapshots; walk-forward on training only; holdout not run"
MODEL = "mlx-community/Llama-3.2-1B-Instruct-4bit"
CACHE = Path("data/llm_cache")
OUT = Path("results/posthoc_llm")
SEED = 20261004
FOLDS = {1: (range(0, 6), range(6, 10)), 2: (range(0, 10), range(10, 15)),
         3: (range(0, 15), range(15, 19)), 4: (range(0, 19), range(19, 25))}
CLASSES = ["under", "fair", "over"]
MAX_TRAIN = 3000
N_VALID = 200
QS = [0.5, 0.7]
# Columns allowed into a prompt. Anything else (pay, r, y, c, week, game_id, team, event, t_ns) never enters.
PROMPT_COLS = ["nfl", "preseason", "pregame", "mins_from_ko", "p", "q", "s", "dp1", "dp5", "dp15", "n5", "n15",
               "imb5", "age", "pm_gap", "pm_ok", "score_diff", "period", "sec_left", "own_poss", "wp", "wp_gap",
               "espn_ok", "nv_gap", "nv_ok"]
INSTRUCTION = "Kalshi football team price snapshot. Is this team's price under, fair or over vs cost? Answer one word."


def cents(x: float) -> str:
    return str(int(round(float(x) * 100)))


def make_prompt(row: dict) -> str:
    """Compact integer-cent key=value line from PROMPT_COLS only."""
    g = {k: row[k] for k in PROMPT_COLS}
    f = [f"lg={'NFL' if g['nfl'] else 'CFB'}", f"pre={int(g['preseason'])}", f"pregame={int(g['pregame'])}",
         f"min={int(round(g['mins_from_ko']))}", f"p={cents(g['p'])}", f"q={cents(g['q'])}", f"s={cents(g['s'])}",
         f"dp1={cents(g['dp1'])}", f"dp5={cents(g['dp5'])}", f"dp15={cents(g['dp15'])}",
         f"n5={int(g['n5'])}", f"n15={int(g['n15'])}", f"imb5={int(round(g['imb5'] * 100))}",
         f"age={int(round(np.expm1(g['age'])))}",
         f"pm={cents(g['pm_gap']) if g['pm_ok'] else 'na'}"]
    if g["espn_ok"]:
        f += [f"sd={int(g['score_diff'])}", f"per={int(g['period'])}", f"left={int(round(g['sec_left'] / 60))}",
              f"poss={int(g['own_poss'])}", f"wp={int(round(g['wp'] * 100))}", f"wpgap={cents(g['wp_gap'])}"]
    else:
        f += ["espn=na"]
    f.append(f"nv={cents(g['nv_gap']) if g['nv_ok'] else 'na'}")
    return INSTRUCTION + "\n" + " ".join(f)


def label(r: float, c: float) -> str:
    return "under" if r > c else ("over" if r < -c else "fair")


def load_snapshots() -> pd.DataFrame:
    df = pd.read_parquet(CACHE / "snapshots.parquet")
    assert df["week"].max() <= 24
    return df


def fold_frames(df: pd.DataFrame, k: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    trw, tew = FOLDS[k]
    tr, te = df[df["week"].isin(list(trw))], df[df["week"].isin(list(tew))]
    assert tr["week"].max() < te["week"].min()
    return tr, te


def prep() -> None:
    df = load_snapshots()
    for k in FOLDS:
        tr, _ = fold_frames(df, k)
        last = tr["week"].max()
        val = tr[tr["week"] == last].sample(min(N_VALID, (tr["week"] == last).sum()), random_state=SEED)
        pool = tr.drop(val.index)
        sub = pool.sample(min(MAX_TRAIN, len(pool)), random_state=SEED)
        d = CACHE / f"fold_{k}"
        d.mkdir(parents=True, exist_ok=True)
        for name, part in (("train", sub), ("valid", val)):
            with open(d / f"{name}.jsonl", "w") as fh:
                for r in part.to_dict("records"):
                    fh.write(json.dumps({"prompt": make_prompt(r), "completion": label(r["r"], r["c"])}) + "\n")
        cnt = sub.apply(lambda r: label(r["r"], r["c"]), axis=1).value_counts().to_dict()
        print(f"fold {k}: train {len(sub)} rows (weeks {min(FOLDS[k][0])}-{max(FOLDS[k][0])}), valid {len(val)} "
              f"(week {last}), classes {cnt}", flush=True)


def train(k: int) -> None:
    d = CACHE / f"fold_{k}"
    n = sum(1 for _ in open(d / "train.jsonl"))
    # SPEC: cut below ~1 epoch only to keep a fold near 15 min. Fold 1 ran 375 iters at ~4 s/iter under load
    # (about 25 min), so folds 2 to 4 are capped at 225 iters; counts are reported.
    iters = min(375 if k == 1 else 225, n // 8)
    cfg = d / "lora.yaml"
    cfg.write_text(f"""model: {MODEL}
train: true
data: {d}
fine_tune_type: lora
mask_prompt: true
num_layers: 8
batch_size: 8
iters: {iters}
learning_rate: 1.0e-4
steps_per_report: 25
steps_per_eval: {iters}
val_batches: 5
max_seq_length: 512
seed: {SEED}
adapter_path: {OUT / 'adapters' / f'fold_{k}'}
lora_parameters:
  rank: 8
  dropout: 0.05
  scale: 20.0
""")
    t0 = time.time()
    subprocess.run(["nice", "-n", "19", sys.executable, "-m", "mlx_lm", "lora", "-c", str(cfg)], check=True)
    print(f"fold {k}: trained {iters} iters in {time.time() - t0:.0f} s", flush=True)
    (d / "train_time.json").write_text(json.dumps({"iters": iters, "seconds": time.time() - t0}))


def class_token_ids(tok) -> list[int]:
    ids = []
    for c in CLASSES:
        e = tok.encode(c, add_special_tokens=False)
        assert len(e) == 1, (c, e)
        ids.append(e[0])
    return ids


def chat_prompt_ids(tok, text: str) -> list[int]:
    return tok.apply_chat_template([{"role": "user", "content": text}], add_generation_prompt=True, tokenize=True)


def class_probs(model, tok, texts: list[str], ids: list[int], batch: int = 32) -> np.ndarray:
    """Softmax over the three class tokens at the answer position; right-padded batches, read each row's last real
    position (causal attention, so padding after it does not change it)."""
    import mlx.core as mx
    out = np.zeros((len(texts), 3))
    seqs = [chat_prompt_ids(tok, t) for t in texts]
    pad = tok.pad_token_id if tok.pad_token_id is not None else 0
    for i in range(0, len(seqs), batch):
        chunk = seqs[i:i + batch]
        L = max(len(s) for s in chunk)
        arr = np.full((len(chunk), L), pad, dtype=np.int32)
        for j, s in enumerate(chunk):
            arr[j, :len(s)] = s
        logits = model(mx.array(arr))
        last = mx.array(np.array([len(s) - 1 for s in chunk]))
        sel = logits[mx.arange(len(chunk)), last][:, ids]
        p = mx.softmax(sel.astype(mx.float32), axis=-1)
        out[i:i + len(chunk)] = np.array(p)
    return out


def infer(k: int) -> None:
    from mlx_lm import load
    df = load_snapshots()
    _, te = fold_frames(df, k)
    model, tok = load(MODEL, adapter_path=str(OUT / "adapters" / f"fold_{k}"))
    ids = class_token_ids(tok)
    t0 = time.time()
    texts = [make_prompt(r) for r in te.to_dict("records")]
    pr = class_probs(model, tok, texts, ids)
    e = te[["game_id", "team", "t_ns", "week"]].copy()
    e[["p_under", "p_fair", "p_over"]] = pr
    e.to_parquet(OUT / f"pred_fold{k}.parquet")
    print(f"fold {k}: inferred {len(te)} rows in {time.time() - t0:.0f} s", flush=True)
    (CACHE / f"fold_{k}" / "infer_time.json").write_text(json.dumps({"rows": len(te), "seconds": time.time() - t0}))


# ---------------- evaluation ----------------

RIDGE_FEATS = ["p", "dp1", "dp5", "dp15", "n5", "n15", "v5", "v15", "imb5", "age", "q", "s",
               "pm_gap", "pm_age", "pm_ok", "score_diff", "period", "sec_left", "own_poss", "wp", "wp_gap", "espn_ok",
               "nv_gap", "nv_ok", "nfl", "preseason", "pregame", "mins_from_ko", "weekday", "ko_hour",
               "x_p2", "x_p_sd", "x_p_sec", "x_p_min", "x_wpgap", "x_pmgap", "x_s1"]   # posthoc-regress FEATS (a7cb8fb)
EXT = {"costside": ("../wt-costside/results/posthoc_costside/trials_log.csv",
                    "../wt-costside/results/posthoc_costside/daily_pnl.csv"),
       "search": ("../wt-search/results/posthoc_search/trials.csv", "../wt-search/results/posthoc_search/trades.csv"),
       "maker": ("../wt-costside-maker/results/posthoc_costside_maker/trials_log.csv",
                 "../wt-costside-maker/results/posthoc_costside_maker/daily_pnl.csv"),
       "patterns": ("../wt-costside-patterns/results/posthoc_costside_patterns/trials_log.csv",
                    "../wt-costside-patterns/results/posthoc_costside_patterns/daily_pnl.csv"),
       "unsup": ("../wt-unsup/results/posthoc_unsup/trials_log.csv", "../wt-unsup/results/posthoc_unsup/daily_pnl.csv"),
       "regress": ("../wt-regress/results/posthoc_regress/trials_log.csv",
                   "../wt-regress/results/posthoc_regress/daily_pnl.csv")}


def ridge_pred(tr: pd.DataFrame, te: pd.DataFrame, alpha: float = 10.0) -> np.ndarray:
    Xtr, Xte = tr[RIDGE_FEATS].to_numpy(float), te[RIDGE_FEATS].to_numpy(float)
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    Z, Zt = (Xtr - mu) / sd, (Xte - mu) / sd
    y = tr["r"].to_numpy(float)
    w = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    return Zt @ w + y.mean()


def taker_threshold(p: float) -> float:
    import regress_common as C
    return 0.01 + C.fee_taker(min(round(p + 0.01, 4), 0.99)) / 10


def external() -> tuple[dict, dict]:
    """Other branches' trials, read-only (posthoc-regress a7cb8fb external(), plus the regress branch)."""
    ser, info = {}, {}
    for name, (tl, dp) in EXT.items():
        try:
            t = pd.read_csv(tl)
        except FileNotFoundError:
            info[name] = {"trials": 0, "status": "not found"}
            continue
        ids = t["trial"] if "trial" in t else (t["trial_id"] if "trial_id" in t else t.iloc[:, 0])
        try:
            d = pd.read_csv(dp)
            if name == "search":
                d = d.rename(columns={"trial": "trial_id", "date": "et_date"})
            daily = {k: v.groupby("et_date")["pnl"].sum() for k, v in d.groupby("trial_id")}
            status = "daily P&L used"
        except (FileNotFoundError, KeyError):
            daily, status = {}, "trial count only"
        if name == "costside":   # its trials_log lists only its own trials; its daily_pnl has every trial it used
            ids = pd.Series(sorted(set(ids) | set(daily)))
        for i in ids:
            ser[f"{name}:{i}"] = daily.get(i, pd.Series(dtype=float))
        info[name] = {"trials": int(len(ids)), "status": status, "with_daily": int(sum(1 for i in ids if i in daily))}
    return ser, info


def evaluate() -> None:
    import regress_common as C
    df = load_snapshots()
    preds, rid = [], []
    for k in FOLDS:
        pf = OUT / f"pred_fold{k}.parquet"
        if not pf.exists():
            print(f"fold {k}: no predictions, skipped", flush=True)
            continue
        preds.append(pd.read_parquet(pf))
        tr, te = fold_frames(df, k)
        e = te[["game_id", "team", "t_ns", "week"]].copy()
        e["ridge"] = ridge_pred(tr, te)
        freq = tr.apply(lambda r: label(r["r"], r["c"]), axis=1).value_counts(normalize=True)
        e[["b_under", "b_fair", "b_over"]] = [freq.get(c, 0.0) for c in CLASSES]
        rid.append(e)
    pred = pd.concat(preds, ignore_index=True).merge(pd.concat(rid, ignore_index=True), on=["game_id", "team", "t_ns", "week"])
    d = df.merge(pred, on=["game_id", "team", "t_ns", "week"])
    d["cls"] = [label(a, b) for a, b in zip(d["r"], d["c"])]
    Y = np.column_stack([(d["cls"] == c).to_numpy(float) for c in CLASSES])
    P = d[["p_under", "p_fair", "p_over"]].to_numpy(float)
    B = d[["b_under", "b_fair", "b_over"]].to_numpy(float)
    brier_llm, brier_base = float(np.mean(np.sum((P - Y) ** 2, 1))), float(np.mean(np.sum((B - Y) ** 2, 1)))
    rr = d["r"].to_numpy(float)
    diag = {"rows": len(d), "accuracy_llm": float((np.array(CLASSES)[P.argmax(1)] == d["cls"]).mean()),
            "accuracy_majority": float((np.array(CLASSES)[B.argmax(1)] == d["cls"]).mean()),
            "brier_llm": brier_llm, "brier_class_freq": brier_base, "brier_skill": 1 - brier_llm / brier_base,
            "corr_llm_score_vs_r": float(np.corrcoef(P[:, 0] - P[:, 2], rr)[0, 1]),
            "ridge_oos_r2_vs_zero": float(1 - np.sum((rr - d["ridge"]) ** 2) / np.sum(rr ** 2)),
            "ridge_corr_vs_r": float(np.corrcoef(d["ridge"], rr)[0, 1]),
            "class_share_test": d["cls"].value_counts(normalize=True).to_dict(),
            "mean_p_under_by_class": d.groupby("cls")["p_under"].mean().to_dict()}
    print(json.dumps(diag, indent=1), flush=True)
    games = pd.read_csv(C.DATA / "raw" / "kalshi_only_games.csv")
    series = {}
    for r in games[games["game_id"].isin(set(d["game_id"]))].itertuples():
        t = pd.read_parquet(C.DATA / "raw" / "kalshi_only" / f"{r.game_id}.parquet", columns=["ts", "market_id", "kind", "price"])
        series[(r.game_id, r.home)] = C._own(t, f"{r.kalshi_event}-{r.home}", False)
        series[(r.game_id, r.away)] = C._own(t, f"{r.kalshi_event}-{r.away}", True)
    d = d.sort_values(["game_id", "t_ns"], kind="stable")
    rules = {"LLM1B.q50": lambda r: r.p_under > 0.5, "LLM1B.q70": lambda r: r.p_under > 0.7,
             "RIDGE.base": lambda r: r.ridge > taker_threshold(r.p), "BENCH.take_first": lambda r: True}
    books, rows = {}, []
    for name, rule in rules.items():
        tr_rows, done = [], set()
        for r in d.itertuples():
            if r.game_id in done or not rule(r):
                continue
            ts, px = series[(r.game_id, r.team)]
            f = C.taker_entry(ts, px, int(r.t_ns), win_s=300)
            if f is None:
                continue
            fee = C.fee_taker(f[1])
            bt = C.book_trade(f[1], fee, payout=r.pay)
            tr_rows.append({"game_id": r.game_id, "team": r.team, "t_ns": int(r.t_ns), "fill_ts": f[0], "entry": f[1],
                            "fee_entry": fee, "payout": r.pay, "pnl": bt["pnl"], "cap": bt["cap"],
                            "day": C.et_date(int(r.t_ns))})
            done.add(r.game_id)
        b = pd.DataFrame(tr_rows)
        books[name] = b
        if len(b):
            b.to_csv(OUT / f"trades_{name}.csv", index=False)
        rows.append({"trial": name, "is_trial": not name.startswith("BENCH"), **C.metrics(b), "label": LABEL})
    tl = pd.DataFrame(rows)
    own = {f"llm:{n}": b.groupby("day")["pnl"].sum() if len(b) else pd.Series(dtype=float)
           for n, b in books.items() if not n.startswith("BENCH")}
    ext, info = external()
    mt = C.multiple_testing({**ext, **own})
    tl["holm_p"] = tl["trial"].map(lambda n: mt["holm"].get(f"llm:{n}") if mt else None)
    tl["raw_p"] = tl["trial"].map(lambda n: mt["raw_p"].get(f"llm:{n}") if mt else None)
    rc_p = mt.get("rc_p", np.nan)
    tl["candidate_edge"] = tl["is_trial"] & (tl["roc_lo"] > 0) & (rc_p < 0.05) & (tl["trades"] >= 100) & (tl["excl5_roc"] > 0)
    tl.to_csv(OUT / "trials_log.csv", index=False)
    daily = pd.concat([s.rename("pnl").rename_axis("et_date").reset_index().assign(trial_id=k.split(":", 1)[1])
                       for k, s in own.items() if len(s)], ignore_index=True)
    daily[["trial_id", "et_date", "pnl"]].to_csv(OUT / "daily_pnl.csv", index=False)
    corr = {k: v for k, v in mt.items() if k not in ("holm", "raw_p")}
    corr.update(external=info, own_trials=len(own), cumulative_trials=len(ext) + len(own),
                holm_survivors_005=[k for k, v in mt.get("holm", {}).items() if v < 0.05],
                candidates=tl.loc[tl["candidate_edge"], "trial"].tolist())
    times = {k: {**json.loads((CACHE / f"fold_{k}" / "train_time.json").read_text()),
                 **{"infer_" + a: b for a, b in json.loads((CACHE / f"fold_{k}" / "infer_time.json").read_text()).items()}}
             for k in FOLDS if (CACHE / f"fold_{k}" / "infer_time.json").exists()}
    (OUT / "diagnostics.json").write_text(json.dumps({"classification": diag, "correction": corr, "fold_times": times},
                                                     indent=2, default=float))
    print(tl.to_string(index=False), flush=True)
    print(json.dumps(corr, indent=1, default=float), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prep":
        prep()
    elif cmd == "train":
        train(int(sys.argv[2]))
    elif cmd == "infer":
        infer(int(sys.argv[2]))
    elif cmd == "evaluate":
        evaluate()
