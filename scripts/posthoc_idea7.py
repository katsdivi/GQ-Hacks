"""Post-hoc Idea 7: cross-venue consensus at kickoff - 5 min, buy the Kalshi team polymarket.com rates higher.

post-hoc, exploratory; selected on training only.

Rule and implementation notes: results/posthoc_idea7/SPEC.md (committed before any real-data run).
Structure follows scripts/posthoc_idea4.py on branch posthoc-idea4 (Decimal money, strategy_a fees, metrics).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea7.py              training only (kickoff < 2026-08-01)
  (holdout: not wired; only on "run idea7 holdout")
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import skew

import strategy_a as A

LABEL = "post-hoc, exploratory; selected on training only"
ROOT = Path("/Users/divyamkataria/GQ HACKS/staleline")
TICKS = ROOT / "data" / "ticks"
META = ROOT / "data" / "raw" / "kalshi_market_meta.csv"
B_GAMES = ROOT / "out" / "strategy_b" / "b_games_espn.csv"
A_ROWS = ROOT / "out" / "strategy_a" / "rows.parquet"
A_THETA = 0.80
OUT = Path("results/posthoc_idea7")
NS = 1_000_000_000
KS = (0.02, 0.03, 0.05)
QTY = 10
DEC_BEFORE_S = 5 * 60          # t = kickoff - 5 min
FRESH_S = 10 * 60              # both prices within 10 min before t
LATENCY_S = 1.0
FILL_WINDOW_S = 5 * 60
HALF = Decimal("0.01")
CAP = Decimal("0.99")
WEBULL = Decimal("0.02")
MIN_TRADES = 100
SEED, N_BOOT = 20261004, 2000
SEASON = ("2025-07-31", "2026-01-25")
SEAL = pd.Timestamp("2026-08-01", tz="UTC")
# run_strategy_b.EXCLUDED_A1 (v3 Amendment 1 section 3), copied verbatim
EXCLUDED_A1 = {"cfb_20251129_ore_wash", "cfb_20251129_cin_tcu", "cfb_20251129_hou_bay", "cfb_20251129_colo_ksu",
               "nfl_20251208_phi_lac", "nfl_20251225_det_min", "nfl_20251225_den_kc", "cfb_20250913_usc_pur",
               "cfb_20251129_ucla_usc", "cfb_20250913_fau_fiu", "cfb_20251018_txam_ark", "cfb_20250920_tem_gt",
               "cfb_20251018_utsa_unt", "cfb_20250913_ull_mizz"}


def D(x) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def fee_direct(p: Decimal) -> Decimal:
    return D(A.fee_kalshi_direct(float(p), QTY))


def fee_webull(p: Decimal) -> Decimal:
    return WEBULL * QTY


def orientation_flag(k_home: float, q_home: float) -> bool:
    """B orientation rule (0014b1e scripts/b_orientation_check.py), applied at this idea's decision time."""
    return abs(k_home - q_home) > 0.20 and abs(k_home - (1 - q_home)) < 0.05 and abs(k_home - 0.5) > 0.10


def own_series(kt: pd.DataFrame, ticker: str, is_away: bool) -> tuple[np.ndarray, np.ndarray]:
    """One Kalshi market's trades as that team's own YES price (stored price is P(home))."""
    t = kt[(kt["market_id"] == ticker) & (kt["kind"] == "trade")].sort_values("ts", kind="stable")
    px = t["price"].to_numpy(float)
    return t["ts"].to_numpy(np.int64), np.round(1.0 - px if is_away else px, 4)


def last_at_or_before(ts: np.ndarray, px: np.ndarray, t_ns: int) -> tuple[int, float] | None:
    i = np.searchsorted(ts, t_ns, side="right") - 1
    return (int(ts[i]), float(px[i])) if i >= 0 else None


def decide(g: dict, kt: pd.DataFrame, pt: pd.DataFrame) -> dict:
    """Prices at t (only rows with ts <= t). Returns gaps or a skip reason."""
    t_ns = g["kickoff"].value - DEC_BEFORE_S * NS
    lo = t_ns - FRESH_S * NS
    kh = last_at_or_before(*own_series(kt, g["home_ticker"], False), t_ns)
    ka = last_at_or_before(*own_series(kt, g["away_ticker"], True), t_ns)
    p = pt[pt["kind"] == "trade"].sort_values("ts", kind="stable")
    q = last_at_or_before(p["ts"].to_numpy(np.int64), np.round(p["price"].to_numpy(float), 4), t_ns)
    if any(x is None or x[0] < lo for x in (kh, ka, q)):
        return {"t_ns": t_ns, "skip": "stale or missing price"}
    q_home = q[1]
    g_home, g_away = q_home - kh[1], (1.0 - q_home) - ka[1]
    return {"t_ns": t_ns, "skip": "", "K_home": kh[1], "K_away": ka[1], "Q_home": q_home,
            "g_home": round(g_home, 4), "g_away": round(g_away, 4), "flagged": orientation_flag(kh[1], q_home)}


def leg(kt: pd.DataFrame, g: dict, team: str, t_ns: int) -> dict:
    ticker = g["home_ticker"] if team == "home" else g["away_ticker"]
    ts, px = own_series(kt, ticker, team == "away")
    lo, hi = t_ns + int(LATENCY_S * NS), t_ns + int(LATENCY_S * NS) + FILL_WINDOW_S * NS
    idx = np.flatnonzero((ts >= lo) & (ts <= hi))
    if len(idx) == 0:
        return {"entered": False, "skip": "no post-decision trade"}
    fill_ts, trade_px = int(ts[idx[0]]), D(px[idx[0]])
    fill = min(trade_px + HALF, CAP)
    payout = g["settle"].get(ticker)
    if payout is None or payout != payout:
        return {"entered": False, "skip": "void/unsettled", "fill_ts": fill_ts}
    payout = D(payout)
    out = {"entered": True, "skip": "", "ticker": ticker, "fill_ts": fill_ts, "trade_px": float(trade_px),
           "fill": float(fill), "capped": bool(trade_px + HALF >= CAP), "payout": float(payout)}
    for x2 in (False, True):
        p = min(fill + HALF, CAP) if x2 else fill
        k = 2 if x2 else 1
        sfx = "_x2" if x2 else ""
        for line, fn in (("direct", fee_direct), ("webull", fee_webull)):
            f = fn(p) * k
            net = (payout - p) * QTY - f
            out[f"fee_{line}{sfx}"] = float(f)
            out[f"pnl_{line}{sfx}"] = float(net)
            out[f"roc_{line}{sfx}"] = float(net / (p * QTY + f))
        out[f"fill{sfx}"] = float(p)
    return out


def evaluate_game(g: dict, kt: pd.DataFrame, pt: pd.DataFrame, ks=KS) -> list[dict]:
    if g["kickoff"] >= SEAL:
        raise ValueError(f"{g['game_id']}: kickoff on/after 2026-08-01 is sealed")
    base = {"game_id": g["game_id"], "league": g["league"]}
    d = decide(g, kt, pt)
    rows = []
    for k in ks:
        if d["skip"]:
            rows += [{**base, "k": k, "leg": lg, "entered": False, "skip": d["skip"]} for lg in ("signal", "placebo")]
            continue
        info = {kk: d[kk] for kk in ("t_ns", "K_home", "K_away", "Q_home", "g_home", "g_away", "flagged")}
        info["day"] = pd.Timestamp(d["t_ns"], unit="ns", tz="UTC").tz_convert("America/New_York").date().isoformat()
        hi_team = "home" if d["g_home"] >= d["g_away"] else "away"      # tie -> home
        lo_team = "home" if d["g_home"] <= d["g_away"] else "away"      # tie -> home
        for lg, team, ok in (("signal", hi_team, d[f"g_{hi_team}"] >= k - 1e-9),
                             ("placebo", lo_team, d[f"g_{lo_team}"] <= -k + 1e-9)):
            if not ok:
                rows.append({**base, "k": k, "leg": lg, "entered": False, "skip": "no signal", **info})
                continue
            rows.append({**base, "k": k, "leg": lg, "team": team, "g": d[f"g_{team}"], **info,
                         **leg(kt, g, team, d["t_ns"])})
    return rows


# ---------- metrics ----------

def boot_ci(x: np.ndarray) -> tuple[float, float]:
    if len(x) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(SEED)
    m = x[rng.integers(0, len(x), size=(N_BOOT, len(x)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def a_daily() -> pd.Series:
    r = pd.read_parquet(A_ROWS)
    e = r[(r["theta"] == A_THETA) & (~r["placebo"].astype(bool)) & r["entered"].astype(bool)]
    return e.groupby(e["date"].astype(str))["pnl_direct"].sum()


def metrics(e: pd.DataFrame, line: str, x2: bool, adaily: pd.Series | None) -> dict:
    s = "_x2" if x2 else ""
    pnl, roc, fill = (e[f"pnl_{line}{s}"].to_numpy(float), e[f"roc_{line}{s}"].to_numpy(float),
                      e[f"fill{s}"].to_numpy(float))
    n = len(e)
    out = {"trades": n, "wins": int((e["payout"] == 1.0).sum()), "losses": int((e["payout"] == 0.0).sum()),
           "ties": int(((e["payout"] > 0) & (e["payout"] < 1)).sum()), "capped": int(e["capped"].sum()) if n else 0}
    if n == 0:
        return out
    lo, hi = boot_ci(roc)
    daily = e.assign(_p=pnl).groupby("day")["_p"].sum().sort_index()
    first = min(pd.Timestamp(SEASON[0]), pd.Timestamp(daily.index.min()))
    last = max(pd.Timestamp(SEASON[1]), pd.Timestamp(daily.index.max()))
    days = pd.date_range(first, last, freq="D").strftime("%Y-%m-%d")
    full = daily.reindex(days, fill_value=0.0)
    sd_full = full.std(ddof=1)
    sd_d = daily.std(ddof=1) if len(daily) > 1 else float("nan")
    cum = np.concatenate([[0.0], daily.cumsum().to_numpy()])
    top5 = np.argsort(-pnl, kind="stable")[:5]
    keep = np.setdiff1d(np.arange(n), top5)
    corr = float("nan")
    if adaily is not None:
        idx = sorted(set(daily.index) | set(adaily.index))
        a, b = daily.reindex(idx, fill_value=0.0), adaily.reindex(idx, fill_value=0.0)
        corr = float(np.corrcoef(a, b)[0, 1]) if len(idx) > 2 else float("nan")
    out.update(mean_fill=float(fill.mean()), win_rate=float(e["payout"].mean()),
               win_minus_fill=float(e["payout"].mean() - fill.mean()), mean_g=float(e["g"].mean()),
               roc_mean=float(roc.mean()), roc_ci_lo=lo, roc_ci_hi=hi,
               cents_per_contract=float(pnl.sum() / (QTY * n) * 100), pnl_total=float(pnl.sum()),
               game_days=len(daily),
               sharpe_x365=float(full.mean() / sd_full * np.sqrt(365)) if sd_full > 0 else float("nan"),
               sharpe_daily=float(daily.mean() / sd_d) if sd_d == sd_d and sd_d > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()),
               skew_daily=float(skew(daily.to_numpy(), bias=False)) if len(daily) > 2 else float("nan"),
               worst_trade=float(pnl.min()), worst_day=float(daily.min()),
               excl_top5_trades=len(keep), excl_top5_roc=float(roc[keep].mean()) if len(keep) else float("nan"),
               excl_top5_pnl=float(pnl[keep].sum()), corr_with_A=corr)
    return out


SKIPS = ("stale or missing price", "no signal", "no post-decision trade", "void/unsettled")


def results_table(rows: pd.DataFrame, adaily: pd.Series | None) -> pd.DataFrame:
    out = []
    for k in KS:
        for lg in ("signal", "placebo"):
            r = rows[(rows["k"] == k) & (rows["leg"] == lg)]
            sk = r["skip"].fillna("").astype(str)
            skips = {"games": len(r), **{f"skip_{s.replace(' ', '_').replace('/', '_')}": int((sk == s).sum())
                                         for s in SKIPS}}
            ent = r[r["entered"].astype(bool)]
            for sample, e in (("all", ent), ("excl_flagged", ent[~ent["flagged"].astype(bool)])):
                for line in ("direct", "webull"):
                    for x2 in (False, True):
                        out.append({"label": LABEL, "sample": "training", "subset": sample, "k": k, "leg": lg,
                                    "fee_line": "kalshi_direct" if line == "direct" else "webull",
                                    "costs": "x2" if x2 else "x1", **skips,
                                    **metrics(e, line, x2, adaily)})
    return pd.DataFrame(out)


def select_k(tab: pd.DataFrame) -> float | None:
    s = tab[(tab["leg"] == "signal") & (tab["subset"] == "all") & (tab["fee_line"] == "kalshi_direct")
            & (tab["costs"] == "x1") & (tab["trades"] >= MIN_TRADES)]
    if s.empty:
        return None
    return float(s.sort_values(["roc_mean", "k"], ascending=[False, False]).iloc[0]["k"])


# ---------- loading ----------

def training_games() -> list[dict]:
    g = pd.read_csv(B_GAMES)
    t8 = pd.to_datetime(g["t8_kickoff"], utc=True)
    es = pd.to_datetime(g["espn_kickoff"], utc=True)
    covered = (t8 - pd.Timedelta(hours=2) <= es - pd.Timedelta(minutes=30)) & \
              (t8 + pd.Timedelta(hours=5) >= es + pd.Timedelta(hours=4.5))
    assert set(g.loc[~covered, "game_id"]) == EXCLUDED_A1, "coverage exclusions differ from Amendment 1 list"
    assert (es < SEAL).all(), "training only"
    m = pd.read_csv(META)
    m = m[m["status"] == "finalized"]
    settle = dict(zip(m["ticker"], m["settlement_value_dollars"].astype(float)))
    out = []
    for r, k in zip(g[covered].itertuples(), es[covered]):
        out.append({"game_id": r.game_id, "league": r.league, "kickoff": k, "home_ticker": r.kalshi_home_ticker,
                    "away_ticker": r.kalshi_away_ticker,
                    "settle": {t: settle.get(t) for t in (r.kalshi_home_ticker, r.kalshi_away_ticker)}})
    return out


def main() -> None:
    games = training_games()
    print(f"{LABEL}\nsample training: {len(games)} games", flush=True)
    rows = []
    for i, g in enumerate(games):
        kt = pd.read_parquet(TICKS / f"{g['game_id']}_kalshi.parquet")
        pt = pd.read_parquet(TICKS / f"{g['game_id']}_polymarket.parquet")
        rows += evaluate_game(g, kt, pt)
        if i % 200 == 0:
            print(f"  {i}/{len(games)}", flush=True)
    rows = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    tab = results_table(rows, a_daily())
    tab.to_csv(OUT / "training_results.csv", index=False)
    rows.assign(label=LABEL).to_csv(OUT / "training_trades.csv", index=False)   # per-trade, gitignored
    sel = select_k(tab)
    flagged = sorted(rows.loc[rows["flagged"].fillna(False).astype(bool), "game_id"].unique())
    pd.set_option("display.width", 300, "display.max_columns", 60)
    print(f"selected k (training rule): {sel}")
    print(f"orientation-flagged games at t: {len(flagged)} {flagged}")
    print(tab.round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
