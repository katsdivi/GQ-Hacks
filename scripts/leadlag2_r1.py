"""Post-hoc leadlag2 Round 1: polymarket.com vs Kalshi information share, and IS-gated gap trades.

post-hoc, exploratory; training only (kickoff before 2026-08-01). Spec: results/posthoc_leadlag2/SPEC.md (Round 1,
55d151c, committed before any R1 data was read).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/leadlag2_r1.py          descriptive D1 to D4 and the 24 trading trials
Writes data/leadlag2_cache/{r1_games.pkl, r1_trades.parquet} (gitignored) and results/posthoc_leadlag2/r1_*.csv.
"""
from __future__ import annotations

import pickle
import sys

import numpy as np
import pandas as pd
from scipy import stats

import leadlag2_common as C

STEP = 5 * C.NS                     # 5 s grid
LAGS = 12                           # +-60 s
STALE = 30 * C.NS
MIN_CHANGES = 50


# ---------------- data ----------------

def _side_flow(x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    x = x[x["kind"] == "trade"].sort_values("ts", kind="stable")
    s = np.where(x["side"].astype(str) == "buy", 1.0, np.where(x["side"].astype(str) == "sell", -1.0, 0.0))
    return x["ts"].to_numpy(np.int64), s * x["size"].to_numpy(float)


def load_r1_games() -> list[dict]:
    """B training games with polymarket.com ticks: Kalshi P(home) series and signed flow, polymarket.com likewise."""
    f = C.CACHE / "r1_games.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    C.CACHE.mkdir(parents=True, exist_ok=True)
    sett = C._settle_map()
    ko = pd.read_csv(C.DATA / "raw" / "kalshi_only_games.csv")
    b = pd.read_csv(C.OUTB / "b_games_espn.csv")
    bset = set(b["game_id"]) - C.EXCLUDED_A1
    games = []
    for r in ko.itertuples():
        k = pd.Timestamp(r.kickoff_utc_espn)
        assert k < C.SEAL, "training only"
        if r.game_id not in bset:
            continue
        pk = C.DATA / "raw" / "kalshi_only" / f"{r.game_id}.parquet"
        pp = C.DATA / "ticks" / f"{r.game_id}_polymarket.parquet"
        if not (pk.exists() and pp.exists()):
            continue
        t = pd.read_parquet(pk, columns=["ts", "market_id", "kind", "price", "size", "side"])
        q = pd.read_parquet(pp, columns=["ts", "kind", "price", "size", "side"])
        games.append({"game_id": r.game_id, "league": r.league, "home": r.home, "away": r.away,
                      "kickoff_ns": k.value,
                      "pay": {r.home: sett.get((r.game_id, "home"), np.nan),
                              r.away: sett.get((r.game_id, "away"), np.nan)},
                      "own": {r.home: C._own(t, f"{r.kalshi_event}-{r.home}", False),
                              r.away: C._own(t, f"{r.kalshi_event}-{r.away}", True)},
                      "kph": C._phome(t), "pm": C._phome(q), "kflow": _side_flow(t), "pflow": _side_flow(q)})
    f.write_bytes(pickle.dumps(games))
    return games


def week_map() -> dict:
    """ET week index of every training game (all 1,267 kalshi_only games, as costside)."""
    ko = pd.read_csv(C.DATA / "raw" / "kalshi_only_games.csv")
    wk = {r.game_id: pd.Timestamp(r.kickoff_utc_espn).tz_convert("America/New_York").tz_localize(None)
          .to_period("W-SUN").start_time for r in ko.itertuples()}
    idx = {w: i for i, w in enumerate(sorted(set(wk.values())))}
    return {g: idx[w] for g, w in wk.items()}


# ---------------- grid and statistics ----------------

def asof_grid(ts: np.ndarray, px: np.ndarray, grid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Backward as-of price and age at each grid time (nan before the first trade)."""
    i = np.searchsorted(ts, grid, side="right") - 1
    ok = i >= 0
    p = np.where(ok, px[np.maximum(i, 0)], np.nan)
    age = np.where(ok, grid - ts[np.maximum(i, 0)], np.iinfo(np.int64).max)
    return p, age


def flow_bins(ts: np.ndarray, fl: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """Signed flow in (grid[j-1], grid[j]] for j >= 1 (first bin 0)."""
    c = np.concatenate([[0.0], np.cumsum(fl)])
    i = np.searchsorted(ts, grid, side="right")
    s = c[i]
    return np.diff(s, prepend=s[0])


def xcorr_lag(a: np.ndarray, b: np.ndarray) -> tuple[int, float]:
    """Lag k (steps) maximizing corr(a[t - k], b[t]); k > 0 means a leads b."""
    best, bk = -np.inf, 0
    for k in range(-LAGS, LAGS + 1):
        if k >= 0:
            x, y = a[:len(a) - k] if k else a, b[k:]
        else:
            x, y = a[-k:], b[:len(b) + k]
        if len(x) < 10 or x.std() == 0 or y.std() == 0:
            continue
        c = np.corrcoef(x, y)[0, 1]
        if c > best:
            best, bk = c, k
    return bk, best


def vecm_shares(pm: np.ndarray, k: np.ndarray, p: int = 3) -> dict:
    """Bivariate VECM, beta = (1, -1) imposed. Returns polymarket.com Hasbrouck IS (both orderings, midpoint) and
    Gonzalo-Granger component share."""
    x = np.column_stack([pm, k])
    dx = np.diff(x, axis=0)
    z = (pm - k)[:-1]
    T = len(dx)
    if T <= p + 20:
        return {}
    Y = dx[p:]
    cols = [z[p:]]
    for i in range(1, p + 1):
        cols.append(dx[p - i:T - i, 0])
        cols.append(dx[p - i:T - i, 1])
    X = np.column_stack(cols + [np.ones(len(Y))])
    coef, *_ = np.linalg.lstsq(X, Y, rcond=None)
    res = Y - X @ coef
    om = np.cov(res.T)
    a_pm, a_k = coef[0, 0], coef[0, 1]
    den = a_k - a_pm
    if not np.isfinite(den) or abs(den) < 1e-12 or not np.all(np.isfinite(om)) or np.linalg.det(om) <= 0:
        return {}
    gg = float(np.clip(a_k / den, 0, 1))
    psi = np.array([a_k, -a_pm])
    out = {"gg_pm": gg, "alpha_pm": float(a_pm), "alpha_k": float(a_k)}
    shares = []
    for order in ([0, 1], [1, 0]):
        o = om[np.ix_(order, order)]
        F = np.linalg.cholesky(o)
        v = psi[order] @ F
        tot = float(psi @ om @ psi)
        if tot <= 0:
            return out
        s = (v ** 2) / tot
        shares.append(float(s[order.index(0)]))
    out.update(is_pm_hi=max(shares), is_pm_lo=min(shares), is_pm=float(np.mean(shares)))
    return out


def window_stats(g: dict, lo: int, hi: int) -> dict:
    grid = np.arange(lo, hi + 1, STEP, dtype=np.int64)
    kt, kp = g["kph"]
    pt, pp = g["pm"]
    if len(kt) == 0 or len(pt) == 0 or len(grid) < 50:
        return {}
    k, _ = asof_grid(kt, kp, grid)
    q, _ = asof_grid(pt, pp, grid)
    ok = np.isfinite(k) & np.isfinite(q)
    if ok.sum() < 50:
        return {}
    first = np.argmax(ok)
    k, q, grid = k[first:], q[first:], grid[first:]
    dk, dq = np.diff(k), np.diff(q)
    nk, nq = int((dk != 0).sum()), int((dq != 0).sum())
    out = {"n_k_changes": nk, "n_pm_changes": nq}
    if nk < MIN_CHANGES or nq < MIN_CHANGES:
        return out
    lag, c = xcorr_lag(dq, dk)
    out.update(lag_s=lag * 5, lag_corr=c)
    kf = flow_bins(*g["kflow"], grid)[1:]
    pf = flow_bins(*g["pflow"], grid)[1:]
    for kk in (0, 1, 2, 6, 12):
        if kk == 0:
            a1, b1, a2, b2 = pf, dk, kf, dq
        else:
            a1, b1, a2, b2 = pf[:-kk], dk[kk:], kf[:-kk], dq[kk:]
        out[f"pmflow_to_dk_{kk * 5}s"] = float(np.corrcoef(a1, b1)[0, 1]) if a1.std() > 0 and b1.std() > 0 else np.nan
        out[f"kflow_to_dpm_{kk * 5}s"] = float(np.corrcoef(a2, b2)[0, 1]) if a2.std() > 0 and b2.std() > 0 else np.nan
    out.update(vecm_shares(q, k))
    return out


# ---------------- trading ----------------

def gap_signals(g: dict, lo: int, hi: int, thr: float) -> list[tuple[int, int]]:
    grid = np.arange(lo, hi + 1, STEP, dtype=np.int64)
    kt, kp = g["kph"]
    pt, pp = g["pm"]
    if len(kt) == 0 or len(pt) == 0:
        return []
    k, ka = asof_grid(kt, kp, grid)
    q, qa = asof_grid(pt, pp, grid)
    gap = q - k
    ok = np.isfinite(gap) & (ka <= STALE) & (qa <= STALE) & (np.abs(gap) >= thr - 1e-9)
    return [(int(t), 1 if v > 0 else -1) for t, v in zip(grid[ok], gap[ok])]


def row(trial, g, team, t, entry, fee_e, fee_alt, payout, exit_px=None, extra=None):
    b = C.book_trade(entry, fee_e, payout=payout, exit_px=exit_px)
    ba = C.book_trade(entry, fee_alt, payout=payout, exit_px=exit_px)
    return {"trial": trial, "game_id": g["game_id"], "team": team, "t": t, "day": C.et_date(t), "entry": entry,
            "fee_entry": fee_e, "payout": payout if exit_px is None else np.nan, "exit": exit_px,
            "pnl": b["pnl"], "cap": b["cap"], "pnl_alt": ba["pnl"], "cap_alt": ba["cap"], **(extra or {})}


def run_game(g, sigs, trial, exec_mode, exit_h):
    rows, free = [], -1
    team_of = {1: g["home"], -1: g["away"]}
    for t, d in sigs:
        if t < free:
            continue
        team = team_of[d]
        ts, px = g["own"][team]
        pay = g["pay"][team]
        if exec_mode == "taker":
            f = C.taker_entry(ts, px, t, 60)
            fe, fa = C.fee_taker, C.fee_taker
        else:
            last = C.asof(ts, px, t)
            f = C.maker_entry(ts, px, t, last, 60) if last == last else None
            fe, fa = C.fee_maker175, C.fee_maker0
        if f is None:
            continue
        fill_ts, entry = f
        if exit_h is None:
            if pay == pay:
                rows.append(row(trial, g, team, t, entry, fe(entry), fa(entry), pay))
            break
        ex = C.exit_at(ts, px, fill_ts, exit_h)
        if ex is None:
            if pay == pay:
                rows.append(row(trial, g, team, t, entry, fe(entry), fa(entry), pay, extra={"held": True}))
            break
        rows.append(row(trial, g, team, t, entry, fe(entry), fa(entry), None, exit_px=ex[1], extra={"held": False}))
        free = ex[0]
    return rows


def registry() -> list[dict]:
    reg = []
    for gate in ("E", "W", "P"):
        for thr in (0.02, 0.04):
            for ex in ("taker", "maker"):
                for h in (300, None):
                    reg.append({"round": 1, "trial": f"LL2.R1.{gate}.g{int(thr * 100)}.{ex}.{'H300' if h else 'settle'}",
                                "method": {"E": "IS-gated gap, early-window IS >= 0.6",
                                           "W": "IS-gated gap, walk-forward league IS >= 0.6",
                                           "P": "placebo: early-window IS <= 0.4"}[gate],
                                "params": f"gate={gate} g={thr} exec={ex} exit={'300s' if h else 'settle'}",
                                "cost_line": "taker (alt taker)" if ex == "taker" else "maker175 (alt maker0)",
                                "gate": gate, "thr": thr, "exec": ex, "exit_h": h})
    return reg


def main() -> None:
    games = load_r1_games()
    wk = week_map()
    print(f"R1 games (B training set with polymarket.com ticks): {len(games)}", flush=True)
    desc = []
    for i, g in enumerate(games):
        ko = g["kickoff_ns"]
        rec = {"game_id": g["game_id"], "league": g["league"], "week": wk[g["game_id"]]}
        for name, lo, hi in (("ingame", ko + 20 * 60 * C.NS, ko + 4 * 3600 * C.NS),
                             ("pregame", ko - 2 * 3600 * C.NS, ko - 5 * 60 * C.NS),
                             ("early", ko + 20 * 60 * C.NS, ko + 80 * 60 * C.NS),
                             ("late", ko + 80 * 60 * C.NS, ko + 4 * 3600 * C.NS)):
            for kk, v in window_stats(g, lo, hi).items():
                rec[f"{name}_{kk}"] = v
        desc.append(rec)
        if i % 200 == 0:
            print(f"  desc {i}/{len(games)}", flush=True)
    D = pd.DataFrame(desc)
    C.OUT.mkdir(parents=True, exist_ok=True)
    D.to_csv(C.OUT / "r1_game_shares.csv", index=False)      # per-game lags and shares only, no prices

    # walk-forward league IS (past weeks only, full in-game window)
    wf = {}
    for g in games:
        w = wk[g["game_id"]]
        past = D[(D.week < w) & (D.league == g["league"])]["ingame_is_pm"].dropna()
        wf[g["game_id"]] = float(past.mean()) if len(past) >= 10 else np.nan
    D["wf_league_is"] = D.game_id.map(wf)
    D.to_csv(C.OUT / "r1_game_shares.csv", index=False)

    rows = []
    for r in registry():
        for g in games:
            if wk[g["game_id"]] < C.HIST_WEEKS:
                continue
            d = D[D.game_id == g["game_id"]].iloc[0]
            if r["gate"] == "E":
                ok = d.get("early_is_pm", np.nan) >= 0.6
            elif r["gate"] == "W":
                ok = wf[g["game_id"]] >= 0.6
            else:
                ok = d.get("early_is_pm", np.nan) <= 0.4
            if not ok:
                continue
            ko = g["kickoff_ns"]
            sigs = gap_signals(g, ko + 80 * 60 * C.NS, ko + 4 * 3600 * C.NS, r["thr"])
            rows += run_game(g, sigs, r["trial"], r["exec"], r["exit_h"])
    T = pd.DataFrame(rows)
    T.to_parquet(C.CACHE / "trades_round1.parquet", index=False)
    pd.DataFrame(registry()).drop(columns=["gate", "thr", "exec", "exit_h"]).to_csv(C.CACHE / "registry_round1.csv",
                                                                                   index=False)
    print(f"R1 trades: {len(T)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
