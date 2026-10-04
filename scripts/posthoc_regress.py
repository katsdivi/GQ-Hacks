"""Post-hoc supervised residual regression: where is the Kalshi price wrong, using every data source combined.

post-hoc, exploratory; walk-forward on training only; holdout not run. Rules: results/posthoc_regress/SPEC.md
(4b318d6, committed before any real data).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_regress.py            build snapshots (cached in data/regress_cache/), fit, trade, report
"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize

import regress_common as C
import strategy_a as A
import ingest.kalshi_only_train as T

LABEL = "post-hoc, exploratory; supervised residual model over all data sources; walk-forward on training only; holdout not run"
NS = C.NS
ESPN = Path("../wt-idea6/data/espn_raw")
NV = Path("../wt-idea13/results/posthoc_idea13/training_games.csv")
SCORING = {"touchdown", "field-goal", "safety"}
SNAP_MIN = [-30, -5] + list(range(20, 181, 10))
STALE_S = 30 * 60
MODELS = ["RIDGE1", "RIDGE10", "LOGIT01", "LOGIT1", "BOOST", "ISO"]
EXECS = ["TAKER", "MAKER"]
MARGINS = [0.0, 0.01]
BOOKS = ["primary", "all"]
FEATS = ["p", "dp1", "dp5", "dp15", "n5", "n15", "v5", "v15", "imb5", "age", "q", "s",
         "pm_gap", "pm_age", "pm_ok", "score_diff", "period", "sec_left", "own_poss", "wp", "wp_gap", "espn_ok",
         "nv_gap", "nv_ok", "nfl", "preseason", "pregame", "mins_from_ko", "weekday", "ko_hour",
         "x_p2", "x_p_sd", "x_p_sec", "x_p_min", "x_wpgap", "x_pmgap", "x_s1"]


# ---------------- ESPN ----------------

def plays_with_poss(summary: dict) -> list[dict]:
    out = []
    for dr in (summary.get("drives") or {}).get("previous", []):
        tid = str((dr.get("team") or {}).get("id", ""))
        for p in dr.get("plays", []):
            out.append({**p, "_poss": tid})
    return out


def espn_defect(plays: list[dict], ko: int) -> bool:
    """Idea 10 defect rule (posthoc-idea10 92ee688): a scoring event outside [ko, ko + 6 h] or out of order."""
    wcs = [pd.Timestamp(x["wallclock"]).value if x.get("wallclock") else None for x in plays]
    prev = (0, 0)
    for i, x in enumerate(plays):
        cur = (x.get("homeScore", prev[0]), x.get("awayScore", prev[1]))
        st = (x.get("scoringType") or {}).get("name")
        if x.get("scoringPlay") and st in SCORING and wcs[i] is not None and (cur[0] > prev[0]) != (cur[1] > prev[1]):
            w = wcs[i]
            before = next((wcs[j] for j in range(i - 1, -1, -1) if wcs[j] is not None), None)
            after = next((wcs[j] for j in range(i + 1, len(plays)) if wcs[j] is not None), None)
            if not (ko <= w <= ko + 6 * 3600 * NS) or (before is not None and w < before) or \
                    (after is not None and w > after):
                return True
        prev = cur
    return False


def orient(comp: dict, k_home: tuple[str, str], k_away: tuple[str, str]) -> str | None:
    """posthoc-idea6 scripts/posthoc_idea6.py orient() at 0f57732, verbatim logic."""
    t = {c["homeAway"]: c["team"] for c in comp["competitors"]}
    same = T._name_score(*k_home, t["home"]) + T._name_score(*k_away, t["away"])
    swap = T._name_score(*k_home, t["away"]) + T._name_score(*k_away, t["home"])
    best = max(same, swap)
    if best < 1.6 or same == swap:
        return None
    return "same" if same > swap else "swapped"


def clock_s(txt) -> float:
    try:
        m, s = str(txt).split(":")
        return int(m) * 60 + float(s)
    except Exception:
        return 0.0


def espn_state(summary: dict, ko: int, orientation: str | None) -> dict | None:
    """Per-play arrays (wallclock sorted as recorded) with ESPN-home perspective; None if unusable."""
    if summary is None or orientation is None:
        return None
    plays = plays_with_poss(summary)
    if not plays or espn_defect(plays, ko):
        return None
    comp = summary["header"]["competitions"][0]
    home_id = next(str(c["id"]) for c in comp["competitors"] if c["homeAway"] == "home")
    rows = []
    prev = (0, 0)
    for p in plays:
        if not p.get("wallclock"):
            continue
        cur = (p.get("homeScore", prev[0]), p.get("awayScore", prev[1]))
        prev = cur
        per = int((p.get("period") or {}).get("number", 1))
        left = max(0, 4 - per) * 900 + clock_s((p.get("clock") or {}).get("displayValue")) if per <= 4 else 0.0
        rows.append((pd.Timestamp(p["wallclock"]).value, cur[0] - cur[1], per, left, 1 if p["_poss"] == home_id else 0,
                     str(p.get("id"))))
    if not rows:
        return None
    df = pd.DataFrame(rows, columns=["wc", "hdiff", "period", "left", "hposs", "pid"])
    wp = {}
    for w in summary.get("winprobability") or []:
        if w.get("homeWinPercentage") is not None:
            wp[str(w.get("playId"))] = float(w["homeWinPercentage"])
    df["hwp"] = df["pid"].map(wp)
    df = df.sort_values("wc", kind="stable").reset_index(drop=True)   # as-of lookups need time order
    return {"df": df, "flip": orientation == "swapped"}


def espn_at(st: dict | None, t: int, kalshi_home_side: bool) -> dict:
    """Latest ESPN state with wallclock <= t, for the Kalshi team (home side if kalshi_home_side)."""
    z = {"score_diff": 0.0, "period": 0.0, "sec_left": 0.0, "own_poss": 0.0, "wp": 0.0, "espn_ok": 0.0}
    if st is None:
        return z
    df = st["df"]
    i = np.searchsorted(df["wc"].to_numpy(), t, side="right") - 1
    if i < 0:
        return {**z, "sec_left": 3600.0}
    r = df.iloc[i]
    espn_home = kalshi_home_side != st["flip"]   # is this Kalshi team ESPN's home team?
    sgn = 1.0 if espn_home else -1.0
    w = df["hwp"].iloc[: i + 1].dropna()
    hwp = float(w.iloc[-1]) if len(w) else np.nan
    return {"score_diff": sgn * float(r.hdiff), "period": float(r.period), "sec_left": float(r.left),
            "own_poss": float(r.hposs if espn_home else 1 - r.hposs),
            "wp": (hwp if espn_home else 1 - hwp) if hwp == hwp else 0.0, "espn_ok": 1.0 if hwp == hwp else 0.0}


# ---------------- snapshots ----------------

def own_series(t: pd.DataFrame, ticker: str, away: bool):
    x = t[(t["market_id"] == ticker) & (t["kind"] == "trade")].sort_values("ts", kind="stable")
    px = x["price"].to_numpy(float)
    side = x["side"].astype(str).to_numpy()
    yes = (side == "sell") if away else (side == "buy")   # taker YES on this team's own market
    return (x["ts"].to_numpy(np.int64), np.round(1 - px if away else px, 4), x["size"].to_numpy(float), yes)


def asof(ts, px, t):
    i = np.searchsorted(ts, t, side="right") - 1
    return float(px[i]) if i >= 0 else np.nan


def team_feats(s, t: int) -> dict | None:
    ts, px, sz, yes = s
    i = np.searchsorted(ts, t, side="right") - 1
    if i < 0 or t - ts[i] > STALE_S * NS:
        return None
    p = float(px[i])
    out = {"p": p, "age": np.log1p((t - ts[i]) / NS)}
    for m in (1, 5, 15):
        q = asof(ts, px, t - m * 60 * NS)
        out[f"dp{m}"] = p - q if q == q else 0.0
    for m in (5, 15):
        lo = np.searchsorted(ts, t - m * 60 * NS, side="right")
        out[f"n{m}"] = float(i + 1 - lo)
        out[f"v{m}"] = float(np.log1p(sz[lo:i + 1].sum()))
    lo = np.searchsorted(ts, t - 5 * 60 * NS, side="right")
    tot = sz[lo:i + 1].sum()
    out["imb5"] = float((sz[lo:i + 1][yes[lo:i + 1]].sum() - sz[lo:i + 1][~yes[lo:i + 1]].sum()) / tot) if tot > 0 else 0.0
    return out


def build_snapshots() -> pd.DataFrame:
    f = C.CACHE / "snapshots.parquet"
    if f.exists():
        return pd.read_parquet(f)
    C.CACHE.mkdir(parents=True, exist_ok=True)
    sett = C._settle_map()
    games = pd.read_csv(C.DATA / "raw" / "kalshi_only_games.csv")
    b = pd.read_csv(C.OUTB / "b_games_espn.csv")
    bset = set(b["game_id"]) - C.EXCLUDED_A1
    ids = pd.read_csv(ESPN / "ids_training.csv", dtype={"espn_id": str}).set_index("game_id")
    nv = pd.read_csv(NV).set_index("game_id")["p_home"] if NV.exists() else pd.Series(dtype=float)
    agame = {g.game_id: g for g in A.load_games(C.DATA / "raw" / "kalshi_only_games.csv",
                                                 C.DATA / "raw" / "kalshi_market_meta.csv",
                                                 ticks_dir=C.DATA / "raw" / "kalshi_only")}
    wk, _ = C.week_index([{"game_id": r.game_id, "kickoff_ns": pd.Timestamp(r.kickoff_utc_espn).value}
                          for r in games.itertuples()])
    rows, espn_used = [], 0
    for n, r in enumerate(games.itertuples()):
        ko = pd.Timestamp(r.kickoff_utc_espn).value
        assert ko < C.SEAL.value, "training only"
        p = C.DATA / "raw" / "kalshi_only" / f"{r.game_id}.parquet"
        if not p.exists():
            continue
        t = pd.read_parquet(p, columns=["ts", "market_id", "kind", "price", "size", "side"])
        ser = {r.home: own_series(t, f"{r.kalshi_event}-{r.home}", False),
               r.away: own_series(t, f"{r.kalshi_event}-{r.away}", True)}
        pm = None
        if r.game_id in bset:
            pp = C.DATA / "ticks" / f"{r.game_id}_polymarket.parquet"
            if pp.exists():
                x = pd.read_parquet(pp, columns=["ts", "kind", "price"])
                x = x[x["kind"] == "trade"].sort_values("ts", kind="stable")
                pm = (x["ts"].to_numpy(np.int64), x["price"].to_numpy(float))
        st = None
        if r.game_id in ids.index and isinstance(ids.loc[r.game_id, "espn_id"], str):
            sp = ESPN / f"{r.league.lower()}_{int(float(ids.loc[r.game_id, 'espn_id']))}.json"
            if sp.exists():
                summ = json.loads(sp.read_text())
                comp = summ["header"]["competitions"][0]
                o = orient(comp, (ids.loc[r.game_id, "k_home_name"], r.home), (ids.loc[r.game_id, "k_away_name"], r.away))
                st = espn_state(summ, ko, o)
        espn_used += st is not None
        g = agame.get(r.game_id)
        pre = bool(A.is_preseason(g)) if g is not None else False
        kod = pd.Timestamp(ko, unit="ns", tz="UTC").tz_convert("America/New_York")
        nvh = nv.get(r.game_id, np.nan)
        for mins in SNAP_MIN:
            tt = ko + mins * 60 * NS
            for team, other, is_home in ((r.home, r.away, True), (r.away, r.home, False)):
                pay = sett.get((r.game_id, "home" if is_home else "away"), np.nan)
                if pay != pay:
                    continue
                fe = team_feats(ser[team], tt)
                if fe is None:
                    continue
                qo = asof(ser[other][0], ser[other][1], tt)
                if qo == qo and tt - ser[other][0][np.searchsorted(ser[other][0], tt, side="right") - 1] > STALE_S * NS:
                    qo = np.nan
                fe["q"] = qo if qo == qo else 1 - fe["p"]
                fe["s"] = fe["p"] + fe["q"]
                fe.update(pm_gap=0.0, pm_age=0.0, pm_ok=0.0)
                if pm is not None:
                    j = np.searchsorted(pm[0], tt, side="right") - 1
                    if j >= 0 and tt - pm[0][j] <= STALE_S * NS:
                        ph = float(pm[1][j])
                        fe.update(pm_gap=(ph if is_home else 1 - ph) - fe["p"], pm_age=np.log1p((tt - pm[0][j]) / NS),
                                  pm_ok=1.0)
                es = espn_at(st, tt, is_home) if mins > 0 else {"score_diff": 0.0, "period": 0.0, "sec_left": 3600.0,
                                                                "own_poss": 0.0, "wp": 0.0, "espn_ok": 0.0}
                fe.update(es)
                fe["wp_gap"] = fe["wp"] - fe["p"] if fe["espn_ok"] else 0.0
                okv = r.league == "NFL" and mins < 0 and nvh == nvh
                fe["nv_gap"] = ((nvh if is_home else 1 - nvh) - fe["p"]) if okv else 0.0
                fe["nv_ok"] = 1.0 if okv else 0.0
                fe.update(nfl=float(r.league == "NFL"), preseason=float(pre), pregame=float(mins < 0),
                          mins_from_ko=float(mins), weekday=float(kod.weekday()), ko_hour=float(kod.hour))
                fe.update(x_p2=fe["p"] ** 2, x_p_sd=fe["p"] * fe["score_diff"], x_p_sec=fe["p"] * fe["sec_left"] / 3600,
                          x_p_min=fe["p"] * mins / 60, x_wpgap=fe["wp_gap"] * fe["espn_ok"],
                          x_pmgap=fe["pm_gap"] * fe["pm_ok"], x_s1=fe["s"] - 1)
                rows.append({"game_id": r.game_id, "team": team, "is_home": is_home, "t_ns": tt, "mins": mins,
                             "week": wk[r.game_id], "pay": pay, "event": r.kalshi_event, **fe})
        if n % 200 == 0:
            print(f"  snapshots {n}/{len(games)}", flush=True)
    df = pd.DataFrame(rows)
    df["r"] = df["pay"] - df["p"]
    df["c"] = 0.01 + np.array([C.fee_taker(min(round(x + 0.01, 4), 0.99)) for x in df["p"]]) / 10
    df["y"] = (df["r"] > df["c"]).astype(float)
    df.attrs["espn_games"] = espn_used
    df.to_parquet(f)
    (C.CACHE / "espn_games.txt").write_text(str(espn_used))
    return df


# ---------------- models ----------------

def standardize(Xtr, Xte):
    mu, sd = Xtr.mean(0), Xtr.std(0)
    sd = np.where(sd > 0, sd, 1.0)
    return (Xtr - mu) / sd, (Xte - mu) / sd


def ridge(Xtr, ytr, Xte, alpha):
    Z, Zt = standardize(Xtr, Xte)
    ym = ytr.mean()
    w = np.linalg.solve(Z.T @ Z + alpha * np.eye(Z.shape[1]), Z.T @ (ytr - ym))
    return Zt @ w + ym


def logit(Xtr, ytr, Xte, Cc):
    Z, Zt = standardize(Xtr, Xte)
    Z1, Zt1 = np.column_stack([np.ones(len(Z)), Z]), np.column_stack([np.ones(len(Zt)), Zt])
    lam = 1.0 / Cc

    def f(w):
        z = Z1 @ w
        ll = np.sum(np.logaddexp(0, z) - ytr * z) / len(ytr)
        g = Z1.T @ (1 / (1 + np.exp(-z)) - ytr) / len(ytr)
        reg = 0.5 * lam * np.sum(w[1:] ** 2) / len(ytr)
        gr = np.concatenate([[0.0], lam * w[1:] / len(ytr)])
        return ll + reg, g + gr

    w = optimize.minimize(f, np.zeros(Z1.shape[1]), jac=True, method="L-BFGS-B").x
    return 1 / (1 + np.exp(-(Zt1 @ w)))


def boost(Xtr, ytr, Xte, rounds=100, lr=0.05, bins=16, min_leaf=50):
    """Gradient-boosted depth-2 regression trees on squared loss, histogram splits on past-only quantile bins."""
    edges = [np.unique(np.quantile(Xtr[:, j], np.linspace(0, 1, bins + 1)[1:-1])) for j in range(Xtr.shape[1])]
    Btr = np.column_stack([np.searchsorted(edges[j], Xtr[:, j], side="right") for j in range(Xtr.shape[1])])
    Bte = np.column_stack([np.searchsorted(edges[j], Xte[:, j], side="right") for j in range(Xte.shape[1])])
    base = ytr.mean()
    ftr, fte = np.full(len(ytr), base), np.full(len(Xte), base)

    def best_split(idx, res):
        best = (0.0, None, None)
        tot, n = res[idx].sum(), len(idx)
        for j in range(Btr.shape[1]):
            nb = len(edges[j]) + 1
            s = np.bincount(Btr[idx, j], weights=res[idx], minlength=nb)
            c = np.bincount(Btr[idx, j], minlength=nb)
            cs, cc = np.cumsum(s)[:-1], np.cumsum(c)[:-1]
            ok = (cc >= min_leaf) & (n - cc >= min_leaf)
            if not ok.any():
                continue
            gain = np.where(ok, cs ** 2 / np.maximum(cc, 1) + (tot - cs) ** 2 / np.maximum(n - cc, 1), -np.inf) - tot ** 2 / n
            k = int(np.argmax(gain))
            if gain[k] > best[0]:
                best = (float(gain[k]), j, k)
        return best

    allidx = np.arange(len(ytr))
    for _ in range(rounds):
        res = ytr - ftr
        g0, j0, k0 = best_split(allidx, res)
        if j0 is None:
            break
        L, R = allidx[Btr[:, j0] <= k0], allidx[Btr[:, j0] > k0]
        Lte, Rte = Bte[:, j0] <= k0, Bte[:, j0] > k0
        for side, side_te in ((L, Lte), (R, Rte)):
            g1, j1, k1 = best_split(side, res)
            if j1 is None:
                v = res[side].mean()
                ftr[side] += lr * v
                fte[side_te] += lr * v
                continue
            a, bb = side[Btr[side, j1] <= k1], side[Btr[side, j1] > k1]
            va, vb = res[a].mean(), res[bb].mean()
            ftr[a] += lr * va
            ftr[bb] += lr * vb
            fte[side_te & (Bte[:, j1] <= k1)] += lr * va
            fte[side_te & (Bte[:, j1] > k1)] += lr * vb
    return fte


def pav(x, y):
    """Isotonic (non-decreasing) fit of y on x; returns breakpoints and fitted values."""
    o = np.argsort(x, kind="stable")
    xs, ys = x[o], y[o].astype(float)
    vals, wts, xs_hi = [], [], []
    for xi, yi in zip(xs, ys):
        vals.append(yi); wts.append(1.0); xs_hi.append(xi)
        while len(vals) > 1 and vals[-2] > vals[-1]:
            w = wts[-2] + wts[-1]
            v = (vals[-2] * wts[-2] + vals[-1] * wts[-1]) / w
            vals[-2:], wts[-2:], xs_hi[-2:] = [v], [w], [xs_hi[-1]]
    return np.array(xs_hi), np.array(vals)


def iso_predict(xtr, ytr, xte):
    hi, v = pav(xtr, ytr)
    i = np.clip(np.searchsorted(hi, xte, side="left"), 0, len(v) - 1)
    return v[i]


def predict(model: str, tr: pd.DataFrame, te: pd.DataFrame, feats=FEATS) -> np.ndarray:
    """Predicted edge e for test rows, fit on train rows only."""
    Xtr, Xte = tr[feats].to_numpy(float), te[feats].to_numpy(float)
    if model.startswith("RIDGE"):
        return ridge(Xtr, tr["r"].to_numpy(float), Xte, 1.0 if model == "RIDGE1" else 10.0)
    if model.startswith("LOGIT"):
        return logit(Xtr, tr["y"].to_numpy(float), Xte, 0.1 if model == "LOGIT01" else 1.0) - te["p"].to_numpy(float)
    if model == "BOOST":
        return boost(Xtr, tr["r"].to_numpy(float), Xte)
    if model == "ISO":
        return iso_predict(tr["p"].to_numpy(float), tr["pay"].to_numpy(float), te["p"].to_numpy(float)) - te["p"].to_numpy(float)
    raise ValueError(model)


def walk_forward(df: pd.DataFrame, first_test: int) -> pd.DataFrame:
    out = []
    for w in sorted(df["week"].unique()):
        if w < first_test:
            continue
        tr, te = df[df["week"] < w], df[df["week"] == w]
        assert tr["week"].max() < w
        if len(tr) < 500 or te.empty:
            continue
        e = te[["game_id", "team", "t_ns", "week"]].copy()
        for m in MODELS:
            e[m] = predict(m, tr, te)
        out.append(e)
        print(f"  week {w}: train {len(tr)}, test {len(te)}", flush=True)
    return pd.concat(out, ignore_index=True)


# ---------------- trading ----------------

def threshold(execu: str, p: float, margin: float) -> float:
    if execu == "TAKER":
        return 0.01 + C.fee_taker(min(round(p + 0.01, 4), 0.99)) / 10 + margin
    return -0.01 + C.fee_maker175(max(round(p - 0.01, 4), 0.01)) / 10 + margin


def trade_books(df: pd.DataFrame, pred: pd.DataFrame, series: dict) -> dict:
    """{trial: trades DataFrame}. series[(game_id, team)] = (ts, px) own-market trades."""
    d = df.merge(pred, on=["game_id", "team", "t_ns", "week"])
    trials = {}
    for m in MODELS:
        for ex in EXECS:
            for mg in MARGINS:
                rows = []
                for r in d.itertuples():
                    e = getattr(r, m)
                    if not (e > threshold(ex, r.p, mg)):
                        continue
                    ts, px = series[(r.game_id, r.team)]
                    if ex == "TAKER":
                        f = C.taker_entry(ts, px, int(r.t_ns), win_s=300)
                        if f is None:
                            continue
                        fee, fee_alt = C.fee_taker(f[1]), C.fee_taker(f[1])
                    else:
                        f = C.maker_entry(ts, px, int(r.t_ns), round(r.p - 0.01, 4), 300)
                        if f is None:
                            continue
                        fee, fee_alt = C.fee_maker175(f[1]), C.fee_maker0(f[1])
                    bt, ba = C.book_trade(f[1], fee, payout=r.pay), C.book_trade(f[1], fee_alt, payout=r.pay)
                    rows.append({"game_id": r.game_id, "team": r.team, "t_ns": int(r.t_ns), "fill_ts": f[0],
                                 "entry": f[1], "fee_entry": fee, "payout": r.pay, "pnl": bt["pnl"], "cap": bt["cap"],
                                 "pnl_alt": ba["pnl"], "cap_alt": ba["cap"], "e": e, "day": C.et_date(int(r.t_ns))})
                allb = pd.DataFrame(rows)
                for book in BOOKS:
                    name = f"{m}.{ex}.m{int(mg * 100)}.{book}"
                    if allb.empty:
                        trials[name] = allb
                        continue
                    if book == "primary":
                        b = allb.sort_values(["game_id", "t_ns", "e"], ascending=[True, True, False])
                        b = b.drop_duplicates("game_id", keep="first")
                    else:
                        b = allb
                    trials[name] = b.reset_index(drop=True)
    return trials


# ---------------- diagnostics ----------------

def oos_fit(df: pd.DataFrame, pred: pd.DataFrame) -> pd.DataFrame:
    d = df.merge(pred, on=["game_id", "team", "t_ns", "week"])
    out = []
    for m in MODELS:
        for ph, sub in (("all", d), ("pregame", d[d["mins"] < 0]), ("ingame", d[d["mins"] > 0])):
            rr = sub["r"].to_numpy(float)
            pr = sub[m].to_numpy(float) if not m.startswith("LOGIT") else sub[m].to_numpy(float)
            sse0, sse = np.sum(rr ** 2), np.sum((rr - pr) ** 2)
            out.append({"model": m, "phase": ph, "rows": len(sub), "oos_r2_vs_price": 1 - sse / sse0,
                        "corr_pred_real": float(np.corrcoef(pr, rr)[0, 1]) if np.std(pr) > 0 else np.nan})
    return pd.DataFrame(out)


def importance(df: pd.DataFrame, first_test: int, models=("RIDGE10", "BOOST")) -> pd.DataFrame:
    """Permutation importance: drop in OOS correlation when a feature is shuffled in the test rows only."""
    rng = np.random.default_rng(C.SEED)
    res = []
    weeks = [w for w in sorted(df["week"].unique()) if w >= first_test]
    base = {m: ([], []) for m in models}
    perm = {(m, f): [] for m in models for f in FEATS}
    for w in weeks:
        tr, te = df[df["week"] < w], df[df["week"] == w]
        if len(tr) < 500 or te.empty:
            continue
        for m in models:
            pr = predict(m, tr, te)
            base[m][0].append(pr)
            base[m][1].append(te["r"].to_numpy(float))
            for f in FEATS:
                te2 = te.copy()
                te2[f] = rng.permutation(te2[f].to_numpy())
                perm[(m, f)].append(predict(m, tr, te2) if m != "BOOST" else None)
    for m in models:
        pr, rr = np.concatenate(base[m][0]), np.concatenate(base[m][1])
        c0 = np.corrcoef(pr, rr)[0, 1]
        for f in FEATS:
            if m == "BOOST":
                continue
            pp = np.concatenate(perm[(m, f)])
            res.append({"model": m, "feature": f, "corr_drop": c0 - np.corrcoef(pp, rr)[0, 1]})
    return pd.DataFrame(res)


def importance_boost(df: pd.DataFrame, first_test: int) -> pd.DataFrame:
    """BOOST importance on the last 6 test weeks only (cost: one refit per week, permuted test rows re-predicted)."""
    rng = np.random.default_rng(C.SEED)
    weeks = [w for w in sorted(df["week"].unique()) if w >= first_test][-6:]
    prs, rrs, perm = [], [], {f: [] for f in FEATS}
    for w in weeks:
        tr, te = df[df["week"] < w], df[df["week"] == w]
        Xtr = tr[FEATS].to_numpy(float)
        Xs = [te[FEATS].to_numpy(float)]
        for f in FEATS:
            x = te[FEATS].to_numpy(float).copy()
            j = FEATS.index(f)
            x[:, j] = rng.permutation(x[:, j])
            Xs.append(x)
        big = np.vstack(Xs)
        out = boost(Xtr, tr["r"].to_numpy(float), big)
        n = len(te)
        prs.append(out[:n])
        rrs.append(te["r"].to_numpy(float))
        for k, f in enumerate(FEATS):
            perm[f].append(out[(k + 1) * n:(k + 2) * n])
    pr, rr = np.concatenate(prs), np.concatenate(rrs)
    c0 = np.corrcoef(pr, rr)[0, 1]
    return pd.DataFrame([{"model": "BOOST (last 6 test weeks)", "feature": f,
                          "corr_drop": c0 - np.corrcoef(np.concatenate(perm[f]), rr)[0, 1]} for f in FEATS])


# ---------------- cumulative correction ----------------

EXT = {"costside": ("../wt-costside/results/posthoc_costside/trials_log.csv",
                    "../wt-costside/results/posthoc_costside/daily_pnl.csv"),
       "search": ("../wt-search/results/posthoc_search/trials.csv", "../wt-search/results/posthoc_search/trades.csv"),
       "maker": ("../wt-costside-maker/results/posthoc_costside_maker/trials_log.csv",
                 "../wt-costside-maker/results/posthoc_costside_maker/daily_pnl.csv"),
       "patterns": ("../wt-costside-patterns/results/posthoc_costside_patterns/trials_log.csv",
                    "../wt-costside-patterns/results/posthoc_costside_patterns/daily_pnl.csv"),
       "unsup": ("../wt-unsup/results/posthoc_unsup/trials_log.csv",
                 "../wt-unsup/results/posthoc_unsup/daily_pnl.csv")}


def external() -> tuple[dict, dict]:
    """Other branches' trials, read-only (as posthoc-costside scripts/costside_log.py external()). costside's own
    trials_log lists only its 156; its daily_pnl has them all."""
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
        for i in ids:
            ser[f"{name}:{i}"] = daily.get(i, pd.Series(dtype=float))
        info[name] = {"trials": int(len(ids)), "status": status, "with_daily": int(sum(1 for i in ids if i in daily))}
    return ser, info


# ---------------- main ----------------

def main() -> None:
    print(LABEL, flush=True)
    df = build_snapshots()
    first_test = C.HIST_WEEKS
    print(f"snapshots: {len(df)} rows, {df['game_id'].nunique()} games", flush=True)
    pf = C.CACHE / "pred.parquet"
    if pf.exists():
        pred = pd.read_parquet(pf)
    else:
        pred = walk_forward(df, first_test)
        pred.to_parquet(pf)
    fit = oos_fit(df, pred)
    print(fit.to_string(index=False), flush=True)
    # own-market series for execution
    games = pd.read_csv(C.DATA / "raw" / "kalshi_only_games.csv")
    need = set(pred["game_id"])
    series = {}
    for r in games[games["game_id"].isin(need)].itertuples():
        t = pd.read_parquet(C.DATA / "raw" / "kalshi_only" / f"{r.game_id}.parquet", columns=["ts", "market_id", "kind", "price"])
        series[(r.game_id, r.home)] = C._own(t, f"{r.kalshi_event}-{r.home}", False)
        series[(r.game_id, r.away)] = C._own(t, f"{r.kalshi_event}-{r.away}", True)
    trials = trade_books(df, pred, series)
    rows, own = [], {}
    for name, b in trials.items():
        m = C.metrics(b)
        alt = C.metrics(b.assign(pnl=b["pnl_alt"], cap=b["cap_alt"])) if len(b) else {}
        rows.append({"trial": name, **m, "alt_roc": alt.get("roc"), "alt_roc_lo": alt.get("roc_lo"),
                     "alt_roc_hi": alt.get("roc_hi"), "alt_c_per_contract": alt.get("c_per_contract"), "label": LABEL})
        own[f"regress:{name}"] = b.groupby("day")["pnl"].sum() if len(b) else pd.Series(dtype=float)
    tl = pd.DataFrame(rows)
    ext, info = external()
    allser = {**ext, **own}
    mt = C.multiple_testing(allser)
    tl["holm_p"] = tl["trial"].map(lambda n: mt["holm"].get(f"regress:{n}") if mt else None)
    tl["raw_p"] = tl["trial"].map(lambda n: mt["raw_p"].get(f"regress:{n}") if mt else None)
    rc_p = mt.get("rc_p", np.nan)
    tl["candidate_edge"] = (tl["roc_lo"] > 0) & (rc_p < 0.05) & (tl["trades"] >= 100) & (tl["excl5_roc"] > 0)
    C.OUT.mkdir(parents=True, exist_ok=True)
    tl.sort_values("roc_lo", ascending=False).to_csv(C.OUT / "trials_log.csv", index=False)
    daily = pd.concat([s.rename("pnl").rename_axis("et_date").reset_index().assign(trial_id=k.split(":", 1)[1])
                       for k, s in own.items() if len(s)], ignore_index=True)
    daily[["trial_id", "et_date", "pnl"]].to_csv(C.OUT / "daily_pnl.csv", index=False)
    fit.to_csv(C.OUT / "oos_fit.csv", index=False)
    imp = importance(df, first_test, models=("RIDGE10",))
    imp = pd.concat([imp, importance_boost(df, first_test)], ignore_index=True)
    imp.to_csv(C.OUT / "feature_importance.csv", index=False)
    corr = {k: v for k, v in mt.items() if k not in ("holm", "raw_p")}
    corr.update(external=info, own_trials=len(trials), cumulative_trials=len(allser),
                holm_survivors_005=[k for k, v in mt.get("holm", {}).items() if v < 0.05],
                candidates=tl.loc[tl["candidate_edge"], "trial"].tolist())
    (C.OUT / "correction.json").write_text(json.dumps(corr, indent=2, default=float))
    write_results(df, fit, tl, imp, corr)


def write_results(df, fit, tl, imp, corr) -> None:
    espn_games = (C.CACHE / "espn_games.txt").read_text() if (C.CACHE / "espn_games.txt").exists() else "?"
    top = tl[tl["trades"] >= 20].sort_values("roc_lo", ascending=False).head(12)
    cols = ["trial", "trades", "roc", "roc_lo", "roc_hi", "c_per_contract", "win_rate", "breakeven", "sharpe_x365",
            "excl5_roc", "alt_roc"]
    imp_r = imp[imp["model"] == "RIDGE10"].sort_values("corr_drop", ascending=False).head(10)
    imp_b = imp[imp["model"] != "RIDGE10"].sort_values("corr_drop", ascending=False).head(10)
    lines = ["# Post-hoc supervised residual regression: results", "", f"**Label: {LABEL}.**", "",
             "Spec: SPEC.md (4b318d6, committed before any real data). One run.", "",
             f"Snapshot rows: {len(df)} ({df['game_id'].nunique()} games); games with usable ESPN state "
             f"(orientation defined, passing the Idea 10 defect rule): {espn_games}.", "",
             "## Is there any predictable residual? (out of sample, test weeks)", "",
             "R^2 is against the Kalshi price as the forecast (r = 0); corr is predicted vs realised residual.", "",
             C.md(fit.round(4)), "",
             "## Trials (48), top 12 by ROC CI lower bound (>= 20 trades)", "",
             "Primary cost line: taker fee (TAKER) or maker fee 0.0175 (MAKER); alt_roc = maker fee 0 for MAKER.", "",
             C.md(top[cols].round(4)), "",
             f"All 48 trials: trials_log.csv. Trials with any trade: {int((tl['trades'] > 0).sum())}.", "",
             "## Feature importance (descriptive; drop in OOS correlation when shuffled)", "",
             C.md(imp_r.round(4)), "", C.md(imp_b.round(4)), "",
             "## Cumulative multiple-testing correction", "",
             f"Trials in correction: {corr.get('cumulative_trials')} (own {corr.get('own_trials')}; external: "
             f"{json.dumps(corr.get('external'))}).",
             f"Studentized Reality Check p (best by t: {corr.get('best_by_t')}): {corr.get('rc_p')}.",
             f"DSR of the best: {corr.get('dsr_best')} (normal returns: {corr.get('dsr_best_normal_returns')}).",
             f"Holm survivors at 0.05: {corr.get('holm_survivors_005')}.",
             f"Candidate edges (CI lo > 0, RC p < 0.05, >= 100 trades, excl. top 5 > 0): {corr.get('candidates')}.", ""]
    (C.OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
