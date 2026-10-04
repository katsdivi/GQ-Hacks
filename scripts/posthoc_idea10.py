"""Post-hoc Idea 10: scoring-event fade.

post-hoc, exploratory; selected on training only.

Rule and implementation notes: results/posthoc_idea10/SPEC.md (committed 3a02690 before any real-data run).
ESPN team mapping (orient) copied from branch posthoc-idea6, commit 0f57732, scripts/posthoc_idea6.py.

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea10.py              training only (kickoff < 2026-08-01)
  python scripts/posthoc_idea10.py --holdout    only on "run idea10 holdout" (needs holdout ESPN summaries)
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import skew

import ingest.kalshi_only_train as T
import strategy_a as A

LABEL = "post-hoc, exploratory; selected on training only"
DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
ESPN_CACHE = Path("/Users/divyamkataria/GQ HACKS/wt-idea6/data/espn_raw")   # Idea 6 cache, read-only
OUT = Path("results/posthoc_idea10")
NS = 1_000_000_000
SS = (0.03, 0.05, 0.10)
QTY = 10
WIN_LO_S, WIN_HI_S = 20 * 60, 4 * 3600
DECISION_S = 60
PRE_WIN_S, POST_WIN_S = 120, 30
LATENCY_S, ENTRY_WIN_S = 1.0, 60
HOLD_S, EXIT_WIN_S = 180, 120
HORIZONS = (10, 30, 60, 180, 300)
HALF = Decimal("0.01")
CAP, FLOOR = Decimal("0.99"), Decimal("0.01")
WEBULL = Decimal("0.02")
MIN_TRADES = 200
SEED, N_BOOT = 20261004, 2000
SCORING_TYPES = {"touchdown", "field-goal", "safety"}


def D(x) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def fee_direct(p: Decimal, qty: int = QTY) -> Decimal:
    return D(A.fee_kalshi_direct(float(p), qty))


def fee_webull(p: Decimal, qty: int = QTY) -> Decimal:
    return WEBULL * qty


# ---------- ESPN ----------

def orient(comp: dict, k_home: tuple[str, str], k_away: tuple[str, str]) -> str | None:
    """Copied from posthoc-idea6 0f57732. 'same' if ESPN home = Kalshi home, 'swapped' if reversed, None if weak/tied."""
    t = {c["homeAway"]: c["team"] for c in comp["competitors"]}
    same = T._name_score(*k_home, t["home"]) + T._name_score(*k_away, t["away"])
    swap = T._name_score(*k_home, t["away"]) + T._name_score(*k_away, t["home"])
    best = max(same, swap)
    if best < 1.6 or same == swap:
        return None
    return "same" if same > swap else "swapped"


def scoring_events(summary: dict) -> tuple[list[dict], dict]:
    """Scoring plays in ESPN order: {wc_ns, side ('home'/'away' per ESPN), ptype, order}. Plus skip counts."""
    plays = [p for dr in (summary.get("drives") or {}).get("previous", []) for p in dr.get("plays", [])]
    out, skips = [], {"no wallclock": 0, "no single scoring side": 0}
    prev = (0, 0)
    for i, p in enumerate(plays):
        cur = (p.get("homeScore", prev[0]), p.get("awayScore", prev[1]))
        st = (p.get("scoringType") or {}).get("name")
        if p.get("scoringPlay") and st in SCORING_TYPES:
            dh, da = cur[0] - prev[0], cur[1] - prev[1]
            if (dh > 0) == (da > 0):
                skips["no single scoring side"] += 1
            elif not p.get("wallclock"):
                skips["no wallclock"] += 1
            else:
                out.append({"wc_ns": pd.Timestamp(p["wallclock"]).value, "side": "home" if dh > 0 else "away",
                            "ptype": st, "order": i})
        prev = cur
    out.sort(key=lambda e: (e["wc_ns"], e["order"]))
    return out, skips


def to_kalshi(side: str, orientation: str, g: A.Game) -> str:
    espn_home = side == "home"
    return g.home if (espn_home if orientation == "same" else not espn_home) else g.away


# ---------- prices ----------

def team_series(trades: pd.DataFrame, g: A.Game, team: str) -> tuple[np.ndarray, np.ndarray]:
    t = A.own_market_trades(trades, g, team)
    return t["ts"].to_numpy(np.int64), np.round(t["price"].to_numpy(float), 4)


def last_at_or_before(ts: np.ndarray, px: np.ndarray, t_ns: int, within_s: float) -> float | None:
    i = np.searchsorted(ts, t_ns, side="right") - 1
    if i < 0 or ts[i] < t_ns - within_s * NS:
        return None
    return float(px[i])


def first_in(ts: np.ndarray, px: np.ndarray, lo_ns: int, hi_ns: int) -> tuple[int, float] | None:
    i = np.searchsorted(ts, lo_ns, side="left")
    if i >= len(ts) or ts[i] > hi_ns:
        return None
    return int(ts[i]), float(px[i])


def signal(series: dict, team: str, wc_ns: int) -> dict | None:
    """Move m of the scoring team's own YES price from wallclock to t = wallclock + 60 s. Uses only ts <= t."""
    ts, px = series[team]
    t = wc_ns + DECISION_S * NS
    pre = last_at_or_before(ts, px, wc_ns, PRE_WIN_S)
    post = last_at_or_before(ts, px, t, POST_WIN_S)
    if pre is None or post is None:
        return None
    return {"t_ns": t, "pre": pre, "post": post, "m": round(post - pre, 4)}


def trade(series: dict, team: str, t_ns: int, result_home: float, is_home: bool) -> dict | None:
    """Entry and exit for 10 YES of team. None if no entry fill within 60 s."""
    ts, px = series[team]
    lo = t_ns + int(LATENCY_S * NS)
    ent = first_in(ts, px, lo, lo + ENTRY_WIN_S * NS)
    if ent is None:
        return None
    ex_lo = t_ns + HOLD_S * NS
    ex = first_in(ts, px, ex_lo, ex_lo + EXIT_WIN_S * NS)
    r = {"team": team, "entry_ts": ent[0], "entry_trade": ent[1]}
    if ex is None:
        if result_home != result_home:
            return {**r, "void": True}
        settle = D(result_home) if is_home else Decimal(1) - D(result_home)
        r.update(exit_ts=None, exit_trade=None, exit_settle=True, settle=float(settle))
    else:
        r.update(exit_ts=ex[0], exit_trade=ex[1], exit_settle=False)
    return r


def money(r: dict) -> dict:
    out = {}
    for x2 in (False, True):
        k = 2 if x2 else 1
        sfx = "_x2" if x2 else ""
        en = min(D(r["entry_trade"]) + HALF * k, CAP)
        if r["exit_settle"]:
            exitp, exit_fee = D(r["settle"]), False
        else:
            exitp, exit_fee = max(D(r["exit_trade"]) - HALF * k, FLOOR), True
        gross = (exitp - en) * QTY
        for line, fn in (("direct", fee_direct), ("webull", fee_webull)):
            f = (fn(en) + (fn(exitp) if exit_fee else Decimal(0))) * k
            out[f"fee_{line}{sfx}"] = float(f)
            out[f"pnl_{line}{sfx}"] = float(gross - f)
        out[f"entry{sfx}"], out[f"exit{sfx}"], out[f"gross{sfx}"] = float(en), float(exitp), float(gross)
    return out


# ---------- per game ----------

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


def evaluate_game(trades: pd.DataFrame, g: A.Game, events: list[dict], orientation: str,
                  ss=SS, final_test: bool = False) -> tuple[list[dict], list[dict], dict]:
    """Returns (trade rows for every s and leg, event-study rows, event skip counts)."""
    ko = g.kickoff.value
    lo, hi = ko + WIN_LO_S * NS, ko + WIN_HI_S * NS
    series = {tm: team_series(trades, g, tm) for tm in (g.home, g.away)}
    ev = [e for e in events if lo <= e["wc_ns"] <= hi]
    sk = {"outside window": len(events) - len(ev), "no pre/post price": 0}
    sigs, study = [], []
    for e in ev:
        scorer = to_kalshi(e["side"], orientation, g)
        other = g.away if scorer == g.home else g.home
        s = signal(series, scorer, e["wc_ns"])
        if s is None:
            sk["no pre/post price"] += 1
        else:
            sigs.append({**e, **s, "scorer": scorer, "other": other})
        ts, px = series[scorer]
        pre = last_at_or_before(ts, px, e["wc_ns"], PRE_WIN_S)
        row = {"game_id": g.game_id, "ptype": e["ptype"], "wc_ns": e["wc_ns"], "pre": pre}
        for h in HORIZONS:
            p = last_at_or_before(ts, px, e["wc_ns"] + h * NS, 1e12)
            row[f"move_{h}"] = (p - pre) if (pre is not None and p is not None) else np.nan
        study.append(row)
    rows = []
    base = {"game_id": g.game_id, "league": g.league}
    for th in ss:
        for leg in ("fade", "placebo"):
            busy_until = -1
            for s in sigs:
                if s["m"] < th - 1e-9 or s["wc_ns"] < busy_until:
                    continue
                team = s["other"] if leg == "fade" else s["scorer"]
                r = trade(series, team, s["t_ns"], g.result, team == g.home)
                if r is None:
                    continue
                day = pd.Timestamp(s["t_ns"], unit="ns", tz="UTC").tz_convert("America/New_York").date().isoformat()
                row = {**base, "s": th, "leg": leg, "t_ns": s["t_ns"], "wc_ns": s["wc_ns"], "ptype": s["ptype"],
                       "m": s["m"], "day": day, **r}
                if r.get("void"):
                    row["entered"] = False
                    busy_until = 2 ** 62          # held to a void settlement: no further trades this game
                else:
                    row.update(entered=True, **money(r))
                    busy_until = r["exit_ts"] if r["exit_ts"] is not None else 2 ** 62
                rows.append(row)
    return rows, study, sk


# ---------- metrics ----------

def boot_ci(x: np.ndarray, games: np.ndarray) -> tuple[float, float]:
    """Game-level bootstrap of mean per-trade value (all of a game's trades resampled together)."""
    if len(x) < 2:
        return float("nan"), float("nan")
    ug, inv = np.unique(games, return_inverse=True)
    sums, cnts = np.bincount(inv, weights=x), np.bincount(inv)
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(ug), size=(N_BOOT, len(ug)))
    m = sums[idx].sum(axis=1) / cnts[idx].sum(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def metrics(e: pd.DataFrame, line: str, x2: bool) -> dict:
    s = "_x2" if x2 else ""
    n = len(e)
    out = {"trades": n, "games_traded": int(e["game_id"].nunique()) if n else 0,
           "exits_at_settlement": int(e["exit_settle"].sum()) if n else 0}
    if n == 0:
        return out
    pnl = e[f"pnl_{line}{s}"].to_numpy(float)
    cpc = pnl / QTY * 100
    gross = e[f"gross{s}"].to_numpy(float) / QTY * 100
    lo, hi = boot_ci(cpc, e["game_id"].to_numpy())
    daily = e.assign(_p=pnl).groupby("day")["_p"].sum().sort_index()
    sd_d = daily.std(ddof=1) if len(daily) > 1 else float("nan")
    cum = np.concatenate([[0.0], daily.cumsum().to_numpy()])
    by_game = e.assign(_p=pnl).groupby("game_id")["_p"].sum()
    top5 = set(by_game.sort_values(ascending=False, kind="stable").index[:5])
    keep = ~e["game_id"].isin(top5).to_numpy()
    sd_t = pnl.std(ddof=1) if n > 1 else float("nan")
    out.update(net_c_per_contract=float(cpc.mean()), net_ci_lo=lo, net_ci_hi=hi,
               gross_c_per_contract=float(gross.mean()), pnl_total=float(pnl.sum()),
               win_rate=float((pnl > 0).mean()),
               sharpe_per_trade=float(pnl.mean() / sd_t) if sd_t == sd_t and sd_t > 0 else float("nan"),
               game_days=len(daily),
               sharpe_daily_x365=float(daily.mean() / sd_d * np.sqrt(365)) if sd_d == sd_d and sd_d > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()),
               skew_trade=float(skew(pnl, bias=False)) if n > 2 else float("nan"),
               skew_daily=float(skew(daily.to_numpy(), bias=False)) if len(daily) > 2 else float("nan"),
               worst_trade=float(pnl.min()), worst_day=float(daily.min()),
               excl_top5_trades=int(keep.sum()),
               excl_top5_net_c_per_contract=float(cpc[keep].mean()) if keep.any() else float("nan"),
               excl_top5_pnl=float(pnl[keep].sum()),
               mean_m=float(e["m"].mean()), mean_entry=float(e[f"entry{s}"].mean()))
    return out


def results_table(rows: pd.DataFrame, sample: str) -> pd.DataFrame:
    out = []
    for th in SS:
        for leg in ("fade", "placebo"):
            r = rows[(rows["s"] == th) & (rows["leg"] == leg)] if len(rows) else rows
            e = r[r["entered"].astype(bool)] if len(r) else r
            voids = int((~r["entered"].astype(bool)).sum()) if len(r) else 0
            for line in ("direct", "webull"):
                for x2 in (False, True):
                    out.append({"label": LABEL, "sample": sample, "s": th, "leg": leg,
                                "fee_line": "kalshi_direct" if line == "direct" else "webull",
                                "costs": "x2" if x2 else "x1", "voids_excluded": voids, **metrics(e, line, x2)})
    return pd.DataFrame(out)


def select_s(tab: pd.DataFrame) -> float | None:
    s = tab[(tab["leg"] == "fade") & (tab["fee_line"] == "kalshi_direct") & (tab["costs"] == "x1")
            & (tab["trades"] >= MIN_TRADES)]
    if s.empty:
        return None
    return float(s.sort_values(["net_c_per_contract", "s"], ascending=[False, False]).iloc[0]["s"])


def event_study(study: pd.DataFrame) -> pd.DataFrame:
    out = []
    for pt, r in list(study.groupby("ptype")) + [("all", study)]:
        row = {"ptype": pt, "events": len(r), "with_pre_price": int(r["pre"].notna().sum())}
        for h in HORIZONS:
            x = r[f"move_{h}"].dropna()
            row[f"n_{h}s"] = len(x)
            row[f"median_move_{h}s_c"] = float(x.median() * 100) if len(x) else float("nan")
            row[f"mean_move_{h}s_c"] = float(x.mean() * 100) if len(x) else float("nan")
        out.append(row)
    return pd.DataFrame(out)


# ---------- loading ----------

def training_games() -> tuple[list[A.Game], Path]:
    raw = DATA / "raw"
    games = A.load_games(raw / "kalshi_only_games.csv", raw / "kalshi_market_meta.csv", ticks_dir=raw / "kalshi_only")
    assert all(g.kickoff < A.SEAL for g in games), "training only"
    return games, raw / "kalshi_only"


def ticks(tdir: Path, g: A.Game) -> pd.DataFrame:
    f = tdir / f"{g.game_id}.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price"])


def espn_for(g: A.Game, idrow) -> tuple[list[dict] | None, str | None, dict, str]:
    if idrow is None or pd.isna(idrow["espn_id"]):
        return None, None, {}, "no ESPN event id"
    eid = str(int(float(idrow["espn_id"])))
    p = ESPN_CACHE / f"{g.league.lower()}_{eid}.json"
    if not p.exists():
        return None, None, {}, "no ESPN summary"
    s = json.loads(p.read_text())
    o = orient(s["header"]["competitions"][0], (idrow["k_home_name"], g.home), (idrow["k_away_name"], g.away))
    if o is None:
        return None, None, {}, "team mapping"
    ev, sk = scoring_events(s)
    return ev, o, sk, ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="only on 'run idea10 holdout'")
    args = ap.parse_args()
    if args.holdout:
        raise SystemExit("holdout path not built: run only on 'run idea10 holdout'")
    sample = "training"
    games, tdir = training_games()
    ids = pd.read_csv(ESPN_CACHE / "ids_training.csv", dtype={"espn_id": str}).set_index("game_id")
    print(f"{LABEL}\nsample {sample}: {len(games)} games", flush=True)
    rows, study, gskip = [], [], {}
    evskip = {"no wallclock": 0, "no single scoring side": 0, "outside window": 0, "no pre/post price": 0}
    for i, g in enumerate(games):
        tr = ticks(tdir, g)
        ex = exclusion(tr, g, final_test=False)
        if not ex:
            ev, o, sk, ex = espn_for(g, ids.loc[g.game_id] if g.game_id in ids.index else None)
        if ex:
            gskip[ex] = gskip.get(ex, 0) + 1
            continue
        for k, v in sk.items():
            evskip[k] += v
        r, st, sk2 = evaluate_game(tr, g, ev, o)
        for k, v in sk2.items():
            evskip[k] += v
        rows += r
        study += st
        if i % 200 == 0:
            print(f"  {i}/{len(games)}", flush=True)
    rows = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    tab = results_table(rows, sample)
    tab.to_csv(OUT / f"{sample}_results.csv", index=False)
    es = event_study(pd.DataFrame(study))
    es.to_csv(OUT / f"{sample}_event_study.csv", index=False)
    if len(rows):
        rows.assign(label=LABEL).to_csv(OUT / f"{sample}_trades.csv", index=False)
    skips = {"games": len(games), "games_used": len(games) - sum(gskip.values()),
             **{f"game_skip: {k}": v for k, v in gskip.items()}, **{f"event_skip: {k}": v for k, v in evskip.items()},
             "events_in_window_study": len(study)}
    pd.Series(skips).to_csv(OUT / f"{sample}_skips.csv", header=["count"])
    sel = select_s(tab)
    pd.set_option("display.width", 300, "display.max_columns", 60)
    print(f"selected s (training rule): {sel}")
    print(pd.Series(skips).to_string())
    print(tab.round(4).to_string(index=False))
    print(es.round(2).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
