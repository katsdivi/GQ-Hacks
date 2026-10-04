"""Post-hoc cost-side search: shared data loading, execution, metrics and multiple-testing code.

post-hoc, exploratory; training only (kickoff before 2026-08-01). See results/posthoc_costside/SPEC.md.
"""
from __future__ import annotations

import pickle
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
OUTB = Path("/Users/divyamkataria/GQ HACKS/staleline/out/strategy_b")
CACHE = Path("data/costside_cache")
OUT = Path("results/posthoc_costside")
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
NS = 1_000_000_000
QTY = 10
SEED, NBOOT = 20261004, 2000
HIST_WEEKS = 6
EXCLUDED_A1 = {"cfb_20251129_ore_wash", "cfb_20251129_cin_tcu", "cfb_20251129_hou_bay", "cfb_20251129_colo_ksu",
               "nfl_20251208_phi_lac", "nfl_20251225_det_min", "nfl_20251225_den_kc", "cfb_20250913_usc_pur",
               "cfb_20251129_ucla_usc", "cfb_20250913_fau_fiu", "cfb_20251018_txam_ark", "cfb_20250920_tem_gt",
               "cfb_20251018_utsa_unt", "cfb_20250913_ull_mizz"}   # run_strategy_b.EXCLUDED_A1


# ---------------- fees ----------------

def _fee(rate: str, p: float, qty: int = QTY) -> float:
    p = Decimal(str(round(float(p), 4)))
    raw = Decimal(rate) * Decimal(qty) * p * (1 - p)
    return float(raw.quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def fee_taker(p: float, qty: int = QTY) -> float:
    return _fee("0.07", p, qty)


def fee_maker175(p: float, qty: int = QTY) -> float:
    return _fee("0.0175", p, qty)


def fee_maker0(p: float, qty: int = QTY) -> float:
    return 0.0


# ---------------- data ----------------

def _settle_map() -> dict:
    m = pd.read_csv(DATA / "raw" / "kalshi_market_meta.csv")
    out = {}
    for r in m.itertuples():
        v = r.settlement_value_dollars if r.status in ("finalized", "settled") else np.nan
        out[(r.game_id, r.side)] = float(v) if v == v else np.nan
    return out


def _own(t: pd.DataFrame, ticker: str, away: bool) -> tuple[np.ndarray, np.ndarray]:
    x = t[(t["market_id"] == ticker) & (t["kind"] == "trade")].sort_values("ts", kind="stable")
    px = x["price"].to_numpy(float)
    return x["ts"].to_numpy(np.int64), np.round(1 - px if away else px, 4)


def _phome(t: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    x = t[t["kind"] == "trade"].sort_values("ts", kind="stable")
    return x["ts"].to_numpy(np.int64), np.round(x["price"].to_numpy(float), 4)


def load_games() -> list[dict]:
    """Every training game once: own-market trades per team, Kalshi P(home) series, polymarket.com series (B set)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / "games.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    sett = _settle_map()
    ko = pd.read_csv(DATA / "raw" / "kalshi_only_games.csv")
    b = pd.read_csv(OUTB / "b_games_espn.csv")
    b = b[~b["game_id"].isin(EXCLUDED_A1)]
    bset = set(b["game_id"])
    games = []
    for r in ko.itertuples():
        k = pd.Timestamp(r.kickoff_utc_espn)
        assert k < SEAL, "training only"
        p = DATA / "raw" / "kalshi_only" / f"{r.game_id}.parquet"
        if not p.exists():
            continue
        t = pd.read_parquet(p, columns=["ts", "market_id", "kind", "price"])
        g = {"game_id": r.game_id, "league": r.league, "home": r.home, "away": r.away, "kickoff_ns": k.value,
             "pay": {r.home: sett.get((r.game_id, "home"), np.nan), r.away: sett.get((r.game_id, "away"), np.nan)},
             "own": {r.home: _own(t, f"{r.kalshi_event}-{r.home}", False),
                     r.away: _own(t, f"{r.kalshi_event}-{r.away}", True)},
             "kph": _phome(t), "bset": r.game_id in bset, "pm": None}
        if g["bset"]:
            pp = DATA / "ticks" / f"{r.game_id}_polymarket.parquet"
            if pp.exists():
                g["pm"] = _phome(pd.read_parquet(pp, columns=["ts", "kind", "price"]))
        games.append(g)
    f.write_bytes(pickle.dumps(games))
    return games


def et_date(ns: int) -> str:
    return pd.Timestamp(ns, unit="ns", tz="UTC").tz_convert("America/New_York").strftime("%Y-%m-%d")


def week_index(games: list[dict]) -> tuple[dict, int]:
    """ET week (Monday start) of each game's kickoff -> index; first HIST_WEEKS weeks are history only."""
    wk = {g["game_id"]: pd.Timestamp(g["kickoff_ns"], unit="ns", tz="UTC").tz_convert("America/New_York")
          .tz_localize(None).to_period("W-SUN").start_time for g in games}
    weeks = sorted(set(wk.values()))
    idx = {w: i for i, w in enumerate(weeks)}
    return {gid: idx[w] for gid, w in wk.items()}, HIST_WEEKS


# ---------------- execution ----------------

def asof(ts: np.ndarray, px: np.ndarray, t: int) -> float:
    i = np.searchsorted(ts, t, side="right") - 1
    return float(px[i]) if i >= 0 else np.nan


def taker_entry(ts, px, t: int, win_s: float = 60.0):
    """First own trade at or after t + 1 s within win_s: fill = trade + 1 c, cap 0.99; skip at 0.99."""
    lo = t + NS
    i = np.searchsorted(ts, lo, side="left")
    if i >= len(ts) or ts[i] > t + int(win_s * NS):
        return None
    f = min(round(px[i] + 0.01, 4), 0.99)
    if f >= 0.99:
        return None
    return int(ts[i]), f


def maker_entry(ts, px, t: int, limit: float, w_s: float):
    """Filled at limit only if an own trade prints <= limit - 0.01 with ts in (t + 1 s, t + w_s]."""
    if not (0.01 <= limit <= 0.98):
        return None
    lo, hi = t + NS, t + int(w_s * NS)
    i = np.searchsorted(ts, lo, side="right")
    j = np.searchsorted(ts, hi, side="right")
    hit = np.flatnonzero(px[i:j] <= limit - 0.01 + 1e-9)
    if len(hit) == 0:
        return None
    return int(ts[i + hit[0]]), round(limit, 4)


def exit_at(ts, px, fill_ts: int, h_s: float):
    """Sell at first own trade at or after fill_ts + H, price trade - 1 c (floor 0.01); None if none within 120 s."""
    lo = fill_ts + int(h_s * NS)
    i = np.searchsorted(ts, lo, side="left")
    if i >= len(ts) or ts[i] > lo + 120 * NS:
        return None
    return int(ts[i]), max(round(px[i] - 0.01, 4), 0.01)


def book_trade(entry_px: float, entry_fee: float, payout: float | None = None, exit_px: float | None = None) -> dict:
    """Net P&L of 10 contracts; exit_px given -> sold (taker fee on exit), else held to payout."""
    if exit_px is not None:
        fx = fee_taker(exit_px)
        pnl = (exit_px - entry_px) * QTY - entry_fee - fx
    else:
        pnl = (payout - entry_px) * QTY - entry_fee
    return {"pnl": round(pnl, 6), "cap": entry_px * QTY + entry_fee}


# ---------------- metrics ----------------

def roc_ci(df: pd.DataFrame) -> tuple[float, float, float]:
    """ROC = sum pnl / sum capital, game-level bootstrap."""
    if df.empty:
        return np.nan, np.nan, np.nan
    gsum = df.groupby("game_id")[["pnl", "cap"]].sum()
    p, c = gsum["pnl"].to_numpy(), gsum["cap"].to_numpy()
    roc = p.sum() / c.sum()
    if len(p) < 2:
        return roc, np.nan, np.nan
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(p), size=(NBOOT, len(p)))
    bs = p[idx].sum(1) / c[idx].sum(1)
    return float(roc), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def metrics(df: pd.DataFrame) -> dict:
    out = {"trades": len(df), "games": df["game_id"].nunique() if len(df) else 0}
    if df.empty:
        return out
    roc, lo, hi = roc_ci(df)
    daily = df.groupby("day")["pnl"].sum().sort_index()
    sd = daily.std(ddof=1) if len(daily) > 1 else np.nan
    cum = np.concatenate([[0.0], daily.cumsum().to_numpy()])
    gp = df.groupby("game_id")["pnl"].sum().sort_values(ascending=False)
    keep = df[~df["game_id"].isin(gp.index[:5])]
    out.update(roc=roc, roc_lo=lo, roc_hi=hi, pnl=float(df["pnl"].sum()),
               c_per_contract=float(df["pnl"].sum() / (QTY * len(df)) * 100),
               sharpe_daily=float(daily.mean() / sd) if sd and sd > 0 else np.nan,
               sharpe_x365=float(daily.mean() / sd * np.sqrt(365)) if sd and sd > 0 else np.nan,
               max_dd=float((np.maximum.accumulate(cum) - cum).max()),
               excl5_pnl=float(keep["pnl"].sum()),
               excl5_roc=float(keep["pnl"].sum() / keep["cap"].sum()) if len(keep) else np.nan,
               game_days=len(daily))
    if "payout" in df and df["payout"].notna().any():
        h = df[df["payout"].notna()]
        out.update(win_rate=float(h["payout"].mean()), breakeven=float((h["entry"] + h["fee_entry"] / QTY).mean()))
    return out


def multiple_testing(series: dict[str, pd.Series], seed: int = SEED, nboot: int = NBOOT, block: float = 5.0) -> dict:
    """Studentized White Reality Check (stationary bootstrap), Holm and DSR over trials' daily P&L series."""
    names = list(series)
    days = sorted(set().union(*[set(s.index) for s in series.values()])) if series else []
    X = np.column_stack([series[n].reindex(days, fill_value=0.0).to_numpy(float) for n in names]) if names else None
    if X is None or len(days) < 3:
        return {}
    T, K = X.shape
    mu, sd = X.mean(0), X.std(0, ddof=1)
    ok = sd > 0
    tstat = np.where(ok, mu / np.where(ok, sd, 1) * np.sqrt(T), -np.inf)
    best = int(np.argmax(tstat))
    rng = np.random.default_rng(seed)
    p = 1.0 / block
    bmax = np.empty(nboot)
    for b in range(nboot):
        idx = np.empty(T, dtype=int)
        idx[0] = rng.integers(T)
        jump = rng.random(T) < p
        newstart = rng.integers(0, T, size=T)
        for t in range(1, T):
            idx[t] = newstart[t] if jump[t] else (idx[t - 1] + 1) % T
        Xb = X[idx]
        tb = np.where(ok, (Xb.mean(0) - mu) / np.where(ok, sd, 1) * np.sqrt(T), -np.inf)
        bmax[b] = tb.max()
    rc_p = float((bmax >= tstat[best]).mean())
    pv = np.where(ok, 1 - stats.t.cdf(tstat, T - 1), 1.0)
    order = np.argsort(pv)
    holm = np.empty(K)
    run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (K - r) * pv[i]))
        holm[i] = run
    sr = np.where(ok, mu / np.where(ok, sd, 1), np.nan)
    srb = sr[best]
    var_sr = np.nanvar(sr, ddof=1) if np.isfinite(sr).sum() > 1 else 0.0
    g = 0.5772156649
    n_eff = max(int(np.isfinite(sr).sum()), 2)
    sr0 = np.sqrt(var_sr) * ((1 - g) * stats.norm.ppf(1 - 1 / n_eff) + g * stats.norm.ppf(1 - 1 / (n_eff * np.e)))
    xb = X[:, best]
    sk, ku = stats.skew(xb), stats.kurtosis(xb, fisher=False)
    den = np.sqrt(max(1 - sk * srb + (ku - 1) / 4 * srb ** 2, 1e-12))
    dsr = float(stats.norm.cdf((srb - sr0) * np.sqrt(T - 1) / den))
    return {"days": T, "trials": K, "best_by_t": names[best], "best_t": float(tstat[best]), "rc_p": rc_p,
            "dsr_best": dsr, "sr_best_daily": float(srb), "sr0": float(sr0),
            "holm": dict(zip(names, holm.tolist())), "raw_p": dict(zip(names, pv.tolist()))}
