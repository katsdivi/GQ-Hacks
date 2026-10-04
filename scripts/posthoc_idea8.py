"""Post-hoc Idea 8: taker-flow fade before kickoff.

post-hoc, exploratory; selected on training only.

Rule and implementation notes: results/posthoc_idea8/SPEC.md (committed before any real-data run).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea8.py              training only (kickoff < 2026-08-01)
  python scripts/posthoc_idea8.py --holdout    the v3 A4 holdout A set, ONCE, only on "run idea8 holdout"
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import skew

import strategy_a as A

LABEL = "post-hoc, exploratory; selected on training only"
DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
A_ROWS = Path("/Users/divyamkataria/GQ HACKS/staleline/out/strategy_a/rows.parquet")
A_THETA = 0.80
OUT = Path("results/posthoc_idea8")
NS = 1_000_000_000
XS = (0.2, 0.4, 0.6)
QTY = 10
W_LO_S, W_HI_S = 35 * 60, 5 * 60          # W = [kickoff - 35 min, kickoff - 5 min); t = kickoff - 5 min
MIN_V = 500
LATENCY_S = 1.0
FILL_WINDOW_S = 300
HALF = Decimal("0.01")
CAP = Decimal("0.99")
WEBULL = Decimal("0.02")
MIN_TRADES = 100
SEED, N_BOOT = 20261004, 2000
SEASON = {"training": ("2025-07-31", "2026-01-25"), "holdout": ("2026-08-06", "2026-10-04")}
AB_CUTOFF = pd.Timestamp("2026-10-03 20:00", tz="America/New_York")


def D(x) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def fee_direct(p: Decimal, qty: int = QTY) -> Decimal:
    return D(A.fee_kalshi_direct(float(p), qty))


def fee_webull(p: Decimal, qty: int = QTY) -> Decimal:
    return WEBULL * qty


# ---------- signal ----------

def pressure(trades: pd.DataFrame, g: A.Game) -> tuple[float, float]:
    """(P_h, V) from trades in W on both team markets. Stored side is in P(home) terms (ingest/kalshi.py:152-155):
    home buy = taker YES, home sell = taker NO, away buy = taker NO, away sell = taker YES, so +size for buy and
    -size for sell on either market is exactly the spec's P_h."""
    ko = g.kickoff.value
    lo, hi = ko - W_LO_S * NS, ko - W_HI_S * NS
    mk = {f"{g.event}-{g.home}", f"{g.event}-{g.away}"}
    w = trades[(trades["kind"] == "trade") & trades["market_id"].isin(mk) & (trades["ts"] >= lo) & (trades["ts"] < hi)]
    sgn = np.where(w["side"] == "buy", 1.0, np.where(w["side"] == "sell", -1.0, 0.0))
    size = w["size"].to_numpy(float)
    return float((sgn * size).sum()), float(size.sum())


def pressure_raw(raw: pd.DataFrame, g: A.Game) -> float:
    """Spec formula from raw taker sides (columns market_id, taker_side yes/no, size, ts); for tests."""
    ko = g.kickoff.value
    w = raw[(raw["ts"] >= ko - W_LO_S * NS) & (raw["ts"] < ko - W_HI_S * NS)]
    h, a = w[w["market_id"] == f"{g.event}-{g.home}"], w[w["market_id"] == f"{g.event}-{g.away}"]
    s = lambda d, side: float(d.loc[d["taker_side"] == side, "size"].sum())
    return (s(h, "yes") - s(h, "no")) + (s(a, "no") - s(a, "yes"))


def leg(trades: pd.DataFrame, g: A.Game, team: str, t_ns: int) -> dict:
    t = A.own_market_trades(trades, g, team)
    ts, px = t["ts"].to_numpy(np.int64), np.round(t["price"].to_numpy(float), 4)
    lo = t_ns + int(LATENCY_S * NS)
    idx = np.flatnonzero((ts >= lo) & (ts <= lo + FILL_WINDOW_S * NS))
    if len(idx) == 0:
        return {"team": team, "entered": False, "skip": "no post-decision trade"}
    fill_ts, trade_px = int(ts[idx[0]]), D(px[idx[0]])
    fill = min(trade_px + HALF, CAP)
    if fill >= CAP:
        return {"team": team, "entered": False, "skip": "fill at 0.99", "fill_ts": fill_ts}
    if g.result != g.result:
        return {"team": team, "entered": False, "skip": "unsettled", "fill_ts": fill_ts}
    payout = D(g.result) if team == g.home else Decimal(1) - D(g.result)
    out = {"team": team, "entered": True, "skip": "", "fill_ts": fill_ts, "trade_px": float(trade_px),
           "payout": float(payout)}
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


def exclusion(trades: pd.DataFrame, g: A.Game, final_test: bool) -> str:
    if g.kickoff >= A.SEAL and not final_test:
        raise ValueError(f"{g.game_id}: kickoff on/after 2026-08-01 is sealed (needs --holdout)")
    if g.kickoff_source not in A.KICKOFF_SOURCES:
        return f"kickoff not from ESPN ({g.kickoff_source})"
    if g.exclude:
        return g.exclude
    present = set(trades.loc[trades["kind"] == "trade", "market_id"].unique()) if len(trades) else set()
    if any(f"{g.event}-{t}" not in present for t in (g.home, g.away)):
        return "missing market"
    return ""


def evaluate_game(trades: pd.DataFrame, g: A.Game, xs=XS, final_test: bool = False) -> list[dict]:
    base = {"game_id": g.game_id, "league": g.league}
    ex = exclusion(trades, g, final_test)
    if ex:
        return [{**base, "x": x, "leg": lg, "entered": False, "skip": ex} for x in xs for lg in ("fade", "placebo")]
    ph, v = pressure(trades, g)
    t_ns = g.kickoff.value - W_HI_S * NS
    day = pd.Timestamp(t_ns, unit="ns", tz="UTC").tz_convert("America/New_York").date().isoformat()
    sig = {"P_h": ph, "V": v, "t_ns": t_ns, "day": day}
    if v < MIN_V:
        return [{**base, **sig, "x": x, "leg": lg, "entered": False, "skip": "V < 500"}
                for x in xs for lg in ("fade", "placebo")]
    i = ph / v
    rows = []
    for x in xs:
        if i >= x:
            fade, follow = g.away, g.home
        elif i <= -x:
            fade, follow = g.home, g.away
        else:
            rows += [{**base, **sig, "I": i, "x": x, "leg": lg, "entered": False, "skip": "below x"}
                     for lg in ("fade", "placebo")]
            continue
        for lg, team in (("fade", fade), ("placebo", follow)):
            rows.append({**base, **sig, "I": i, "x": x, "leg": lg, **leg(trades, g, team, t_ns)})
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


def metrics(e: pd.DataFrame, line: str, x2: bool, season: tuple[str, str], adaily: pd.Series | None) -> dict:
    s = "_x2" if x2 else ""
    pnl, roc, fill = e[f"pnl_{line}{s}"].to_numpy(float), e[f"roc_{line}{s}"].to_numpy(float), e[f"fill{s}"].to_numpy(float)
    n = len(e)
    out = {"trades": n, "wins": int((e["payout"] == 1.0).sum()), "losses": int((e["payout"] == 0.0).sum()),
           "ties": int((e["payout"] == 0.5).sum())}
    if n == 0:
        return out
    lo, hi = boot_ci(roc)
    daily = e.assign(_p=pnl).groupby("day")["_p"].sum().sort_index()
    first = min(pd.Timestamp(season[0]), pd.Timestamp(daily.index.min()))
    last = max(pd.Timestamp(season[1]), pd.Timestamp(daily.index.max()))
    days = pd.date_range(first, last, freq="D").strftime("%Y-%m-%d")
    full = daily.reindex(days, fill_value=0.0)
    sd_full = full.std(ddof=1)
    sd_d = daily.std(ddof=1) if len(daily) > 1 else float("nan")
    cum = np.concatenate([[0.0], daily.cumsum().to_numpy()])
    keep = np.setdiff1d(np.arange(n), np.argsort(-pnl, kind="stable")[:5])
    corr = float("nan")
    if adaily is not None and len(adaily):
        u = sorted(set(daily.index) | set(adaily.index))
        a, b = daily.reindex(u, fill_value=0.0), adaily.reindex(u, fill_value=0.0)
        corr = float(np.corrcoef(a, b)[0, 1]) if a.std() > 0 and b.std() > 0 else float("nan")
    out.update(mean_fill=float(fill.mean()), win_rate=float(e["payout"].mean()),
               win_minus_fill=float(e["payout"].mean() - fill.mean()), mean_I=float(e["I"].mean()),
               mean_abs_I=float(e["I"].abs().mean()),
               roc_mean=float(roc.mean()), roc_ci_lo=lo, roc_ci_hi=hi,
               cents_per_contract=float(pnl.sum() / (QTY * n) * 100), pnl_total=float(pnl.sum()),
               game_days=len(daily), season_days=len(days),
               sharpe_x365=float(full.mean() / sd_full * np.sqrt(365)) if sd_full > 0 else float("nan"),
               sharpe_daily=float(daily.mean() / sd_d) if sd_d == sd_d and sd_d > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()),
               skew_daily=float(skew(daily.to_numpy(), bias=False)) if len(daily) > 2 else float("nan"),
               worst_trade=float(pnl.min()), worst_day=float(daily.min()),
               excl_top5_trades=len(keep), excl_top5_roc=float(roc[keep].mean()) if len(keep) else float("nan"),
               excl_top5_pnl=float(pnl[keep].sum()), corr_daily_with_A=corr)
    return out


SKIP_NAMES = ["V < 500", "below x", "no post-decision trade", "fill at 0.99", "unsettled"]


def results_table(rows: pd.DataFrame, sample: str, adaily: pd.Series | None) -> pd.DataFrame:
    out = []
    for x in XS:
        for lg in ("fade", "placebo"):
            r = rows[(rows["x"] == x) & (rows["leg"] == lg)]
            e = r[r["entered"].astype(bool)]
            sk = r["skip"].fillna("").astype(str)
            skips = {"games": len(r), **{f"skip_{k}": int((sk == k).sum()) for k in SKIP_NAMES},
                     "skip_excluded": int((~r["entered"].astype(bool) & ~sk.isin(SKIP_NAMES)).sum())}
            for line in ("direct", "webull"):
                for x2 in (False, True):
                    out.append({"label": LABEL, "sample": sample, "x": x, "leg": lg,
                                "fee_line": "kalshi_direct" if line == "direct" else "webull",
                                "costs": "x2" if x2 else "x1", **skips,
                                **metrics(e, line, x2, SEASON[sample], adaily)})
    return pd.DataFrame(out)


def select_x(tab: pd.DataFrame) -> float | None:
    s = tab[(tab["leg"] == "fade") & (tab["fee_line"] == "kalshi_direct") & (tab["costs"] == "x1")
            & (tab["trades"] >= MIN_TRADES)]
    if s.empty:
        return None
    return float(s.sort_values(["roc_mean", "x"], ascending=[False, False]).iloc[0]["x"])


# ---------- loading ----------

def training_games() -> tuple[list[A.Game], Path]:
    raw = DATA / "raw"
    games = A.load_games(raw / "kalshi_only_games.csv", raw / "kalshi_market_meta.csv", ticks_dir=raw / "kalshi_only")
    assert all(g.kickoff < A.SEAL for g in games), "training only"
    return games, raw / "kalshi_only"


def holdout_games() -> tuple[list[A.Game], Path]:
    """As Post-hoc Idea 4 (scripts/final_test_run.real_ctx construction); input CSVs go to a temp dir."""
    hr = DATA / "holdout_raw"
    ev = pd.read_csv(hr / "events.csv")
    st = pd.read_csv(hr / "settlements.csv")
    home = st[st["side"] == "home"].set_index("game_id")["result"]
    ev = ev[ev["espn_kickoff"].notna()]
    ev = ev[pd.to_datetime(ev["espn_kickoff"], utc=True) <= AB_CUTOFF]
    a_games = pd.DataFrame({"game_id": ev["game_id"], "league": ev["league"], "home": ev["k_home_code"],
                            "away": ev["k_away_code"], "kalshi_event": ev["k_event"], "kalshi_ticker": ev["k_home_ticker"],
                            "kickoff_utc_espn": ev["espn_kickoff"], "kickoff_source": "espn",
                            "settlement_result": ev["game_id"].map(home).map({"yes": 1.0, "no": 0.0})})
    tmp = Path(tempfile.mkdtemp(prefix="posthoc_idea8_"))
    a_games.to_csv(tmp / "games.csv", index=False)
    st.assign(price_ranges=None).to_csv(tmp / "meta.csv", index=False)
    return A.load_games(tmp / "games.csv", tmp / "meta.csv", ticks_dir=hr / "kalshi", expect_preseason=None), hr / "kalshi"


def ticks(tdir: Path, g: A.Game) -> pd.DataFrame:
    f = tdir / f"{g.game_id}.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price",
                                                                       "size", "side"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="run the v3 A4 holdout A set ONCE (only when told)")
    args = ap.parse_args()
    sample = "holdout" if args.holdout else "training"
    games, tdir = holdout_games() if args.holdout else training_games()
    print(f"{LABEL}\nsample {sample}: {len(games)} games", flush=True)
    rows = []
    for i, g in enumerate(games):
        rows += evaluate_game(ticks(tdir, g), g, final_test=args.holdout)
        if i % 200 == 0:
            print(f"  {i}/{len(games)}", flush=True)
    rows = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    tab = results_table(rows, sample, a_daily())
    tab.to_csv(OUT / f"{sample}_results.csv", index=False)
    cols = ["game_id", "league", "x", "leg", "team", "t_ns", "day", "P_h", "V", "I", "fill_ts", "trade_px", "fill",
            "payout", "fee_direct", "pnl_direct", "roc_direct", "fee_webull", "pnl_webull", "roc_webull", "fill_x2",
            "fee_direct_x2", "pnl_direct_x2", "fee_webull_x2", "pnl_webull_x2"]
    rows[rows["entered"].astype(bool)][cols].assign(label=LABEL).to_csv(OUT / f"{sample}_trades.csv", index=False)
    sig = rows.drop_duplicates("game_id")
    print(f"games with V >= 500: {int((sig['V'] >= MIN_V).sum())} of {len(sig)}; "
          f"I quantiles: {sig.loc[sig['V'] >= MIN_V, 'I'].quantile([.05, .25, .5, .75, .95]).round(3).to_dict()}")
    sel = select_x(tab) if sample == "training" else None
    pd.set_option("display.width", 300, "display.max_columns", 80)
    print(f"selected x (training rule): {sel}")
    print(tab.round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
