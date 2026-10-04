"""Post-hoc Idea 4: late-game near-certainty favorite, hold to settlement.

post-hoc, exploratory; designed and selected on training only; holdout run once.

Rule and implementation notes: results/posthoc_idea4/SPEC.md (committed before any real-data run).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea4.py              training only (kickoff < 2026-08-01)
  python scripts/posthoc_idea4.py --holdout    the v3 A4 holdout A/B set, ONCE, only when explicitly told
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

LABEL = "post-hoc, exploratory; designed and selected on training only; holdout run once"
DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
OUT = Path("results/posthoc_idea4")
NS = 1_000_000_000
THETAS = (0.90, 0.93, 0.95, 0.97)
QTY = 10
WIN_LO_S, WIN_HI_S = 20 * 60, 4 * 3600
FRESH_S = 60
LATENCY_S = 1.0
FILL_WINDOW_S = 5 * 60
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


def team_series(trades: pd.DataFrame, g: A.Game, team: str) -> tuple[np.ndarray, np.ndarray]:
    t = A.own_market_trades(trades, g, team)
    return t["ts"].to_numpy(np.int64), np.round(t["price"].to_numpy(float), 4)


def decide(trades: pd.DataFrame, g: A.Game, theta: float) -> dict | None:
    """First eligible trade (either team, merged time order, home first at equal ns). Uses only rows <= t."""
    ko = g.kickoff.value
    lo, hi = ko + WIN_LO_S * NS, ko + WIN_HI_S * NS
    best = None
    for order, team in enumerate((g.home, g.away)):
        ts, px = team_series(trades, g, team)
        if len(ts) == 0:
            continue
        prev = np.searchsorted(ts, ts, side="left") - 1          # last trade with ts strictly < own ts
        has_prev = prev >= 0
        gap = np.where(has_prev, ts - ts[np.maximum(prev, 0)], np.iinfo(np.int64).max)
        ok = (ts >= lo) & (ts <= hi) & (px >= theta) & has_prev & (gap <= FRESH_S * NS)
        idx = np.flatnonzero(ok)
        if len(idx) == 0:
            continue
        cand = (int(ts[idx[0]]), order, team, float(px[idx[0]]))
        if best is None or cand[:2] < best[:2]:
            best = cand
    if best is None:
        return None
    return {"t_ns": best[0], "team": best[2], "signal_px": best[3]}


def leg(trades: pd.DataFrame, g: A.Game, team: str, t_ns: int) -> dict:
    """Fill and settle 10 YES contracts of team at decision t. Money in Decimal."""
    ts, px = team_series(trades, g, team)
    m = (ts >= t_ns + int(LATENCY_S * NS)) & (ts <= t_ns + FILL_WINDOW_S * NS)
    idx = np.flatnonzero(m)
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
           "fill": float(fill), "payout": float(payout)}
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


def evaluate_game(trades: pd.DataFrame, g: A.Game, thetas=THETAS, final_test: bool = False) -> list[dict]:
    base = {"game_id": g.game_id, "league": g.league}
    ex = exclusion(trades, g, final_test)
    rows = []
    for th in thetas:
        if ex:
            rows += [{**base, "theta": th, "leg": lg, "entered": False, "skip": ex} for lg in ("favorite", "placebo")]
            continue
        d = decide(trades, g, th)
        if d is None:
            rows += [{**base, "theta": th, "leg": lg, "entered": False, "skip": "no signal"}
                     for lg in ("favorite", "placebo")]
            continue
        other = g.away if d["team"] == g.home else g.home
        day = pd.Timestamp(d["t_ns"], unit="ns", tz="UTC").tz_convert("America/New_York").date().isoformat()
        for lg, team in (("favorite", d["team"]), ("placebo", other)):
            r = leg(trades, g, team, d["t_ns"])
            rows.append({**base, "theta": th, "leg": lg, "t_ns": d["t_ns"], "signal_px": d["signal_px"],
                         "day": day, **r})
    return rows


# ---------- metrics ----------

def boot_ci(x: np.ndarray) -> tuple[float, float]:
    if len(x) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(SEED)
    m = x[rng.integers(0, len(x), size=(N_BOOT, len(x)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def metrics(e: pd.DataFrame, line: str, x2: bool, season: tuple[str, str]) -> dict:
    s = "_x2" if x2 else ""
    pnl, roc, fee, fill = (e[f"pnl_{line}{s}"].to_numpy(float), e[f"roc_{line}{s}"].to_numpy(float),
                           e[f"fee_{line}{s}"].to_numpy(float), e[f"fill{s}"].to_numpy(float))
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
    top5 = np.argsort(-pnl, kind="stable")[:5]
    keep = np.setdiff1d(np.arange(n), top5)
    out.update(mean_fill=float(fill.mean()), win_rate=float(e["payout"].mean()),
               roc_mean=float(roc.mean()), roc_ci_lo=lo, roc_ci_hi=hi,
               cents_per_contract=float(pnl.sum() / (QTY * n) * 100), pnl_total=float(pnl.sum()),
               game_days=len(daily), season_first=first.date().isoformat(), season_last=last.date().isoformat(),
               season_days=len(days),
               sharpe_x365=float(full.mean() / sd_full * np.sqrt(365)) if sd_full > 0 else float("nan"),
               sharpe_daily=float(daily.mean() / sd_d) if sd_d == sd_d and sd_d > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()),
               skew_daily=float(skew(daily.to_numpy(), bias=False)) if len(daily) > 2 else float("nan"),
               worst_trade=float(pnl.min()), worst_day=float(daily.min()),
               excl_top5_trades=len(keep), excl_top5_roc=float(roc[keep].mean()) if len(keep) else float("nan"),
               excl_top5_pnl=float(pnl[keep].sum()),
               breakeven_win_rate=float((fill + fee / QTY).mean()))
    out["win_minus_breakeven"] = out["win_rate"] - out["breakeven_win_rate"]
    return out


def results_table(rows: pd.DataFrame, sample: str) -> pd.DataFrame:
    out = []
    for th in THETAS:
        for lg in ("favorite", "placebo"):
            r = rows[(rows["theta"] == th) & (rows["leg"] == lg)]
            e = r[r["entered"].astype(bool)]
            sk = r["skip"].fillna("").astype(str)
            skips = {"games": len(r), "skip_no_signal": int((sk == "no signal").sum()),
                     "skip_no_post_decision_trade": int((sk == "no post-decision trade").sum()),
                     "skip_fill_at_099": int((sk == "fill at 0.99").sum()),
                     "skip_unsettled": int((sk == "unsettled").sum()),
                     "skip_excluded": int((~r["entered"].astype(bool) & ~sk.isin(
                         ["no signal", "no post-decision trade", "fill at 0.99", "unsettled"])).sum())}
            for line in ("direct", "webull"):
                for x2 in (False, True):
                    out.append({"label": LABEL, "sample": sample, "theta": th, "leg": lg,
                                "fee_line": "kalshi_direct" if line == "direct" else "webull",
                                "costs": "x2" if x2 else "x1", **skips, **metrics(e, line, x2, SEASON[sample])})
    return pd.DataFrame(out)


def select_theta(tab: pd.DataFrame) -> float | None:
    s = tab[(tab["leg"] == "favorite") & (tab["fee_line"] == "kalshi_direct") & (tab["costs"] == "x1")
            & (tab["trades"] >= MIN_TRADES)]
    if s.empty:
        return None
    return float(s.sort_values(["roc_mean", "theta"], ascending=[False, False]).iloc[0]["theta"])


# ---------- loading ----------

def training_games() -> tuple[list[A.Game], Path]:
    raw = DATA / "raw"
    games = A.load_games(raw / "kalshi_only_games.csv", raw / "kalshi_market_meta.csv", ticks_dir=raw / "kalshi_only")
    assert all(g.kickoff < A.SEAL for g in games), "training only"
    return games, raw / "kalshi_only"


def holdout_games() -> tuple[list[A.Game], Path]:
    """As scripts/final_test_run.real_ctx builds the Strategy A games; input CSVs go to a temp dir."""
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
    a_meta = st.assign(price_ranges=None)
    tmp = Path(tempfile.mkdtemp(prefix="posthoc_idea4_"))
    a_games.to_csv(tmp / "games.csv", index=False)
    a_meta.to_csv(tmp / "meta.csv", index=False)
    return A.load_games(tmp / "games.csv", tmp / "meta.csv", ticks_dir=hr / "kalshi", expect_preseason=None), hr / "kalshi"


def ticks(tdir: Path, g: A.Game) -> pd.DataFrame:
    f = tdir / f"{g.game_id}.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="run the v3 A4 holdout A/B set ONCE (only when told)")
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
    tab = results_table(rows, sample)
    tab.to_csv(OUT / f"{sample}_results.csv", index=False)
    cols = ["game_id", "league", "theta", "leg", "team", "t_ns", "day", "signal_px", "fill_ts", "trade_px", "fill",
            "payout", "fee_direct", "pnl_direct", "roc_direct", "fee_webull", "pnl_webull", "roc_webull", "fill_x2",
            "fee_direct_x2", "pnl_direct_x2", "fee_webull_x2", "pnl_webull_x2"]
    tr = rows[rows["entered"].astype(bool)][cols].assign(label=LABEL)
    tr.to_csv(OUT / f"{sample}_trades.csv", index=False)
    sel = select_theta(tab) if sample == "training" else None
    pd.set_option("display.width", 300, "display.max_columns", 60)
    print(f"selected theta (training rule): {sel}")
    print(tab.round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
