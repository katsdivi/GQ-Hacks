"""Helpers copied verbatim from scripts/posthoc_idea4.py on branch posthoc-idea4 (commit 5a90856): fees, metrics,
game-bootstrap CI, holdout game loader, tick loader. Not modified except for this docstring and the constants block.

post-hoc, exploratory; sportsbook closing line used as a signal only; selected on training only.
"""
from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import skew

import strategy_a as A

DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
QTY = 10
WEBULL = Decimal("0.02")
SEED, N_BOOT = 20261004, 2000
AB_CUTOFF = pd.Timestamp("2026-10-03 20:00", tz="America/New_York")


def D(x) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def fee_direct(p: Decimal, qty: int = QTY) -> Decimal:
    return D(A.fee_kalshi_direct(float(p), qty))


def fee_webull(p: Decimal, qty: int = QTY) -> Decimal:
    return WEBULL * qty


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
