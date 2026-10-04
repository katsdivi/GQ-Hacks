"""Post-hoc Idea 12: in-game Kalshi vs polymarket.com gap, Kalshi leg only, hold to settlement.

post-hoc, exploratory; selected on training only.

Rule and implementation notes: results/posthoc_idea12/SPEC.md (committed before any real-data run, ca72fb9).
Reuses: Strategy B's game set and the 14 Amendment 1 exclusions (run_strategy_b.py), strategy_b.venue_grid for the
0014b1e orientation check, strategy_a fee functions; metrics modelled on scripts/posthoc_idea4.py (posthoc-idea4).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea12.py              training only (kickoff < 2026-08-01)
  (holdout: not wired; only on "run idea12 holdout")
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import skew

import strategy_a as A
import strategy_b as B

LABEL = "post-hoc, exploratory; selected on training only"
ROOT = Path("/Users/divyamkataria/GQ HACKS/staleline")
DATA = ROOT / "data"
OUT = Path("results/posthoc_idea12")
NS = 1_000_000_000
KS = (0.03, 0.05, 0.08)
QTY = 10
WIN_LO_S, WIN_HI_S = 20 * 60, 4 * 3600
FRESH_S = 30
PERSIST_S = 10
LATENCY_S = 1.0
FILL_WINDOW_S = 60
HALF = Decimal("0.01")
CAP = Decimal("0.99")
WEBULL = Decimal("0.02")
MIN_TRADES = 100
EPS = 1e-9
SEED, N_BOOT = 20261004, 2000
SEASON = {"training": ("2025-07-31", "2026-01-25")}
EXCLUDED_A1 = {"cfb_20251129_ore_wash", "cfb_20251129_cin_tcu", "cfb_20251129_hou_bay", "cfb_20251129_colo_ksu",
               "nfl_20251208_phi_lac", "nfl_20251225_det_min", "nfl_20251225_den_kc", "cfb_20250913_usc_pur",
               "cfb_20251129_ucla_usc", "cfb_20250913_fau_fiu", "cfb_20251018_txam_ark", "cfb_20250920_tem_gt",
               "cfb_20251018_utsa_unt", "cfb_20250913_ull_mizz"}   # = run_strategy_b.EXCLUDED_A1
STALE_FILE = Path("results/holdout_diag/d_b_big_diff_games.csv")


def D(x) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def fee_direct(p: Decimal, qty: int = QTY) -> Decimal:
    return D(A.fee_kalshi_direct(float(p), qty))


def fee_webull(p: Decimal, qty: int = QTY) -> Decimal:
    return WEBULL * qty


# ---------- signal ----------

def team_state(k_ts, k_px, p_ts, p_px):
    """Step function of (valid, g) for one team. k_px / p_px are that team's own YES prices, ts sorted.
    Returns event times e (sorted) and arrays valid, g giving the state on [e_i, e_{i+1})."""
    ev = np.unique(np.concatenate([k_ts, p_ts, k_ts + FRESH_S * NS + 1, p_ts + FRESH_S * NS + 1]))
    ik = np.searchsorted(k_ts, ev, side="right") - 1
    ip = np.searchsorted(p_ts, ev, side="right") - 1
    ok = (ik >= 0) & (ip >= 0)
    kt = np.where(ok, k_ts[np.clip(ik, 0, None)], 0)
    pt = np.where(ok, p_ts[np.clip(ip, 0, None)], 0)
    valid = ok & (ev - kt <= FRESH_S * NS) & (ev - pt <= FRESH_S * NS)
    g = np.where(valid, p_px[np.clip(ip, 0, None)] - k_px[np.clip(ik, 0, None)], np.nan)
    return ev, valid, g


def first_signal(ev, valid, g, cand, k: float, sign: int):
    """First candidate time t where sign*g >= k now and continuously over [t - 10 s, t]. Uses state at or before t."""
    cond = valid & (sign * np.nan_to_num(g, nan=-9) >= k - EPS)
    # start time of the run of True containing each event
    start = np.empty(len(ev), dtype=np.int64)
    s = None
    for i in range(len(ev)):
        if cond[i]:
            s = ev[i] if s is None else s
            start[i] = s
        else:
            s = None
            start[i] = np.iinfo(np.int64).max
    i = np.searchsorted(ev, cand, side="right") - 1
    has = i >= 0
    ii = np.clip(i, 0, None)
    hit = has & cond[ii] & (start[ii] <= cand - PERSIST_S * NS)
    idx = np.flatnonzero(hit)
    if len(idx) == 0:
        return None
    j = idx[0]
    return int(cand[j]), float(g[ii[j]])


def decide(kt: pd.DataFrame, pt: pd.DataFrame, home_mkt: str, away_mkt: str, ko_ns: int, k: float, sign: int):
    """sign=+1: signal (g >= k); sign=-1: placebo (g <= -k). Returns {t_ns, team ('home'/'away'), g} or None."""
    kt = kt[(kt["kind"] == "trade")].sort_values("ts", kind="stable")
    pt = pt[(pt["kind"] == "trade")].sort_values("ts", kind="stable")
    lo, hi = ko_ns + WIN_LO_S * NS, ko_ns + WIN_HI_S * NS
    h = kt[kt["market_id"] == home_mkt]
    a = kt[kt["market_id"] == away_mkt]
    p_ts, p_ph = pt["ts"].to_numpy(np.int64), pt["price"].to_numpy(float)
    allts = np.concatenate([kt["ts"].to_numpy(np.int64), p_ts])
    cand = np.unique(allts[(allts >= lo) & (allts <= hi)])
    best = None
    for order, (team, tr, own_p) in enumerate((("home", h, p_ph), ("away", a, 1.0 - p_ph))):
        k_ts = tr["ts"].to_numpy(np.int64)
        k_px = tr["price"].to_numpy(float) if team == "home" else 1.0 - tr["price"].to_numpy(float)
        if len(k_ts) == 0 or len(p_ts) == 0 or len(cand) == 0:
            continue
        ev, valid, g = team_state(k_ts, np.round(k_px, 4), p_ts, np.round(own_p, 6))
        r = first_signal(ev, valid, g, cand, k, sign)
        if r is None:
            continue
        c = (r[0], -abs(r[1]), order, team, r[1])
        if best is None or c[:3] < best[:3]:
            best = c
    if best is None:
        return None
    return {"t_ns": best[0], "team": best[3], "g": best[4]}


# ---------- fill and settle ----------

def leg(kt: pd.DataFrame, mkt: str, is_home: bool, t_ns: int, payout) -> dict:
    tr = kt[(kt["kind"] == "trade") & (kt["market_id"] == mkt)].sort_values("ts", kind="stable")
    ts = tr["ts"].to_numpy(np.int64)
    px = tr["price"].to_numpy(float) if is_home else 1.0 - tr["price"].to_numpy(float)
    i = int(np.searchsorted(ts, t_ns + int(LATENCY_S * NS), side="left"))
    if i >= len(ts) or ts[i] > t_ns + FILL_WINDOW_S * NS:
        return {"entered": False, "skip": "no post-decision trade"}
    fill = min(D(px[i]) + HALF, CAP)
    if fill >= CAP:
        return {"entered": False, "skip": "fill at 0.99", "fill_ts": int(ts[i])}
    if payout is None:
        return {"entered": False, "skip": "void/unsettled", "fill_ts": int(ts[i])}
    payout = D(payout)
    out = {"entered": True, "skip": "", "fill_ts": int(ts[i]), "trade_px": float(D(px[i])), "payout": float(payout)}
    for x2 in (False, True):
        p = min(fill + HALF, CAP) if x2 else fill
        kf = 2 if x2 else 1
        sfx = "_x2" if x2 else ""
        for line, fn in (("direct", fee_direct), ("webull", fee_webull)):
            f = fn(p) * kf
            net = (payout - p) * QTY - f
            out[f"fee_{line}{sfx}"] = float(f)
            out[f"pnl_{line}{sfx}"] = float(net)
            out[f"roc_{line}{sfx}"] = float(net / (p * QTY + f))
        out[f"fill{sfx}"] = float(p)
    return out


def orientation_flag(kt, pt, t_ns: int) -> bool:
    """0014b1e rule at the (single) entry decision, Strategy B grid prices, label floor(t) - 1 s."""
    g = t_ns // NS - 1
    kp, _ = B.venue_grid(kt, "kalshi", g, g)
    pp, _ = B.venue_grid(pt, "polymarket", g, g)
    K, PM = float(kp[0]), float(pp[0])
    if np.isnan(K) or np.isnan(PM):
        return False
    return abs(K - PM) > 0.20 and abs(K - (1 - PM)) < 0.05 and abs(K - 0.5) > 0.10


def evaluate_game(gid, ko, kt, pt, home_mkt, away_mkt, settle: dict, final_test=False) -> list[dict]:
    if pd.Timestamp(ko) >= A.SEAL and not final_test:
        raise ValueError(f"{gid}: kickoff on/after 2026-08-01 is sealed (needs 'run idea12 holdout')")
    ko_ns = pd.Timestamp(ko).value
    base = {"game_id": gid}
    present = set(kt.loc[kt["kind"] == "trade", "market_id"].unique())
    rows = []
    for k in KS:
        for lg, sign in (("signal", 1), ("placebo", -1)):
            if home_mkt not in present or away_mkt not in present or pt.empty:
                rows.append({**base, "k": k, "leg": lg, "entered": False, "skip": "missing market"})
                continue
            d = decide(kt, pt, home_mkt, away_mkt, ko_ns, k, sign)
            if d is None:
                rows.append({**base, "k": k, "leg": lg, "entered": False, "skip": "no signal"})
                continue
            is_home = d["team"] == "home"
            mkt = home_mkt if is_home else away_mkt
            day = pd.Timestamp(d["t_ns"], unit="ns", tz="UTC").tz_convert("America/New_York").date().isoformat()
            r = leg(kt, mkt, is_home, d["t_ns"], settle.get(mkt))
            rows.append({**base, "k": k, "leg": lg, "t_ns": d["t_ns"], "team": d["team"], "market": mkt,
                         "g": d["g"], "day": day, "flagged": orientation_flag(kt, pt, d["t_ns"]), **r})
    return rows


# ---------- metrics (as posthoc_idea4.metrics, plus mean g) ----------

def boot_ci(x: np.ndarray) -> tuple[float, float]:
    if len(x) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(SEED)
    m = x[rng.integers(0, len(x), size=(N_BOOT, len(x)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def metrics(e: pd.DataFrame, line: str, x2: bool, season) -> dict:
    s = "_x2" if x2 else ""
    pnl, roc, fill = (e[f"pnl_{line}{s}"].to_numpy(float), e[f"roc_{line}{s}"].to_numpy(float),
                      e[f"fill{s}"].to_numpy(float))
    n = len(e)
    out = {"trades": n, "wins": int((e["payout"] == 1.0).sum()), "losses": int((e["payout"] == 0.0).sum())}
    if n == 0:
        return out
    lo, hi = boot_ci(roc)
    daily = e.assign(_p=pnl).groupby("day")["_p"].sum().sort_index()
    first = min(pd.Timestamp(season[0]), pd.Timestamp(daily.index.min()))
    last = max(pd.Timestamp(season[1]), pd.Timestamp(daily.index.max()))
    full = daily.reindex(pd.date_range(first, last, freq="D").strftime("%Y-%m-%d"), fill_value=0.0)
    sd_full = full.std(ddof=1)
    sd_d = daily.std(ddof=1) if len(daily) > 1 else float("nan")
    cum = np.concatenate([[0.0], daily.cumsum().to_numpy()])
    top5 = np.argsort(-pnl, kind="stable")[:5]
    keep = np.setdiff1d(np.arange(n), top5)
    out.update(mean_fill=float(fill.mean()), win_rate=float(e["payout"].mean()), mean_g=float(e["g"].mean()),
               roc_mean=float(roc.mean()), roc_ci_lo=lo, roc_ci_hi=hi,
               cents_per_contract=float(pnl.sum() / (QTY * n) * 100), pnl_total=float(pnl.sum()),
               game_days=len(daily),
               sharpe_x365=float(full.mean() / sd_full * np.sqrt(365)) if sd_full > 0 else float("nan"),
               sharpe_daily=float(daily.mean() / sd_d) if sd_d == sd_d and sd_d > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()),
               skew_daily=float(skew(daily.to_numpy(), bias=False)) if len(daily) > 2 else float("nan"),
               worst_trade=float(pnl.min()), worst_day=float(daily.min()),
               excl_top5_roc=float(roc[keep].mean()) if len(keep) else float("nan"),
               excl_top5_pnl=float(pnl[keep].sum()))
    return out


def results_table(rows: pd.DataFrame, sample: str, stale: set) -> pd.DataFrame:
    out = []
    for k in KS:
        for lg in ("signal", "placebo"):
            r = rows[(rows["k"] == k) & (rows["leg"] == lg)]
            ent = r["entered"].fillna(False).astype(bool)
            sk = r["skip"].fillna("").astype(str)
            skips = {"games": len(r)} | {f"skip_{x.replace(' ', '_').replace('/', '_')}": int((sk == x).sum())
                                         for x in ("no signal", "no post-decision trade", "fill at 0.99",
                                                   "void/unsettled", "missing market")}
            e_all = r[ent]
            subsets = {"all": e_all, "excl_stale12": e_all[~e_all["game_id"].isin(stale)],
                       "excl_flagged": e_all[~e_all["flagged"].fillna(False).astype(bool)]}
            for subset, e in subsets.items():
                for line in ("direct", "webull"):
                    for x2 in (False, True):
                        out.append({"label": LABEL, "sample": sample, "k": k, "leg": lg, "subset": subset,
                                    "fee_line": "kalshi_direct" if line == "direct" else "webull",
                                    "costs": "x2" if x2 else "x1", **skips,
                                    "flagged_games": int(e_all["flagged"].fillna(False).astype(bool).sum()),
                                    **metrics(e, line, x2, SEASON[sample])})
    return pd.DataFrame(out)


def select_k(tab: pd.DataFrame):
    s = tab[(tab["leg"] == "signal") & (tab["subset"] == "all") & (tab["fee_line"] == "kalshi_direct")
            & (tab["costs"] == "x1") & (tab["trades"] >= MIN_TRADES)]
    if s.empty:
        return None
    return float(s.sort_values(["roc_mean", "k"], ascending=[False, False]).iloc[0]["k"])


# ---------- loading ----------

def training_games() -> pd.DataFrame:
    g = pd.read_csv(ROOT / "out/strategy_b/b_games_espn.csv")
    t8 = pd.to_datetime(g["t8_kickoff"], utc=True)
    es = pd.to_datetime(g["espn_kickoff"], utc=True)
    cov = (t8 - pd.Timedelta(hours=2) <= es - pd.Timedelta(minutes=30)) & \
          (t8 + pd.Timedelta(hours=5) >= es + pd.Timedelta(hours=4.5))
    assert set(g.loc[~cov, "game_id"]) == EXCLUDED_A1, "coverage exclusions differ from Amendment 1 list"
    assert (es < A.SEAL).all(), "training only"
    return g[cov].reset_index(drop=True)


def settlements() -> dict:
    out = {}
    for f in ("kalshi_kxnflgame_historical.parquet", "kalshi_kxncaafgame_historical.parquet"):
        d = pd.read_parquet(DATA / "raw" / f, columns=["ticker", "status", "result", "settlement_value_dollars"])
        for r in d.itertuples():
            v = pd.to_numeric(r.settlement_value_dollars, errors="coerce")
            if r.status in ("finalized", "settled") and v == v and r.result in ("yes", "no", "scalar"):
                out[r.ticker] = float(v)
    return out


def stale_games() -> set:
    f = STALE_FILE
    d = pd.read_csv(f)
    return set(d.loc[d["class"] == "stale venue (polymarket)", "game_id"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    g = training_games()
    settle, stale = settlements(), stale_games()
    print(f"{LABEL}\nsample training: {len(g)} games; stale list {len(stale)} ids "
          f"({len(stale & set(g['game_id']))} in sample)", flush=True)
    rows = []
    for i, r in enumerate(g.itertuples()):
        kt = pd.read_parquet(DATA / "ticks" / f"{r.game_id}_kalshi.parquet")
        pt = pd.read_parquet(DATA / "ticks" / f"{r.game_id}_polymarket.parquet")
        rows += evaluate_game(r.game_id, r.espn_kickoff, kt, pt, r.kalshi_home_ticker, r.kalshi_away_ticker, settle)
        if i % 100 == 0:
            print(f"  {i}/{len(g)}", flush=True)
    rows = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    tab = results_table(rows, "training", stale)
    tab.to_csv(OUT / "training_results.csv", index=False)
    rows.assign(label=LABEL).to_csv(OUT / "training_trades.csv", index=False)   # per-trade, gitignored
    sel = select_k(tab)
    print(f"selected k (training rule): {sel}")
    pd.set_option("display.width", 300, "display.max_columns", 60)
    v = tab[(tab["subset"] == "all") & (tab["fee_line"] == "kalshi_direct") & (tab["costs"] == "x1")]
    print(v.round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
