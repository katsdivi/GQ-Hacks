"""Post-hoc Idea 9: ESPN win probability vs Kalshi.

post-hoc, exploratory; ESPN data used as a signal only; selected on training only.

Rule and implementation notes: results/posthoc_idea9/SPEC.md (committed df80d2c before any real-data run).
Team mapping and end-marker text rule copied from branch posthoc-idea6, commit 0f57732 (scripts/posthoc_idea6.py).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea9.py              training only (kickoff < 2026-08-01)
  (holdout: not wired; only on "run idea9 holdout")
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.stats import skew

import ingest.kalshi_only_train as T
import strategy_a as A

LABEL = "post-hoc, exploratory; ESPN data used as a signal only; selected on training only"
DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
IDEA6_CACHE = Path("/Users/divyamkataria/GQ HACKS/wt-idea6/data/espn_raw")   # read only
CACHE = Path("data/espn_raw")                                                 # this worktree, gitignored
A_ROWS = Path("/Users/divyamkataria/GQ HACKS/staleline/out/strategy_a/rows.parquet")
A_THETA = 0.80
OUT = Path("results/posthoc_idea9")
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/football/{}/summary"
NS = 1_000_000_000
KS = (0.05, 0.10)
DELAYS = (60, 180)
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
MARKERS = {"end game", "end of game", "end of 4th quarter"}


def D(x) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def fee_direct(p: Decimal, qty: int = QTY) -> Decimal:
    return D(A.fee_kalshi_direct(float(p), qty))


def fee_webull(p: Decimal, qty: int = QTY) -> Decimal:
    return WEBULL * qty


# ---------- ESPN (marker rule and orient() copied from posthoc-idea6 0f57732) ----------

def is_marker(text: str) -> bool:
    return re.sub(r"\.+$", "", str(text or "").strip()).strip().lower() in MARKERS


def orient(comp: dict, k_home: tuple[str, str], k_away: tuple[str, str]) -> str | None:
    """'same' if ESPN home = Kalshi home, 'swapped' if reversed, None if the name match is weak or tied."""
    t = {c["homeAway"]: c["team"] for c in comp["competitors"]}
    same = T._name_score(*k_home, t["home"]) + T._name_score(*k_away, t["away"])
    swap = T._name_score(*k_home, t["away"]) + T._name_score(*k_away, t["home"])
    best = max(same, swap)
    if best < 1.6 or same == swap:
        return None
    return "same" if same > swap else "swapped"


def plays_of(summary: dict) -> list[dict]:
    return [p for dr in (summary.get("drives") or {}).get("previous", []) for p in dr.get("plays", [])]


def wp_series(summary: dict) -> pd.DataFrame:
    """ESPN win probability joined to plays with a wallclock: columns order, wc_ns, home_wp (ESPN home)."""
    plays = {str(p.get("id")): p for p in plays_of(summary)}
    rows = []
    for i, w in enumerate(summary.get("winprobability") or []):
        p = plays.get(str(w.get("playId")))
        if p is None or not p.get("wallclock") or w.get("homeWinPercentage") is None:
            continue
        rows.append({"order": i, "wc_ns": pd.Timestamp(p["wallclock"]).value, "home_wp": float(w["homeWinPercentage"])})
    return pd.DataFrame(rows, columns=["order", "wc_ns", "home_wp"])


def window_end(summary: dict, ko_ns: int) -> int:
    """Earlier of kickoff + 4 h and the wallclock of the first end-marker play (any score)."""
    hi = ko_ns + WIN_HI_S * NS
    for p in plays_of(summary):
        if is_marker(p.get("text")) and p.get("wallclock"):
            return min(hi, pd.Timestamp(p["wallclock"]).value)
    return hi


def espn_by_known_time(wp: pd.DataFrame, delay: int, lo: int, hi: int) -> pd.DataFrame:
    """Distinct known-times t = wallclock + delay in [lo, hi]; value = last play in ESPN order with that t."""
    s = wp.assign(t=wp["wc_ns"] + delay * NS).sort_values("order", kind="stable")
    s = s.groupby("t", sort=True)["home_wp"].last().reset_index()
    return s[(s["t"] >= lo) & (s["t"] <= hi)].reset_index(drop=True)


# ---------- Kalshi ----------

def team_series(trades: pd.DataFrame, g: A.Game, team: str) -> tuple[np.ndarray, np.ndarray]:
    t = A.own_market_trades(trades, g, team)
    return t["ts"].to_numpy(np.int64), np.round(t["price"].to_numpy(float), 4)


def asof_price(ts: np.ndarray, px: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Last trade at or before each t, within FRESH_S of t, else NaN (backward as-of)."""
    i = np.searchsorted(ts, t, side="right") - 1
    ok = (i >= 0)
    out = np.full(len(t), np.nan)
    j = np.maximum(i, 0)
    fresh = ok & (t - ts[j] <= FRESH_S * NS) if len(ts) else np.zeros(len(t), bool)
    if len(ts):
        out[fresh] = px[j[fresh]]
    return out


def signals(trades: pd.DataFrame, g: A.Game, espn: pd.DataFrame, espn_home_is_kalshi_home: bool, k: float) -> dict:
    """First t with g_X >= k (signal) and first t with g_X <= -k (placebo), each over both teams."""
    t = espn["t"].to_numpy(np.int64)
    hw = espn["home_wp"].to_numpy(float)
    kh = hw if espn_home_is_kalshi_home else 1.0 - hw          # ESPN prob for the Kalshi home team
    out = {}
    gaps = {}
    for team, e in ((g.home, kh), (g.away, 1.0 - kh)):
        ts, px = team_series(trades, g, team)
        kx = asof_price(ts, px, t)
        gaps[team] = (e - kx, e, kx)
    for leg, sign in (("signal", 1.0), ("placebo", -1.0)):
        best = None
        for order, team in enumerate((g.home, g.away)):
            gx, e, kx = gaps[team]
            hit = np.flatnonzero(np.nan_to_num(sign * gx, nan=-np.inf) >= k - 1e-12)
            if len(hit) == 0:
                continue
            i = hit[0]
            cand = (int(t[i]), -abs(float(gx[i])), order, team, float(gx[i]), float(e[i]), float(kx[i]))
            if best is None or cand[:3] < best[:3]:
                best = cand
        if best is not None:
            out[leg] = {"t_ns": best[0], "team": best[3], "g": best[4], "espn_p": best[5], "kalshi_p": best[6]}
    return out


def leg(trades: pd.DataFrame, g: A.Game, team: str, t_ns: int) -> dict:
    """Fill and settle 10 YES contracts of team at decision t. Money in Decimal."""
    ts, px = team_series(trades, g, team)
    m = (ts >= t_ns + int(LATENCY_S * NS)) & (ts <= t_ns + int(LATENCY_S * NS) + FILL_WINDOW_S * NS)
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
        raise ValueError(f"{g.game_id}: kickoff on/after 2026-08-01 is sealed (needs the holdout phrase)")
    if g.kickoff_source not in A.KICKOFF_SOURCES:
        return f"kickoff not from ESPN ({g.kickoff_source})"
    if g.exclude:
        return g.exclude
    present = set(trades.loc[trades["kind"] == "trade", "market_id"].unique()) if len(trades) else set()
    if any(f"{g.event}-{t}" not in present for t in (g.home, g.away)):
        return "missing market"
    return ""


def evaluate_game(trades: pd.DataFrame, g: A.Game, summary: dict | None, names: tuple[str, str] | None,
                  final_test: bool = False) -> list[dict]:
    """names = (Kalshi home team name, Kalshi away team name). summary None = no ESPN summary."""
    base = {"game_id": g.game_id, "league": g.league}
    variants = [(k, d) for d in DELAYS for k in KS]

    def skip_all(why):
        return [{**base, "k": k, "delay": d, "leg": lg, "entered": False, "skip": why}
                for k, d in variants for lg in ("signal", "placebo")]

    ex = exclusion(trades, g, final_test)
    if ex:
        return skip_all(ex)
    if summary is None:
        return skip_all("no ESPN summary")
    wp = wp_series(summary)
    if wp.empty:
        return skip_all("no win probability series")
    comp = summary["header"]["competitions"][0]
    o = orient(comp, (names[0], g.home), (names[1], g.away)) if names else None
    if o is None:
        return skip_all("team mapping")
    ko = g.kickoff.value
    lo, hi = ko + WIN_LO_S * NS, window_end(summary, ko)
    rows = []
    for k, d in variants:
        espn = espn_by_known_time(wp, d, lo, hi)
        sig = signals(trades, g, espn, o == "same", k) if len(espn) else {}
        for lg in ("signal", "placebo"):
            s = sig.get(lg)
            if s is None:
                rows.append({**base, "k": k, "delay": d, "leg": lg, "entered": False, "skip": "no signal"})
                continue
            day = pd.Timestamp(s["t_ns"], unit="ns", tz="UTC").tz_convert("America/New_York").date().isoformat()
            r = leg(trades, g, s["team"], s["t_ns"])
            rows.append({**base, "k": k, "delay": d, "leg": lg, "t_ns": s["t_ns"], "day": day, "g": s["g"],
                         "espn_p": s["espn_p"], "kalshi_p": s["kalshi_p"], **r})
    return rows


# ---------- metrics ----------

def boot_ci(x: np.ndarray) -> tuple[float, float]:
    if len(x) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(SEED)
    m = x[rng.integers(0, len(x), size=(N_BOOT, len(x)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def a_daily() -> pd.Series | None:
    if not A_ROWS.exists():
        return None
    r = pd.read_parquet(A_ROWS)
    r = r[(r["theta"] == A_THETA) & (~r["placebo"].astype(bool)) & (r["entered"].astype(bool))]
    return r.groupby(r["date"].astype(str))["pnl_direct"].sum()


def metrics(e: pd.DataFrame, line: str, x2: bool, season: tuple[str, str], a_day: pd.Series | None) -> dict:
    s = "_x2" if x2 else ""
    pnl, roc, fill = (e[f"pnl_{line}{s}"].to_numpy(float), e[f"roc_{line}{s}"].to_numpy(float),
                      e[f"fill{s}"].to_numpy(float))
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
    pay = e["payout"].to_numpy(float)
    corr = float("nan")
    if a_day is not None:
        u = sorted(set(daily.index) | set(a_day.index))
        x, y = daily.reindex(u, fill_value=0.0), a_day.reindex(u, fill_value=0.0)
        if len(u) > 2 and x.std() > 0 and y.std() > 0:
            corr = float(np.corrcoef(x, y)[0, 1])
    out.update(mean_fill=float(fill.mean()), win_rate=float(pay.mean()),
               win_minus_fill=float(pay.mean() - fill.mean()),
               roc_mean=float(roc.mean()), roc_ci_lo=lo, roc_ci_hi=hi,
               cents_per_contract=float(pnl.sum() / (QTY * n) * 100), pnl_total=float(pnl.sum()),
               mean_g=float(e["g"].mean()),
               brier_espn=float(((e["espn_p"] - pay) ** 2).mean()),
               brier_kalshi=float(((e["kalshi_p"] - pay) ** 2).mean()),
               game_days=len(daily),
               sharpe_x365=float(full.mean() / sd_full * np.sqrt(365)) if sd_full > 0 else float("nan"),
               sharpe_daily=float(daily.mean() / sd_d) if sd_d == sd_d and sd_d > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()),
               skew_daily=float(skew(daily.to_numpy(), bias=False)) if len(daily) > 2 else float("nan"),
               worst_trade=float(pnl.min()), worst_day=float(daily.min()),
               excl_top5_trades=len(keep), excl_top5_roc=float(roc[keep].mean()) if len(keep) else float("nan"),
               excl_top5_pnl=float(pnl[keep].sum()), corr_daily_vs_A=corr)
    return out


def results_table(rows: pd.DataFrame, sample: str) -> pd.DataFrame:
    a_day = a_daily() if sample == "training" else None
    out = []
    for d in DELAYS:
        for k in KS:
            for lg in ("signal", "placebo"):
                r = rows[(rows["k"] == k) & (rows["delay"] == d) & (rows["leg"] == lg)]
                e = r[r["entered"].astype(bool)]
                sk = r["skip"].fillna("").astype(str)
                skips = {"games": len(r)}
                for why in sorted(set(sk) - {""}):
                    skips[f"skip_{why}"] = int((sk == why).sum())
                for line in ("direct", "webull"):
                    for x2 in (False, True):
                        out.append({"label": LABEL, "sample": sample, "k": k, "delay": d, "leg": lg,
                                    "fee_line": "kalshi_direct" if line == "direct" else "webull",
                                    "costs": "x2" if x2 else "x1", **skips,
                                    **metrics(e, line, x2, SEASON[sample], a_day)})
    return pd.DataFrame(out)


def select(tab: pd.DataFrame) -> tuple[float, int] | None:
    s = tab[(tab["leg"] == "signal") & (tab["fee_line"] == "kalshi_direct") & (tab["costs"] == "x1")
            & (tab["trades"] >= MIN_TRADES)]
    if s.empty:
        return None
    b = s.sort_values(["roc_mean", "delay", "k"], ascending=[False, False, False]).iloc[0]
    return float(b["k"]), int(b["delay"])


# ---------- loading ----------

def training_games() -> tuple[list[A.Game], Path]:
    raw = DATA / "raw"
    games = A.load_games(raw / "kalshi_only_games.csv", raw / "kalshi_market_meta.csv", ticks_dir=raw / "kalshi_only")
    assert all(g.kickoff < A.SEAL for g in games), "training only"
    return games, raw / "kalshi_only"


def load_summary(league: str, eid) -> dict | None:
    if eid is None or eid != eid:
        return None
    eid = str(eid).split(".")[0]
    for d in (IDEA6_CACHE, CACHE):
        f = d / f"{league.lower()}_{eid}.json"
        if f.exists():
            try:
                return json.loads(f.read_text())
            except json.JSONDecodeError:
                pass
    CACHE.mkdir(parents=True, exist_ok=True)
    sport = "nfl" if league.upper() == "NFL" else "college-football"
    for attempt in range(5):
        try:
            r = requests.get(SUMMARY.format(sport), params={"event": eid}, timeout=30)
            if r.status_code == 200:
                (CACHE / f"{league.lower()}_{eid}.json").write_text(r.text)
                time.sleep(0.4)
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    return None


def ticks(tdir: Path, g: A.Game) -> pd.DataFrame:
    f = tdir / f"{g.game_id}.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="not wired; holdout only on 'run idea9 holdout'")
    args = ap.parse_args()
    if args.holdout:
        raise SystemExit("holdout not wired: only on the exact phrase 'run idea9 holdout'")
    sample = "training"
    games, tdir = training_games()
    ids = pd.read_csv(IDEA6_CACHE / "ids_training.csv").set_index("game_id")
    print(f"{LABEL}\nsample {sample}: {len(games)} games", flush=True)
    rows = []
    for i, g in enumerate(games):
        r = ids.loc[g.game_id] if g.game_id in ids.index else None
        summ = load_summary(g.league, r["espn_id"]) if r is not None else None
        names = (r["k_home_name"], r["k_away_name"]) if r is not None else None
        if r is None or r["espn_id"] != r["espn_id"]:
            rows += [{"game_id": g.game_id, "league": g.league, "k": k, "delay": d, "leg": lg, "entered": False,
                      "skip": "no ESPN event id"} for d in DELAYS for k in KS for lg in ("signal", "placebo")]
            continue
        rows += evaluate_game(ticks(tdir, g), g, summ, names)
        if i % 200 == 0:
            print(f"  {i}/{len(games)}", flush=True)
    rows = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    tab = results_table(rows, sample)
    tab.to_csv(OUT / f"{sample}_results.csv", index=False)
    cols = ["game_id", "league", "k", "delay", "leg", "team", "t_ns", "day", "g", "espn_p", "kalshi_p", "fill_ts",
            "trade_px", "fill", "payout", "fee_direct", "pnl_direct", "roc_direct", "fee_webull", "pnl_webull",
            "roc_webull", "fill_x2", "pnl_direct_x2", "pnl_webull_x2"]
    rows[rows["entered"].astype(bool)][cols].assign(label=LABEL).to_csv(OUT / f"{sample}_trades.csv", index=False)
    sel = select(tab)
    pd.set_option("display.width", 320, "display.max_columns", 80)
    print(f"selected (k, delay) by the training rule: {sel}")
    print(tab.round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
