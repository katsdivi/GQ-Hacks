"""Post-hoc cost-side price-pattern search, TRAINING ONLY. Spec: results/posthoc_costside_patterns/SPEC.md.

  PYTHONPATH=.:scripts python scripts/posthoc_costside_patterns.py [--data DIR]

Reads only data/raw/kalshi_only_games.csv, kalshi_market_meta.csv and kalshi_only/<game_id>.parquet (training).
Writes trials_log.csv, daily_pnl.csv, trades_all.csv (gitignored) in results/posthoc_costside_patterns/.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import strategy_a as sa  # noqa: E402

NS = 1_000_000_000
ET = "America/New_York"
QTY = 10
LAT_NS = NS                      # 1.0 s
FILL_WIN_NS = 300 * NS           # 5 min
SEED = 20261004
BOOT = 2000
N_HIST_WEEKS = 6
MIN_WF_TRADES = 30
SETTLE_LAG_NS = 5 * 3600 * NS
OUT = ROOT / "results" / "posthoc_costside_patterns"
BANDS = [(0.70, 0.80), (0.80, 0.90), (0.90, 0.95)]
TIMES = {"ko-5m": -5 * 60, "ko+60m": 60 * 60, "ko+120m": 120 * 60}   # seconds relative to kickoff
LEAGUES = ["ALL", "NFL", "CFB"]


# ---------- pure helpers (unit tested) ----------

def price_asof(tr: tuple[np.ndarray, np.ndarray], t_ns: int, max_age_ns: int) -> float:
    """Last trade price with ts <= t and ts >= t - max_age. NaN if none. Never looks past t."""
    ts, px = tr
    i = np.searchsorted(ts, t_ns, side="right") - 1
    if i < 0 or ts[i] < t_ns - max_age_ns:
        return float("nan")
    return float(px[i])


def fill_price(tr: tuple[np.ndarray, np.ndarray], t_ns: int) -> float | None:
    """First trade with ts >= t + 1 s (and <= t + 5 min): trade price + 1 cent, capped at 0.99."""
    ts, px = tr
    i = np.searchsorted(ts, t_ns + LAT_NS, side="left")
    if i >= len(ts) or ts[i] > t_ns + FILL_WIN_NS:
        return None
    return min(round(float(px[i]) + 0.01, 4), 0.99)


def trade_pnl(price: float, payout: float) -> tuple[float, float, float]:
    """(net pnl, fee, cost basis) for 10 contracts."""
    fee = sa.fee_kalshi_direct(price, QTY)
    return (payout - price) * QTY - fee, fee, price * QTY + fee


def p1_pick(p_ref: dict, p_now: dict, d_cents: float, mode: str):
    """Team to buy for P1 given own-price dicts {team: price} at ref and now, or None."""
    teams = list(p_now)
    if any(math.isnan(p_ref[x]) or math.isnan(p_now[x]) for x in teams):
        return None
    ch = {x: p_now[x] - p_ref[x] for x in teams}
    a, b = teams
    if abs(ch[a] - ch[b]) < 1e-12:
        return None
    riser, faller = (a, b) if ch[a] > ch[b] else (b, a)
    if ch[riser] * 100 < d_cents - 1e-9:
        return None
    return riser if mode == "mom" else faller


def upsets_known(games: list[dict], t_ns: int) -> int:
    """Count of upsets (fav >= 0.70 at its ko-5min lost) among games whose settlement is known by t
    (kickoff + 5 h <= t). Each game dict: ko_ns, fav_px, fav_payout."""
    n = 0
    for h in games:
        if h["ko_ns"] + SETTLE_LAG_NS <= t_ns and h["fav_px"] >= 0.70 and h["fav_payout"] == 0.0:
            n += 1
    return n


# ---------- data ----------

def load(data: Path):
    games = sa.load_games(data / "kalshi_only_games.csv", data / "kalshi_market_meta.csv",
                          ticks_dir=str(data / "kalshi_only"))
    G = []
    for g in games:
        if g.exclude or g.result != g.result:
            continue
        df = pd.read_parquet(data / "kalshi_only" / f"{g.game_id}.parquet")
        tr = {}
        for team in (g.home, g.away):
            t = sa.own_market_trades(df, g, team)
            tr[team] = (t["ts"].to_numpy("int64"), t["price"].to_numpy(float))
        ko = int(g.kickoff.value)
        et = g.kickoff.tz_convert(ET)
        wk = (et.tz_localize(None).normalize() - pd.Timedelta(days=et.dayofweek)).date()
        G.append(dict(g=g, id=g.game_id, league=g.league, ko=ko, et_date=et.date(), week=wk,
                      slot=(et.dayofweek, et.hour), tr=tr))
    weeks = sorted({x["week"] for x in G})
    hist = set(weeks[:N_HIST_WEEKS])
    for x in G:
        x["test"] = x["week"] not in hist
    return G, weeks


def payout(x: dict, team: str) -> float:
    g = x["g"]
    return g.result if team == g.home else 1.0 - g.result


def make_trade(x: dict, team: str, t: int, tid_extra: dict | None = None):
    p = fill_price(x["tr"][team], t)
    if p is None:
        return None
    pay = payout(x, team)
    pnl, fee, cost = trade_pnl(p, pay)
    r = dict(game_id=x["id"], league=x["league"], et_date=x["et_date"], week=x["week"], test=x["test"],
             team=team, fill=p, payout=pay, fee=fee, pnl=pnl, cost=cost)
    if tid_extra:
        r.update(tid_extra)
    return r


# ---------- candidate tables ----------

def p1_candidates(G, d, mode):
    rows = []
    for x in G:
        t = x["ko"] - 30 * 60 * NS
        tref = x["ko"] - 105 * 60 * NS
        teams = (x["g"].home, x["g"].away)
        p_now = {k: price_asof(x["tr"][k], t, 30 * 60 * NS) for k in teams}
        p_ref = {k: price_asof(x["tr"][k], tref, 15 * 60 * NS) for k in teams}
        team = p1_pick(p_ref, p_now, d, mode)
        if team is None:
            continue
        r = make_trade(x, team, t)
        if r:
            rows.append(r)
    return pd.DataFrame(rows)


def fav_at(x, t):
    teams = (x["g"].home, x["g"].away)
    p = {k: price_asof(x["tr"][k], t, 10 * 60 * NS) for k in teams}
    if any(math.isnan(v) for v in p.values()) or p[teams[0]] == p[teams[1]]:
        return None, float("nan")
    f = max(p, key=p.get)
    return f, p[f]


def p3_table(G, tname):
    """All favourite candidates at time tname, with fills, volume (for P5) and the ko-5min upset info."""
    rows = []
    for x in G:
        t = x["ko"] + TIMES[tname] * NS
        f, p = fav_at(x, t)
        if f is None:
            continue
        r = make_trade(x, f, t)
        if r is None:
            continue
        lo = t - 3600 * NS
        vol = sum(int(((ts > lo) & (ts <= t)).sum()) for ts, _ in x["tr"].values())
        r.update(fav_px=p, t_ns=t, ko=x["ko"], slot=x["slot"], vol=vol)
        rows.append(r)
    return pd.DataFrame(rows)


def in_band(df, band):
    lo, hi = band
    return df[(df.fav_px >= lo - 1e-9) & (df.fav_px < hi - 1e-9)]


def lowvol_flags(df: pd.DataFrame) -> pd.Series:
    """True if the game's slot trailing volume (weeks strictly earlier) is in the bottom tercile of slots."""
    out = pd.Series(False, index=df.index)
    for w in sorted(df.week.unique()):
        past = df[df.week < w]
        if past.empty:
            continue
        g = past.groupby("slot").vol.agg(["mean", "count"])
        g = g[g["count"] >= 3]
        if g.empty:
            continue
        thr = np.percentile(g["mean"], 100 / 3)
        low = set(g.index[g["mean"] <= thr])
        m = df.week == w
        out[m] = df[m].slot.map(lambda s: s in low)
    return out


def p4_table(G):
    """ko-5min favourites for all games, with upsets-known count from same-ET-date games (>=5 games that day)."""
    day_n = {}
    for x in G:
        day_n[x["et_date"]] = day_n.get(x["et_date"], 0) + 1
    info = {}
    for x in G:
        t = x["ko"] - 5 * 60 * NS
        f, p = fav_at(x, t)
        info[x["id"]] = dict(ko_ns=x["ko"], fav_px=p if f else float("nan"),
                             fav_payout=payout(x, f) if f else float("nan"), fav=f, t=t)
    by_day = {}
    for x in G:
        by_day.setdefault(x["et_date"], []).append(x)
    rows = []
    for x in G:
        if day_n[x["et_date"]] < 5:
            continue
        me = info[x["id"]]
        if me["fav"] is None:
            continue
        others = [info[y["id"]] for y in by_day[x["et_date"]] if y["id"] != x["id"]]
        k = upsets_known([o for o in others if o["fav"] is not None], me["t"])
        r = make_trade(x, me["fav"], me["t"])
        if r is None:
            continue
        r.update(fav_px=me["fav_px"], k=k)
        rows.append(r)
    return pd.DataFrame(rows)


# ---------- metrics ----------

def metrics(tr: pd.DataFrame, trial_seed=SEED) -> dict:
    tr = tr[tr.test] if len(tr) else tr
    n = len(tr)
    if n == 0:
        return dict(trades=0)
    pnl, cost = tr.pnl.to_numpy(), tr.cost.to_numpy()
    roc = pnl.sum() / cost.sum()
    rng = np.random.default_rng(trial_seed)
    idx = rng.integers(0, n, size=(BOOT, n))
    boots = pnl[idx].sum(1) / cost[idx].sum(1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    daily = tr.groupby("et_date").pnl.sum().sort_index()
    sh = daily.mean() / daily.std(ddof=1) * math.sqrt(365) if len(daily) > 1 and daily.std(ddof=1) > 0 else float("nan")
    cum = daily.cumsum().to_numpy()
    dd = float((np.maximum.accumulate(np.concatenate([[0], cum]))[1:] - cum).max())
    keep = tr.sort_values("pnl", ascending=False).iloc[5:]
    ex_roc = keep.pnl.sum() / keep.cost.sum() if len(keep) else float("nan")
    ex_c = keep.pnl.sum() / (QTY * len(keep)) * 100 if len(keep) else float("nan")
    return dict(trades=n, roc=roc, roc_ci_lo=lo, roc_ci_hi=hi, c_per_contract=pnl.sum() / (QTY * n) * 100,
                win_rate=float((tr.payout > tr.fill).mean()), mean_fill=float(tr.fill.mean()),
                sharpe_x365=sh, max_dd=dd, excl_top5_roc=ex_roc, excl_top5_c=ex_c, net_pnl=pnl.sum())


def wf_select(cells: dict[str, pd.DataFrame], weeks: list) -> pd.DataFrame:
    """Per test week pick the cell with the best cumulative net pnl over strictly earlier weeks (>= 30 trades)."""
    out = []
    for w in weeks[N_HIST_WEEKS:]:
        best, bp = None, -1e18
        for name, df in cells.items():
            past = df[df.week < w]
            if len(past) >= MIN_WF_TRADES and past.pnl.sum() > bp:
                best, bp = name, past.pnl.sum()
        if best is not None:
            cur = cells[best][cells[best].week == w]
            out.append(cur.assign(cell=best))
    return pd.concat(out) if out else pd.DataFrame()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "raw"))
    a = ap.parse_args()
    G, weeks = load(Path(a.data))
    print(f"games {len(G)}, weeks {len(weeks)}, test games {sum(x['test'] for x in G)}", flush=True)
    trials = {}   # id -> (method, params, df)
    # P1
    i = 0
    for d in (3, 5):
        for mode in ("mom", "rev"):
            c = p1_candidates(G, d, mode)
            for lg in LEAGUES:
                i += 1
                df = c if lg == "ALL" else c[c.league == lg]
                trials[f"P1-{i:02d}"] = ("P1_drift", f"d={d}c mode={mode} league={lg}", df)
    # P3 / P5 / P4
    tabs = {t: p3_table(G, t) for t in TIMES}
    i = 0
    for t in TIMES:
        for b in BANDS:
            for lg in LEAGUES:
                i += 1
                df = in_band(tabs[t], b)
                df = df if lg == "ALL" else df[df.league == lg]
                trials[f"P3-{i:02d}"] = ("P3_longshot", f"time={t} band={b[0]:.2f}-{b[1]:.2f} league={lg}", df)
    i = 0
    for t in TIMES:
        tb = tabs[t]
        tb = tb[lowvol_flags(tb)]
        for b in BANDS:
            i += 1
            trials[f"P5-{i:02d}"] = ("P5_lowvol", f"time={t} band={b[0]:.2f}-{b[1]:.2f} league=ALL", in_band(tb, b))
    p4 = p4_table(G)
    i = 0
    for K in (1, 2):
        for b in BANDS:
            i += 1
            trials[f"P4-{i:02d}"] = ("P4_slate", f"K>={K} band={b[0]:.2f}-{b[1]:.2f} league=ALL",
                                     in_band(p4[p4.k >= K], b))
    for tag, pre in (("W-P1", "P1-"), ("W-P3", "P3-"), ("W-P5", "P5-")):
        cells = {k: v[2] for k, v in trials.items() if k.startswith(pre)}
        trials[tag] = ("WF_select_" + pre[:2], "cum-net-pnl past weeks, >=30 trades", wf_select(cells, weeks))
    assert len(trials) == 57, len(trials)
    log, daily, allt = [], [], []
    for tid, (method, params, df) in trials.items():
        m = metrics(df)
        log.append(dict(round=1, trial_id=tid, method=method, params=params, **m))
        if len(df):
            t = df[df.test]
            if len(t):
                dd = t.groupby("et_date").pnl.sum().reset_index()
                dd.insert(0, "trial_id", tid)
                daily.append(dd)
                allt.append(t.assign(trial_id=tid)[["trial_id", "game_id", "league", "et_date", "team", "fill",
                                                     "payout", "fee", "pnl"]])
    OUT.mkdir(parents=True, exist_ok=True)
    cols = ["round", "trial_id", "method", "params", "trades", "roc", "roc_ci_lo", "roc_ci_hi", "c_per_contract",
            "excl_top5_roc", "excl_top5_c", "win_rate", "mean_fill", "sharpe_x365", "max_dd", "net_pnl"]
    pd.DataFrame(log).reindex(columns=cols).to_csv(OUT / "trials_log.csv", index=False)
    pd.concat(daily).rename(columns={"pnl": "pnl"}).to_csv(OUT / "daily_pnl.csv", index=False)
    pd.concat(allt).to_csv(OUT / "trades_all.csv", index=False)
    print(pd.DataFrame(log).reindex(columns=cols).drop(columns=["round", "method"]).round(4).to_string())


if __name__ == "__main__":
    main()
