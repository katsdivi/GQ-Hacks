"""Post-hoc unsupervised regime mining: PCA + k-means / GMM-lite clusters of market and game states, walk-forward.

post-hoc, exploratory; clusters fit on past weeks only; training only (kickoff before 2026-08-01); holdout not run.
Rules: results/posthoc_unsup/SPEC.md (committed before any real-data run).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_unsup.py build      snapshot dataset -> data/unsup_cache/snapshots.parquet (gitignored)
  python scripts/posthoc_unsup.py run        64 walk-forward trials, correction, atlas -> results/posthoc_unsup/
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import strategy_a as A
import unsup_common as C

LABEL = "post-hoc, exploratory; clusters fit on past weeks only; training only; holdout not run"
DATA = C.DATA
ESPN = Path("/Users/divyamkataria/GQ HACKS/wt-idea6/data/espn_raw")
IDEA13 = Path("/Users/divyamkataria/GQ HACKS/wt-idea13/results/posthoc_idea13/training_games.csv")
COSTSIDE = Path("/Users/divyamkataria/GQ HACKS/wt-costside")
NS = C.NS
DEC_MIN = [-30, -5] + list(range(20, 181, 10))
STALE_S = 600
SEED = 20261004

FEATS = ["p", "dp1", "dp5", "dp15", "n5", "n15", "v5", "v15", "imb5", "log_age", "p_other", "p_sum",
         "pm_gap", "pm_log_age", "pm_miss", "es_diff", "es_period", "es_elapsed", "es_poss", "es_wp", "es_miss",
         "nfl", "preseason", "sat", "sun", "hour", "mins_from_ko", "line_gap", "line_miss"]


# ---------------- ESPN ----------------

def _clock_s(p: dict) -> float:
    try:
        m, s = str(p["clock"]["displayValue"]).split(":")
        return 60 * float(m) + float(s)
    except Exception:
        return np.nan


def espn_state(summary: dict, ko_ns: int) -> dict | None:
    """Plays with wallclock, score, period, clock, possession team id, and win prob; None if the game fails the
    wallclock defect rule (a play outside [ko - 30 min, ko + 6 h], or > 5 min earlier than the previous play)."""
    plays = [p for d in (summary.get("drives") or {}).get("previous", []) for p in d.get("plays", [])]
    rows = []
    for p in plays:
        if not p.get("wallclock"):
            continue
        rows.append((pd.Timestamp(p["wallclock"]).value, p.get("homeScore"), p.get("awayScore"),
                     (p.get("period") or {}).get("number"), _clock_s(p),
                     ((p.get("start") or {}).get("team") or {}).get("id"), str(p.get("id"))))
    if not rows:
        return None
    ts = np.array([r[0] for r in rows], dtype=np.int64)
    if (ts < ko_ns - 1800 * NS).any() or (ts > ko_ns + 6 * 3600 * NS).any():
        return None
    if (np.diff(ts) < -300 * NS).any():
        return None
    wp = {str(w.get("playId")): w.get("homeWinPercentage") for w in summary.get("winprobability", []) or []}
    comp = summary["header"]["competitions"][0]
    home_id = [c["id"] for c in comp["competitors"] if c["homeAway"] == "home"][0]
    return {"ts": ts, "home": np.array([r[1] if r[1] is not None else np.nan for r in rows], float),
            "away": np.array([r[2] if r[2] is not None else np.nan for r in rows], float),
            "period": np.array([r[3] or np.nan for r in rows], float), "clock": np.array([r[4] for r in rows]),
            "poss": [r[5] for r in rows], "wp": np.array([wp.get(r[6], np.nan) if wp.get(r[6]) is not None
                                                           else np.nan for r in rows], float),
            "home_id": home_id, "comp": comp}


def espn_at(es: dict | None, t: int, team_is_espn_home: bool) -> dict:
    """ESPN features from the last play with wallclock <= t (plays are in ESPN order; we take the max index whose
    wallclock <= t among plays up to the last such one, so a later play never leaks)."""
    out = {"es_diff": np.nan, "es_period": np.nan, "es_elapsed": np.nan, "es_poss": 0.0, "es_wp": np.nan,
           "es_miss": 1.0}
    if es is None:
        return out
    ok = np.flatnonzero(es["ts"] <= t)
    if len(ok) == 0:
        out.update(es_diff=0.0, es_period=0.0, es_elapsed=0.0, es_miss=0.0)   # game not started in ESPN yet
        return out
    i = ok[-1]
    h, a = es["home"][i], es["away"][i]
    diff = (h - a) if team_is_espn_home else (a - h)
    per, clk = es["period"][i], es["clock"][i]
    elapsed = (per - 1) * 900 + (900 - clk) if per == per and clk == clk else np.nan
    pid = es["poss"][i]
    poss = 0.0 if pid is None else (1.0 if (pid == es["home_id"]) == team_is_espn_home else -1.0)
    wps = es["wp"][ok]                                   # only plays with wallclock <= t
    wps = wps[~np.isnan(wps)]
    wp = float(wps[-1]) if len(wps) else np.nan
    if wp == wp and not team_is_espn_home:
        wp = 1 - wp
    out.update(es_diff=diff, es_period=per, es_elapsed=elapsed, es_poss=poss, es_wp=wp, es_miss=0.0)
    return out


# ---------------- snapshots ----------------

def asof(ts: np.ndarray, px: np.ndarray, t: int) -> float:
    i = np.searchsorted(ts, t, side="right") - 1
    return float(px[i]) if i >= 0 else np.nan


def game_rows(gid: str, league: str, home: str, away: str, event: str, ko_ns: int, trades: pd.DataFrame,
              pm: tuple | None, es: dict | None, espn_home_is_kalshi_home: bool | None,
              line_home: float, preseason: bool) -> list[dict]:
    """Snapshot rows for one game. Every feature uses rows with ts <= t only."""
    tr = trades[trades["kind"] == "trade"].sort_values("ts", kind="stable")
    all_ts = tr["ts"].to_numpy(np.int64)
    all_sz = tr["size"].to_numpy(float)
    sgn = np.where(tr["side"].to_numpy() == "buy", 1.0, np.where(tr["side"].to_numpy() == "sell", -1.0, 0.0))
    own = {}
    for team, away_flag in ((home, False), (away, True)):
        x = tr[tr["market_id"] == f"{event}-{team}"]
        px = x["price"].to_numpy(float)
        own[team] = (x["ts"].to_numpy(np.int64), np.round(1 - px if away_flag else px, 4))
    rows = []
    for m in DEC_MIN:
        t = ko_ns + m * 60 * NS
        k = np.searchsorted(all_ts, t, side="right")          # trades [0, k) have ts <= t
        for team, other in ((home, away), (away, home)):
            ts, px = own[team]
            i = np.searchsorted(ts, t, side="right") - 1
            if i < 0 or (t - ts[i]) > STALE_S * NS:
                continue
            p = float(px[i])
            r = {"game_id": gid, "team": team, "is_home": team == home, "t_ns": t, "dec_min": m, "p": p}
            for lab, sec in (("dp1", 60), ("dp5", 300), ("dp15", 900)):
                q = asof(ts, px, t - sec * NS)
                r[lab] = p - q if q == q else 0.0
            for lab, sec in (("5", 300), ("15", 900)):
                j = np.searchsorted(all_ts, t - sec * NS, side="right")
                r["n" + lab] = float(k - j)
                r["v" + lab] = float(all_sz[j:k].sum())
            j = np.searchsorted(all_ts, t - 300 * NS, side="right")
            tot = all_sz[j:k].sum()
            imb = float((all_sz[j:k] * sgn[j:k]).sum() / tot) if tot > 0 else 0.0
            r["imb5"] = imb if team == home else -imb
            r["log_age"] = float(np.log1p((t - ts[i]) / NS))
            to, po = own[other]
            r["p_other"] = asof(to, po, t)
            r["p_sum"] = p + r["p_other"] if r["p_other"] == r["p_other"] else np.nan
            if pm is not None and len(pm[0]):
                pi = np.searchsorted(pm[0], t, side="right") - 1
                if pi >= 0:
                    ph = float(pm[1][pi])
                    r["pm_gap"] = (ph if team == home else 1 - ph) - p
                    r["pm_log_age"] = float(np.log1p((t - pm[0][pi]) / NS))
                    r["pm_miss"] = 0.0
            r.setdefault("pm_gap", np.nan)
            r.setdefault("pm_log_age", np.nan)
            r.setdefault("pm_miss", 1.0)
            if espn_home_is_kalshi_home is None:
                r.update(espn_at(None, t, True))
            else:
                r.update(espn_at(es, t, (team == home) == espn_home_is_kalshi_home))
            et = pd.Timestamp(t, unit="ns", tz="UTC").tz_convert("America/New_York")
            r.update(nfl=float(league == "NFL"), preseason=float(preseason), sat=float(et.weekday() == 5),
                     sun=float(et.weekday() == 6), hour=float(et.hour), mins_from_ko=float(m))
            if line_home == line_home:
                r["line_gap"] = (line_home if team == home else 1 - line_home) - p
                r["line_miss"] = 0.0
            else:
                r["line_gap"], r["line_miss"] = np.nan, 1.0
            rows.append(r)
    return rows


def build() -> pd.DataFrame:
    games = A.load_games(DATA / "raw" / "kalshi_only_games.csv", DATA / "raw" / "kalshi_market_meta.csv",
                         ticks_dir=DATA / "raw" / "kalshi_only")
    assert all(g.kickoff < C.SEAL for g in games), "training only"
    sett = C._settle_map()
    ids = pd.read_csv(ESPN / "ids_training.csv").set_index("game_id")
    lines = pd.read_csv(IDEA13).set_index("game_id")["p_home"] if IDEA13.exists() else pd.Series(dtype=float)
    bg = pd.read_csv(C.OUTB / "b_games_espn.csv")
    bset = set(bg["game_id"]) - C.EXCLUDED_A1
    sys.path.insert(0, "/Users/divyamkataria/GQ HACKS/wt-idea6/scripts")
    import posthoc_idea6 as I6   # orient() (ESPN -> Kalshi team orientation by name), commit 0f57732
    out, stats = [], {"games": 0, "no_file": 0, "espn_ok": 0, "espn_defect": 0, "espn_missing": 0, "orient_none": 0}
    for n, g in enumerate(games):
        f = DATA / "raw" / "kalshi_only" / f"{g.game_id}.parquet"
        if not f.exists():
            stats["no_file"] += 1
            continue
        stats["games"] += 1
        trades = pd.read_parquet(f, columns=["ts", "market_id", "kind", "price", "size", "side"])
        pm = None
        if g.game_id in bset:
            pp = DATA / "ticks" / f"{g.game_id}_polymarket.parquet"
            if pp.exists():
                pmd = pd.read_parquet(pp, columns=["ts", "kind", "price"])
                pmd = pmd[pmd["kind"] == "trade"].sort_values("ts", kind="stable")
                pm = (pmd["ts"].to_numpy(np.int64), np.round(pmd["price"].to_numpy(float), 4))
        es, ori = None, None
        if g.game_id in ids.index and ids.loc[g.game_id, "espn_id"] == ids.loc[g.game_id, "espn_id"]:
            eid = str(ids.loc[g.game_id, "espn_id"]).split(".")[0]
            sf = ESPN / f"{g.league.lower()}_{eid}.json"
            if sf.exists():
                s = json.loads(sf.read_text())
                es = espn_state(s, g.kickoff.value)
                if es is None:
                    stats["espn_defect"] += 1
                else:
                    o = I6.orient(es["comp"], (ids.loc[g.game_id, "k_home_name"], g.home),
                                  (ids.loc[g.game_id, "k_away_name"], g.away))
                    if o is None:
                        stats["orient_none"] += 1
                    else:
                        ori = o == "same"
                        stats["espn_ok"] += 1
            else:
                stats["espn_missing"] += 1
        else:
            stats["espn_missing"] += 1
        rows = game_rows(g.game_id, g.league, g.home, g.away, g.event, g.kickoff.value, trades, pm,
                         es if ori is not None else None, ori, float(lines.get(g.game_id, np.nan)),
                         A.is_preseason(g))
        for r in rows:
            r["league"] = g.league
            r["payout"] = sett.get((g.game_id, "home" if r["is_home"] else "away"), np.nan)
            r["kickoff_ns"] = g.kickoff.value
        out += rows
        if n % 200 == 0:
            print(f"  {n}/{len(games)}", flush=True)
    df = pd.DataFrame(out)
    C.CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(C.CACHE / "snapshots.parquet", index=False)
    (C.CACHE / "build_stats.json").write_text(json.dumps(stats, indent=1))
    print(stats, len(df), flush=True)
    return df


# ---------------- clustering (numpy) ----------------

def standardize_fit(X: np.ndarray):
    mu = np.nanmean(X, 0)
    sd = np.nanstd(X, 0)
    sd[~(sd > 0)] = 1.0
    mu = np.where(np.isnan(mu), 0.0, mu)
    return mu, sd


def standardize(X, mu, sd):
    Z = (X - mu) / sd
    return np.where(np.isnan(Z), 0.0, Z)


def pca_fit(Z: np.ndarray, var: float = 0.90, kmax: int = 10):
    U, S, Vt = np.linalg.svd(Z - Z.mean(0), full_matrices=False)
    ev = S ** 2 / max((S ** 2).sum(), 1e-12)
    k = int(min(kmax, np.searchsorted(np.cumsum(ev), var) + 1))
    return Z.mean(0), Vt[:k].T


def kmeans(X: np.ndarray, k: int, seed: int = SEED, restarts: int = 3, iters: int = 60):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(restarts):
        c = [X[rng.integers(len(X))]]
        for _j in range(1, k):                                     # k-means++
            d2 = np.min(((X[:, None, :] - np.array(c)[None]) ** 2).sum(-1), 1)
            c.append(X[rng.choice(len(X), p=d2 / d2.sum())] if d2.sum() > 0 else X[rng.integers(len(X))])
        c = np.array(c)
        for _it in range(iters):
            lab = np.argmin(((X[:, None, :] - c[None]) ** 2).sum(-1), 1)
            new = np.array([X[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
            if np.allclose(new, c):
                break
            c = new
        inertia = ((X - c[lab]) ** 2).sum()
        if best is None or inertia < best[0]:
            best = (inertia, c)
    return best[1]


def kmeans_assign(X, c):
    return np.argmin(((X[:, None, :] - c[None]) ** 2).sum(-1), 1)


def gmm_fit(X: np.ndarray, k: int, iters: int = 60):
    c = kmeans(X, k)
    lab = kmeans_assign(X, c)
    w = np.array([(lab == j).mean() for j in range(k)]) + 1e-6
    mu = c.copy()
    var = np.array([X[lab == j].var(0) if (lab == j).sum() > 1 else X.var(0) for j in range(k)]) + 1e-3
    for _ in range(iters):
        ll = gmm_loglik(X, w, mu, var)
        r = np.exp(ll - ll.max(1, keepdims=True))
        r /= r.sum(1, keepdims=True)
        nk = r.sum(0) + 1e-9
        w = nk / nk.sum()
        mu = (r.T @ X) / nk[:, None]
        var = (r.T @ (X ** 2)) / nk[:, None] - mu ** 2 + 1e-3
    return w, mu, var


def gmm_loglik(X, w, mu, var):
    return (np.log(w)[None] - 0.5 * (np.log(2 * np.pi * var).sum(1))[None]
            - 0.5 * (((X[:, None, :] - mu[None]) ** 2) / var[None]).sum(-1))


def gmm_assign(X, model):
    return np.argmax(gmm_loglik(X, *model), 1)


def fit_assign(train: np.ndarray, test: np.ndarray, method: str, k: int):
    """Fit standardization + PCA + clusterer on train rows only; return labels for train and test."""
    mu, sd = standardize_fit(train)
    Ztr, Zte = standardize(train, mu, sd), standardize(test, mu, sd)
    m, V = pca_fit(Ztr)
    Ptr, Pte = (Ztr - m) @ V, (Zte - m) @ V
    if method == "kmeans":
        c = kmeans(Ptr, k)
        return kmeans_assign(Ptr, c), kmeans_assign(Pte, c)
    g = gmm_fit(Ptr, k)
    return gmm_assign(Ptr, g), gmm_assign(Pte, g)


# ---------------- walk-forward ----------------

def cost(p: np.ndarray, line: str) -> np.ndarray:
    if line == "taker":
        return 0.01 + np.array([C.fee_taker(x) for x in p]) / C.QTY
    return np.array([C.fee_maker175(x) for x in p]) / C.QTY


def add_weeks(df: pd.DataFrame) -> pd.DataFrame:
    wk = pd.to_datetime(df["kickoff_ns"], unit="ns", utc=True).dt.tz_convert("America/New_York") \
        .dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    weeks = sorted(wk.unique())
    return df.assign(week=wk.map({w: i for i, w in enumerate(weeks)}))


def execute(row, line: str, own: dict) -> dict | None:
    ts, px = own[(row.game_id, row.team)]
    if line == "taker":
        e = C.taker_entry(ts, px, int(row.t_ns), win_s=300.0)
        if e is None:
            return None
        f = e[1]
        fee, alt = C.fee_taker(f), C.fee_taker(f)
    else:
        e = C.maker_entry(ts, px, int(row.t_ns), limit=float(row.p), w_s=300.0)
        if e is None:
            return None
        f = e[1]
        fee, alt = C.fee_maker175(f), 0.0
    b = C.book_trade(f, fee, payout=float(row.payout))
    return {"entry": f, "fee_entry": fee, "pnl": b["pnl"], "cap": b["cap"],
            "pnl_alt": (row.payout - f) * C.QTY - alt, "cap_alt": f * C.QTY + alt}


def own_series(df: pd.DataFrame) -> dict:
    out = {}
    for gid in df["game_id"].unique():
        t = pd.read_parquet(DATA / "raw" / "kalshi_only" / f"{gid}.parquet", columns=["ts", "market_id", "kind", "price"])
        ev = t["market_id"].iloc[0].rsplit("-", 1)[0]
        sub = df[df["game_id"] == gid]
        home = sub[sub["is_home"]]["team"].iloc[0] if sub["is_home"].any() else None
        for team in sub["team"].unique():
            ts, px = C._own(t, f"{ev}-{team}", team != home)
            out[(gid, team)] = (ts, px)
    return out


def walk_forward(df: pd.DataFrame, own: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df[df["payout"].notna()].copy()
    X = df[FEATS].to_numpy(float)
    df["net_taker"] = df["payout"] - df["p"] - cost(df["p"].to_numpy(), "taker")
    df["net_maker"] = df["payout"] - df["p"] - cost(df["p"].to_numpy(), "maker")
    trades, ranks = [], []
    test_weeks = sorted(w for w in df["week"].unique() if w >= C.HIST_WEEKS)
    for w in test_weeks:
        past, cur = (df["week"] < w).to_numpy(), (df["week"] == w).to_numpy()
        if cur.sum() == 0:
            continue
        for method in ("kmeans", "gmm"):
            for k in (8, 16):
                ltr, lte = fit_assign(X[past], X[cur], method, k)
                P, Cu = df[past].assign(cl=ltr), df[cur].assign(cl=lte)
                for line in ("taker", "maker"):
                    st = P.groupby("cl")[f"net_{line}"].agg(["mean", "count"])
                    Cu2 = Cu.assign(cl_mean=Cu["cl"].map(st["mean"]), cl_n=Cu["cl"].map(st["count"]).fillna(0))
                    rank = st["mean"].rank(ascending=False, method="first")
                    Cu2["cl_rank"] = Cu2["cl"].map(rank)
                    for margin in (0.0, 0.01):
                        for nmin in (100, 300):
                            el = Cu2[(Cu2["cl_mean"] > margin) & (Cu2["cl_n"] >= nmin)]
                            el = el.sort_values(["game_id", "t_ns", "cl_mean"], ascending=[True, True, False])
                            per_time = el.drop_duplicates(["game_id", "t_ns"])
                            prim = per_time.drop_duplicates("game_id")
                            for sel, sub in (("primary", prim), ("secondary", per_time)):
                                tid = f"U.{method}.k{k}.m{int(margin * 100)}.n{nmin}.{line}.{sel}"
                                for r in sub.itertuples():
                                    x = execute(r, line, own)
                                    if x is None:
                                        continue
                                    trades.append({"trial": tid, "game_id": r.game_id, "team": r.team,
                                                   "t_ns": r.t_ns, "week": w, "cl_rank": r.cl_rank,
                                                   "cl_mean": r.cl_mean, "payout": r.payout,
                                                   "day": C.et_date(int(r.t_ns)), **x})
        print(f"  week {w}: done", flush=True)
    return pd.DataFrame(trades), df


def trial_ids() -> list[str]:
    return [f"U.{m}.k{k}.m{mg}.n{n}.{l}.{s}" for m in ("kmeans", "gmm") for k in (8, 16) for mg in (0, 1)
            for n in (100, 300) for l in ("taker", "maker") for s in ("primary", "secondary")]


def costside_series() -> dict:
    """Cumulative trials' daily P&L: posthoc-costside own (its daily_pnl.csv) plus its external set (read-only)."""
    sys.path.insert(0, str(COSTSIDE / "scripts"))
    d = pd.read_csv(COSTSIDE / "results/posthoc_costside/daily_pnl.csv")
    tl = pd.read_csv(COSTSIDE / "results/posthoc_costside/trials_log.csv")
    ser = {k: v.groupby("et_date")["pnl"].sum() for k, v in d.groupby("trial_id")}
    for t in tl["trial"]:
        ser.setdefault(t, pd.Series(dtype=float))
    import os
    cwd = os.getcwd()
    os.chdir(COSTSIDE)                                          # costside_log.EXT paths are relative to its repo root
    try:
        import costside_log
        ext, info = costside_log.external()
    finally:
        os.chdir(cwd)
    ser.update(ext)
    return ser, {"costside_own": int(len(tl)), **info}


def atlas(df: pd.DataFrame) -> pd.DataFrame:
    """DESCRIPTIVE ONLY, in-sample: k-means k = 8 on all training rows."""
    X = df[FEATS].to_numpy(float)
    lab, _ = fit_assign(X, X[:1], "kmeans", 8)
    d = df.assign(cl=lab)
    g = d.groupby("cl").agg(rows=("p", "size"), price=("p", "mean"), mins_from_ko=("mins_from_ko", "mean"),
                            nfl=("nfl", "mean"), score_diff=("es_diff", "mean"), espn_missing=("es_miss", "mean"),
                            pm_gap=("pm_gap", "mean"), dp5=("dp5", "mean"), n15=("n15", "mean"),
                            imb5=("imb5", "mean"), net_resid_taker=("net_taker", "mean"),
                            raw_resid=("payout", "mean"))
    g["raw_resid"] = g["raw_resid"] - d.groupby("cl")["p"].mean()
    return g.reset_index()


def run() -> None:
    df = add_weeks(pd.read_parquet(C.CACHE / "snapshots.parquet"))
    assert (df["kickoff_ns"] < C.SEAL.value).all(), "training only"
    own = own_series(df)
    trades, dfx = walk_forward(df, own)
    C.CACHE.mkdir(parents=True, exist_ok=True)
    trades.to_parquet(C.CACHE / "trades.parquet", index=False)
    rows, series = [], {}
    for tid in trial_ids():
        d = trades[trades["trial"] == tid] if len(trades) else trades
        m = C.metrics(d) if len(d) else {"trades": 0, "games": 0}
        alt = d.assign(pnl=d["pnl_alt"], cap=d["cap_alt"]) if len(d) else d
        ma = C.metrics(alt) if len(d) else {}
        rows.append({"trial": tid, **m, "alt_roc": ma.get("roc"), "alt_roc_lo": ma.get("roc_lo"),
                     "alt_roc_hi": ma.get("roc_hi"), "alt_c_per_contract": ma.get("c_per_contract")})
        series[tid] = d.groupby("day")["pnl"].sum() if len(d) else pd.Series(dtype=float)
    log = pd.DataFrame(rows)
    prior, info = costside_series()
    allser = {**prior, **series}
    mt = C.multiple_testing(allser)
    log["holm_p"] = log["trial"].map(mt.get("holm", {}))
    log["raw_p"] = log["trial"].map(mt.get("raw_p", {}))
    log["label"] = LABEL
    log = log.sort_values("roc", ascending=False)
    C.OUT.mkdir(parents=True, exist_ok=True)
    log.to_csv(C.OUT / "trials_log.csv", index=False)
    pd.concat([v.rename("pnl").rename_axis("et_date").reset_index().assign(trial_id=k)
               for k, v in series.items() if len(v)], ignore_index=True)[["trial_id", "et_date", "pnl"]] \
        .to_csv(C.OUT / "daily_pnl.csv", index=False)
    stop = log[(log["roc_lo"] > 0) & (log["trades"] >= 100) & (log["excl5_pnl"] > 0)]
    corr = {"own_trials": len(trial_ids()), "prior": info, "cumulative_trials": len(allser),
            "rc_p_best_by_t": mt.get("rc_p"), "best_by_t": mt.get("best_by_t"), "best_t": mt.get("best_t"),
            "dsr_best": mt.get("dsr_best"), "dsr_best_normal_returns": mt.get("dsr_best_normal_returns"),
            "days": mt.get("days"), "holm_survivors_005": [k for k, v in mt.get("holm", {}).items() if v < 0.05],
            "stop_candidates": stop["trial"].tolist(),
            "stop_condition_met": bool((not stop.empty) and mt.get("rc_p", 1) < 0.05)}
    (C.OUT / "correction.json").write_text(json.dumps(corr, indent=1, default=float))
    at = atlas(dfx)
    at.to_csv(C.OUT / "atlas_in_sample.csv", index=False)
    ref = trades[trades["trial"] == "U.kmeans.k8.m0.n100.taker.primary"] if len(trades) else trades
    rk = []
    for r in range(1, 6):
        d = ref[ref["cl_rank"] == r]
        rk.append({"past_rank": r, **(C.metrics(d) if len(d) else {"trades": 0})})
    rk = pd.DataFrame(rk)
    rk.to_csv(C.OUT / "rank_performance.csv", index=False)
    stats = json.loads((C.CACHE / "build_stats.json").read_text())
    write_results(log, corr, at, rk, stats, df)
    print(json.dumps(corr, indent=1, default=float))


def write_results(log, corr, at, rk, stats, df) -> None:
    cols = ["trial", "trades", "games", "roc", "roc_lo", "roc_hi", "c_per_contract", "win_rate", "breakeven",
            "sharpe_x365", "max_dd", "excl5_roc", "excl5_pnl", "alt_roc", "holm_p"]
    cols = [c for c in cols if c in log]
    L = ["# Post-hoc unsupervised regime mining: results", "", f"**Label: {LABEL}.** Spec: SPEC.md.", "",
         f"Snapshot build: {json.dumps(stats)}; {len(df)} snapshot rows; ESPN features missing for games failing "
         "the wallclock defect rule or with no orientation.", "",
         "## All 64 trials (walk-forward test weeks; primary cost line: taker 0.07 fee, or maker 0.0175 fee; "
         "alt_roc = maker fee 0 for maker trials)", "", C.md(log[cols]), "",
         "## Multiple-testing correction over cumulative trials", "", "```", json.dumps(corr, indent=1, default=float),
         "```", "",
         "## Walk-forward performance by the past rank of the trade's cluster (k-means k 8, margin 0, n_min 100, "
         "taker, primary)", "", C.md(rk), "",
         "## Cluster atlas (DESCRIPTIVE ONLY, in-sample: k-means k 8 on all training rows)", "",
         "net_resid_taker = mean(payout - price - taker cost); raw_resid = mean(payout - price).", "", C.md(at), ""]
    (C.OUT / "RESULTS.md").write_text("\n".join(L))


def ranks() -> None:
    """Added after the run (not in SPEC): the SPEC reference trial (k-means k 8, margin 0, n_min 100, taker,
    primary) made 0 trades, so its rank table is empty. Descriptive supplement: all trades of all 64 trials,
    de-duplicated on (game, team, decision time, execution line), grouped by the past rank (1 to 5) of the
    trade's cluster in that week. Not a trial; overlapping trials make it a pooled view only."""
    t = pd.read_parquet(C.CACHE / "trades.parquet")
    t["line"] = t["trial"].str.split(".").str[5]
    t["method"] = t["trial"].str.split(".").str[1]
    out = []
    for (line, method), g in t.groupby(["line", "method"]):
        g = g.drop_duplicates(["game_id", "team", "t_ns"])
        for r in range(1, 6):
            d = g[g["cl_rank"] == r]
            m = C.metrics(d) if len(d) else {"trades": 0}
            out.append({"execution": line, "clusterer": method, "past_rank": r,
                        **{k: m.get(k) for k in ("trades", "games", "roc", "roc_lo", "roc_hi", "c_per_contract",
                                                 "win_rate", "breakeven", "excl5_roc")}})
    rk = pd.DataFrame(out)
    rk.to_csv(C.OUT / "rank_performance_pooled.csv", index=False)
    txt = (C.OUT / "RESULTS.md").read_text()
    marker = "## Cluster atlas"
    add = ("## Pooled walk-forward performance by past cluster rank (added after the run; descriptive only)\n\n"
           "The SPEC reference trial made 0 trades (no k-means k 8 cluster ever cleared the taker cost on past "
           "weeks), so the table above is empty. This supplement pools all trades of all 64 trials, de-duplicated "
           "on (game, team, decision time, execution), by the past rank of the trade's cluster. Overlapping trials; "
           "not a trial and not counted in the correction.\n\n" + C.md(rk) + "\n\n")
    (C.OUT / "RESULTS.md").write_text(txt.replace(marker, add + marker, 1))
    print(rk.round(4).to_string(index=False))


if __name__ == "__main__":
    {"build": build, "run": run, "ranks": ranks}[sys.argv[1]]()
