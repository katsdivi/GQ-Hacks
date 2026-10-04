"""Post-hoc Idea 13: NFL closing moneyline (nflverse, no-vig) as fair value at kickoff; buy the Kalshi side that is
cheap vs the line, hold to settlement.

post-hoc, exploratory; sportsbook closing line used as a signal only; selected on training only.

Rule and implementation notes: results/posthoc_idea13/SPEC.md (committed before any real-data run).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea13.py              training only (kickoff < 2026-08-01)
  python scripts/posthoc_idea13.py --holdout    v3 A4 holdout NFL games, ONCE, only on "run idea13 holdout"
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

import posthoc_idea13_map as M
import strategy_a as A
from posthoc_idea13_common import fee_direct, fee_webull, holdout_games, metrics, ticks

LABEL = "post-hoc, exploratory; sportsbook closing line used as a signal only; selected on training only"
OUT = Path("results/posthoc_idea13")
NS = 1_000_000_000
ES = (0.02, 0.04, 0.06)
QTY = 10
STALE_S = 600
LATENCY_S = 1.0
FILL_WINDOW_S = 300
HALF = Decimal("0.01")
CAP = Decimal("0.99")
MIN_TRADES = 40
SEASON = {"training": ("2025-07-31", "2026-01-25"), "holdout": ("2026-08-06", "2026-10-04")}


def D(x) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def implied(ml: float) -> float:
    """American odds -> implied probability (with vig)."""
    return -ml / (-ml + 100.0) if ml < 0 else 100.0 / (ml + 100.0)


def no_vig(ml_x: float, ml_y: float) -> tuple[float, float]:
    """No-vig probabilities of X and Y: implied probabilities normalized to sum 1."""
    a, b = implied(ml_x), implied(ml_y)
    return a / (a + b), b / (a + b)


def last_price(trades: pd.DataFrame, g: A.Game, team: str, t_ns: int) -> float | None:
    """Last own-market YES trade at or before t, only if within STALE_S before t. Uses rows with ts <= t only."""
    tr = A.own_market_trades(trades, g, team)
    past = tr[tr["ts"] <= t_ns]
    if past.empty or past["ts"].iloc[-1] < t_ns - STALE_S * NS:
        return None
    return float(round(past["price"].iloc[-1], 4))


def leg(trades: pd.DataFrame, g: A.Game, team: str, t_ns: int) -> dict:
    """Fill and settle 10 YES of team at decision t (first trade in [t + 1 s, t + 1 s + 5 min]). Money in Decimal."""
    tr = A.own_market_trades(trades, g, team)
    ts, px = tr["ts"].to_numpy(np.int64), np.round(tr["price"].to_numpy(float), 4)
    lo = t_ns + int(LATENCY_S * NS)
    idx = np.flatnonzero((ts >= lo) & (ts <= lo + FILL_WINDOW_S * NS))
    if len(idx) == 0:
        return {"team": team, "entered": False, "skip": "no post-decision trade"}
    fill_ts, trade_px = int(ts[idx[0]]), D(px[idx[0]])
    fill = min(trade_px + HALF, CAP)
    if fill >= CAP:
        return {"team": team, "entered": False, "skip": "fill at 0.99", "fill_ts": fill_ts}
    if g.result != g.result:
        return {"team": team, "entered": False, "skip": "void", "fill_ts": fill_ts}
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


def evaluate_game(trades: pd.DataFrame, g: A.Game, ml_home: float, ml_away: float, es=ES,
                  final_test: bool = False) -> tuple[list[dict], dict]:
    """Rows per (e, leg) and one per-game record (p, K, settlement) for the Brier comparison."""
    base = {"game_id": g.game_id, "league": g.league}
    info = {**base, "p_home": float("nan"), "k_home": float("nan"), "k_away": float("nan"), "result": g.result,
            "status": ""}
    if ml_home != ml_home or ml_away != ml_away:
        info["status"] = "no nflverse line"
        return [{**base, "e": e, "leg": lg, "entered": False, "skip": "no nflverse line"}
                for e in es for lg in ("signal", "placebo")], info
    ex = exclusion(trades, g, final_test)
    if ex:
        info["status"] = ex
        return [{**base, "e": e, "leg": lg, "entered": False, "skip": ex}
                for e in es for lg in ("signal", "placebo")], info
    t_ns = g.kickoff.value
    p_home, p_away = no_vig(ml_home, ml_away)
    k_home, k_away = last_price(trades, g, g.home, t_ns), last_price(trades, g, g.away, t_ns)
    info.update(p_home=p_home, k_home=k_home if k_home is not None else float("nan"),
                k_away=k_away if k_away is not None else float("nan"))
    if k_home is None or k_away is None:
        info["status"] = "no Kalshi price"
        return [{**base, "e": e, "leg": lg, "entered": False, "skip": "no Kalshi price"}
                for e in es for lg in ("signal", "placebo")], info
    edge = {g.home: p_home - k_home, g.away: p_away - k_away}
    # signal: larger p - K (home on a tie); placebo: larger K - p (home on a tie)
    sig_team = g.home if edge[g.home] >= edge[g.away] else g.away
    pla_team = g.home if -edge[g.home] >= -edge[g.away] else g.away
    day = pd.Timestamp(t_ns, unit="ns", tz="UTC").tz_convert("America/New_York").date().isoformat()
    rows = []
    for e in es:
        for lg, team, gap in (("signal", sig_team, edge[sig_team]), ("placebo", pla_team, -edge[pla_team])):
            if gap < e - 1e-12:
                rows.append({**base, "e": e, "leg": lg, "entered": False, "skip": "below e", "gap": gap})
                continue
            p_x = p_home if team == g.home else p_away
            k_x = k_home if team == g.home else k_away
            rows.append({**base, "e": e, "leg": lg, "t_ns": t_ns, "day": day, "gap": gap, "p_x": p_x, "k_x": k_x,
                         **leg(trades, g, team, t_ns)})
    return rows, info


def brier(info: pd.DataFrame) -> dict:
    d = info[info["p_home"].notna() & info["k_home"].notna() & info["result"].notna()]
    y = d["result"].to_numpy(float)
    return {"brier_games": len(d), "brier_p": float(((d["p_home"] - y) ** 2).mean()) if len(d) else float("nan"),
            "brier_k": float(((d["k_home"] - y) ** 2).mean()) if len(d) else float("nan")}


SKIPS = ("no nflverse line", "no Kalshi price", "below e", "no post-decision trade", "fill at 0.99", "void")


def results_table(rows: pd.DataFrame, sample: str, br: dict) -> pd.DataFrame:
    out = []
    for e in ES:
        for lg in ("signal", "placebo"):
            r = rows[(rows["e"] == e) & (rows["leg"] == lg)]
            en = r[r["entered"].astype(bool)].copy()
            sk = r["skip"].fillna("").astype(str)
            skips = {"games": len(r), **{f"skip_{s.replace(' ', '_').replace('.', '')}": int((sk == s).sum())
                                         for s in SKIPS},
                     "skip_excluded_other": int((~r["entered"].astype(bool) & ~sk.isin(SKIPS)).sum())}
            for line in ("direct", "webull"):
                for x2 in (False, True):
                    m = metrics(en, line, x2, SEASON[sample])
                    if len(en):
                        m["mean_gap"] = float(en["gap"].mean())
                    out.append({"label": LABEL, "sample": sample, "e": e, "leg": lg,
                                "fee_line": "kalshi_direct" if line == "direct" else "webull",
                                "costs": "x2" if x2 else "x1", **skips, **m, **br})
    return pd.DataFrame(out)


def select_e(tab: pd.DataFrame) -> float | None:
    s = tab[(tab["leg"] == "signal") & (tab["fee_line"] == "kalshi_direct") & (tab["costs"] == "x1")
            & (tab["trades"] >= MIN_TRADES)]
    if s.empty:
        return None
    return float(s.sort_values(["roc_mean", "e"], ascending=[False, False]).iloc[0]["e"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="v3 A4 holdout NFL games ONCE (only when told)")
    args = ap.parse_args()
    sample = "holdout" if args.holdout else "training"
    if args.holdout:
        games, tdir = holdout_games()
        meta = M.holdout_nfl()
    else:
        raw = M.DATA / "raw"
        games = A.load_games(raw / "kalshi_only_games.csv", raw / "kalshi_market_meta.csv", ticks_dir=raw / "kalshi_only")
        assert all(g.kickoff < A.SEAL for g in games), "training only"
        tdir = raw / "kalshi_only"
        meta = M.training_nfl()
    games = [g for g in games if g.league.upper() == "NFL"]
    mp = M.match(meta, M.nflverse()).set_index("game_id")
    print(f"{LABEL}\nsample {sample}: {len(games)} NFL games", flush=True)
    rows, infos = [], []
    for g in games:
        mh = mp.loc[g.game_id, "ml_home"] if g.game_id in mp.index else float("nan")
        ma = mp.loc[g.game_id, "ml_away"] if g.game_id in mp.index else float("nan")
        r, info = evaluate_game(ticks(tdir, g), g, float(mh), float(ma), final_test=args.holdout)
        rows += r
        infos.append(info)
    rows, info = pd.DataFrame(rows), pd.DataFrame(infos)
    br = brier(info)
    OUT.mkdir(parents=True, exist_ok=True)
    tab = results_table(rows, sample, br)
    tab.to_csv(OUT / f"{sample}_results.csv", index=False)
    tr = rows[rows["entered"].astype(bool)].assign(label=LABEL)
    tr.to_csv(OUT / f"{sample}_trades.csv", index=False)          # per-trade, gitignored
    info.assign(label=LABEL).to_csv(OUT / f"{sample}_games.csv", index=False)   # per-game prices, gitignored
    sel = select_e(tab) if sample == "training" else None
    pd.set_option("display.width", 300, "display.max_columns", 80)
    print("game status:", info["status"].replace("", "evaluated").value_counts().to_dict())
    print(f"Brier on {br['brier_games']} games: p (nflverse no-vig) {br['brier_p']:.4f}, K (Kalshi) {br['brier_k']:.4f}")
    print(f"selected e (training rule): {sel}")
    cols = ["e", "leg", "fee_line", "costs", "games", "trades", "wins", "losses", "mean_fill", "win_rate", "mean_gap",
            "roc_mean", "roc_ci_lo", "roc_ci_hi", "cents_per_contract", "pnl_total", "sharpe_x365", "sharpe_daily",
            "max_drawdown", "skew_daily", "excl_top5_roc", "excl_top5_pnl"]
    print(tab[[c for c in cols if c in tab]].round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
