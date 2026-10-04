"""Post-hoc Idea 6: buy the ESPN winner just after the game's end marker, hold to settlement.

post-hoc, exploratory; designed and selected on training only.

Rule and implementation notes: results/posthoc_idea6/SPEC.md (committed 7c78c2c before any real-data run).
ESPN ids and summaries: scripts/posthoc_idea6_ids.py (cache data/espn_raw/, gitignored).

Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/posthoc_idea6.py              training only (kickoff < 2026-08-01)
  python scripts/posthoc_idea6.py --holdout    the v3 A4 holdout A set, ONCE, only on "run idea6 holdout"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import skew

import ingest.kalshi_only_train as T
import strategy_a as A

LABEL = "post-hoc, exploratory; designed and selected on training only"
DATA = Path("/Users/divyamkataria/GQ HACKS/staleline/data")
CACHE = Path("data/espn_raw")
OUT = Path("results/posthoc_idea6")
NS = 1_000_000_000
DS = (60, 180, 600)
QTY = 10
LATENCY_S = 1.0
FILL_WINDOW_S = 5 * 60   # SPEC Implementation notes: window measured from t + 1.0 s
HALF = Decimal("0.01")
CAP = Decimal("0.99")
WEBULL = Decimal("0.02")
MIN_TRADES = 50
SEED, N_BOOT = 20261004, 2000
SEASON = {"training": ("2025-07-31", "2026-01-25"), "holdout": ("2026-08-06", "2026-10-04")}
AB_CUTOFF = pd.Timestamp("2026-10-03 20:00", tz="America/New_York")
MARKERS = {"end game", "end of game", "end of 4th quarter"}
SKIP_ORDER = ["no ESPN event id", "no ESPN summary", "ESPN status not final", "no untied end marker",
              "play or score after marker", "marker without wallclock", "team mapping"]


def D(x) -> Decimal:
    return Decimal(str(round(float(x), 4)))


def fee_direct(p: Decimal, qty: int = QTY) -> Decimal:
    return D(A.fee_kalshi_direct(float(p), qty))


def fee_webull(p: Decimal, qty: int = QTY) -> Decimal:
    return WEBULL * qty


# ---------- ESPN game end ----------

def is_marker(text: str) -> bool:
    return re.sub(r"\.+$", "", str(text or "").strip()).strip().lower() in MARKERS


def game_end(summary: dict) -> dict:
    """E from the end-marker rule (SPEC 'Game end E'). Returns {'skip': reason} or
    {'E_ns', 'home_score', 'away_score', 'leader': 'home'|'away'} in ESPN's home/away terms.

    ESPN scoringPlays carry no wallclock, so 'no scoring play after the marker' is checked as: every scoring play
    is in the play list at or before the marker, and the last scoring play's score and the header final score
    both equal the score at the marker."""
    comp = summary["header"]["competitions"][0]
    if not comp.get("status", {}).get("type", {}).get("completed"):
        return {"skip": "ESPN status not final"}
    plays = [p for dr in (summary.get("drives") or {}).get("previous", []) for p in dr.get("plays", [])]
    idx = next((i for i, p in enumerate(plays) if is_marker(p.get("text"))
                and p.get("homeScore") is not None and p.get("homeScore") != p.get("awayScore")), None)
    if idx is None:
        return {"skip": "no untied end marker"}
    m = plays[idx]
    hs, as_ = int(m["homeScore"]), int(m["awayScore"])
    if any(not is_marker(p.get("text")) for p in plays[idx + 1:]):
        return {"skip": "play or score after marker"}
    pos = {str(p.get("id")): i for i, p in enumerate(plays)}
    sps = summary.get("scoringPlays") or []
    if any(pos.get(str(s.get("id")), len(plays)) > idx for s in sps):
        return {"skip": "play or score after marker"}
    if sps and (int(sps[-1]["homeScore"]), int(sps[-1]["awayScore"])) != (hs, as_):
        return {"skip": "play or score after marker"}
    final = {c["homeAway"]: int(c.get("score") or -1) for c in comp["competitors"]}
    if (final.get("home"), final.get("away")) != (hs, as_):
        return {"skip": "play or score after marker"}
    if not m.get("wallclock"):
        return {"skip": "marker without wallclock"}
    return {"E_ns": pd.Timestamp(m["wallclock"]).value, "home_score": hs, "away_score": as_,
            "leader": "home" if hs > as_ else "away"}


def orient(comp: dict, k_home: tuple[str, str], k_away: tuple[str, str]) -> str | None:
    """'same' if ESPN home = Kalshi home, 'swapped' if reversed, None if the name match is weak or tied.
    k_home / k_away = (Kalshi team name, Kalshi code)."""
    t = {c["homeAway"]: c["team"] for c in comp["competitors"]}
    same = T._name_score(*k_home, t["home"]) + T._name_score(*k_away, t["away"])
    swap = T._name_score(*k_home, t["away"]) + T._name_score(*k_away, t["home"])
    best = max(same, swap)
    if best < 1.6 or same == swap:
        return None
    return "same" if same > swap else "swapped"


def winner_code(end: dict, orientation: str, g: A.Game) -> str:
    espn_home_wins = end["leader"] == "home"
    kalshi_home_wins = espn_home_wins if orientation == "same" else not espn_home_wins
    return g.home if kalshi_home_wins else g.away


# ---------- trading ----------

def team_series(trades: pd.DataFrame, g: A.Game, team: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    t = trades[(trades["market_id"] == f"{g.event}-{team}") & (trades["kind"] == "trade")]
    t = t.sort_values("ts", kind="stable")
    px = t["price"].to_numpy(float)
    if team == g.away:
        px = 1.0 - px
    size = t["size"].to_numpy(float) if "size" in t else np.zeros(len(t))
    return t["ts"].to_numpy(np.int64), np.round(px, 4), size


def leg(trades: pd.DataFrame, g: A.Game, team: str, t_ns: int) -> dict:
    """10 YES of team: first trade in [t + 1 s, t + 1 s + 5 min], + 1 cent, cap 0.99, skip at 0.99. Decimal money.
    capacity = contracts traded on the market at or after t + 1 s (whole file)."""
    ts, px, size = team_series(trades, g, team)
    lo = t_ns + int(LATENCY_S * NS)
    after = np.flatnonzero(ts >= lo)
    cap_contracts = float(size[after].sum()) if len(after) else 0.0
    idx = np.flatnonzero((ts >= lo) & (ts <= lo + FILL_WINDOW_S * NS))
    if len(idx) == 0:
        return {"team": team, "entered": False, "skip": "no post-decision trade", "capacity": cap_contracts}
    fill_ts, trade_px = int(ts[idx[0]]), D(px[idx[0]])
    fill = min(trade_px + HALF, CAP)
    if fill >= CAP:
        return {"team": team, "entered": False, "skip": "fill at 0.99", "fill_ts": fill_ts, "capacity": cap_contracts}
    if g.result != g.result:
        return {"team": team, "entered": False, "skip": "unsettled", "fill_ts": fill_ts, "capacity": cap_contracts}
    payout = D(g.result) if team == g.home else Decimal(1) - D(g.result)
    out = {"team": team, "entered": True, "skip": "", "fill_ts": fill_ts, "fill_delay_s": (fill_ts - t_ns) / NS,
           "trade_px": float(trade_px), "fill": float(fill), "payout": float(payout), "capacity": cap_contracts}
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
    if g.exclude:
        return g.exclude
    present = set(trades.loc[trades["kind"] == "trade", "market_id"].unique()) if len(trades) else set()
    if any(f"{g.event}-{t}" not in present for t in (g.home, g.away)):
        return "missing market"
    return ""


def evaluate_game(trades: pd.DataFrame, g: A.Game, end: dict, orientation: str | None,
                  final_test: bool = False) -> tuple[list[dict], dict]:
    """Rows per D and leg, and one descriptive row. end = game_end(...) (or {'skip': ...})."""
    base = {"game_id": g.game_id, "league": g.league}
    ex = exclusion(trades, g, final_test)
    skip = end.get("skip") or ("team mapping" if orientation is None else "") or ex
    desc = {**base, "skip": skip}
    if skip:
        return [{**base, "D": d, "leg": lg, "entered": False, "skip": skip}
                for d in DS for lg in ("winner", "placebo")], desc
    E = end["E_ns"]
    win = winner_code(end, orientation, g)
    lose = g.away if win == g.home else g.home
    wts, wpx, _ = team_series(trades, g, win)
    all_ts = trades.loc[trades["kind"] == "trade", "ts"].to_numpy(np.int64)
    k_win = (1.0 if win == g.home else 0.0) if g.result == g.result else float("nan")
    desc.update(E_ns=E, winner=win, orientation=orientation, kalshi_winner_payout=(
        float("nan") if g.result != g.result else (g.result if win == g.home else 1 - g.result)),
        last_trade_after_E_s=(int(all_ts.max()) - E) / NS if len(all_ts) else float("nan"))
    hit = np.flatnonzero((wts >= E) & (wpx >= 0.99))
    desc["E_to_first_099_s"] = (int(wts[hit[0]]) - E) / NS if len(hit) else float("nan")
    for d in DS:
        desc[f"any_le_097_after_{d}"] = bool(((wts > E + d * NS) & (wpx <= 0.97)).any())
        prior = np.flatnonzero(wts <= E + d * NS)
        desc[f"last_px_at_{d}"] = float(wpx[prior[-1]]) if len(prior) else float("nan")
    rows = []
    day = pd.Timestamp(E, unit="ns", tz="UTC").tz_convert("America/New_York").date().isoformat()
    for d in DS:
        t = E + d * NS
        any_after = bool((all_ts >= t + int(LATENCY_S * NS)).any())
        for lg, team in (("winner", win), ("placebo", lose)):
            rows.append({**base, "D": d, "leg": lg, "t_ns": t, "E_ns": E, "day": day, "any_trade_after_t": any_after,
                         "last_trade_after_E_s": desc["last_trade_after_E_s"], **leg(trades, g, team, t)})
    return rows, desc


# ---------- metrics ----------

def boot_ci(x: np.ndarray, games: np.ndarray) -> tuple[float, float]:
    """Game-bootstrap: one trade per game per D and leg, so resampling rows = resampling games."""
    if len(x) < 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(SEED)
    m = x[rng.integers(0, len(x), size=(N_BOOT, len(x)))].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def metrics(e: pd.DataFrame, line: str, x2: bool, season: tuple[str, str]) -> dict:
    s = "_x2" if x2 else ""
    n = len(e)
    out = {"trades": n, "wins": int((e["payout"] == 1.0).sum()) if n else 0,
           "losses": int((e["payout"] == 0.0).sum()) if n else 0, "ties": int((e["payout"] == 0.5).sum()) if n else 0,
           "losing_game_ids": ";".join(e.loc[e[f"pnl_{line}{s}"] < 0, "game_id"]) if n else ""}
    if n == 0:
        return out
    pnl, roc, fill = (e[f"pnl_{line}{s}"].to_numpy(float), e[f"roc_{line}{s}"].to_numpy(float),
                      e[f"fill{s}"].to_numpy(float))
    lo, hi = boot_ci(roc, e["game_id"].to_numpy())
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
               game_days=len(daily), season_days=len(days),
               sharpe_x365=float(full.mean() / sd_full * np.sqrt(365)) if sd_full > 0 else float("nan"),
               sharpe_daily=float(daily.mean() / sd_d) if sd_d == sd_d and sd_d > 0 else float("nan"),
               max_drawdown=float((np.maximum.accumulate(cum) - cum).max()),
               skew_daily=float(skew(daily.to_numpy(), bias=False)) if len(daily) > 2 else float("nan"),
               worst_trade=float(pnl.min()),
               excl_top5_trades=len(keep), excl_top5_roc=float(roc[keep].mean()) if len(keep) else float("nan"),
               excl_top5_pnl=float(pnl[keep].sum()),
               median_fill_delay_s=float(e["fill_delay_s"].median()),
               median_E_to_last_trade_s=float(e["last_trade_after_E_s"].median()),
               capacity_median=float(e["capacity"].median()), capacity_mean=float(e["capacity"].mean()))
    return out


def results_table(rows: pd.DataFrame, sample: str) -> pd.DataFrame:
    out = []
    for d in DS:
        for lg in ("winner", "placebo"):
            r = rows[(rows["D"] == d) & (rows["leg"] == lg)]
            e = r[r["entered"].astype(bool)]
            sk = r["skip"].fillna("").astype(str)
            skips = {"games": len(r), "games_any_trade_after_t": int(r.get("any_trade_after_t", pd.Series(dtype=bool))
                                                                      .fillna(False).astype(bool).sum()),
                     "skip_end_or_mapping": int(sk.isin(SKIP_ORDER).sum()),
                     "skip_no_post_decision_trade": int((sk == "no post-decision trade").sum()),
                     "skip_fill_at_099": int((sk == "fill at 0.99").sum()),
                     "skip_unsettled": int((sk == "unsettled").sum()),
                     "skip_other_excluded": int((~r["entered"].astype(bool) & ~sk.isin(
                         SKIP_ORDER + ["no post-decision trade", "fill at 0.99", "unsettled"])).sum())}
            for line in ("direct", "webull"):
                for x2 in (False, True):
                    out.append({"label": LABEL, "sample": sample, "D_s": d, "leg": lg,
                                "fee_line": "kalshi_direct" if line == "direct" else "webull",
                                "costs": "x2" if x2 else "x1", **skips, **metrics(e, line, x2, SEASON[sample])})
    return pd.DataFrame(out)


def select_D(tab: pd.DataFrame) -> int | None:
    s = tab[(tab["leg"] == "winner") & (tab["fee_line"] == "kalshi_direct") & (tab["costs"] == "x1")
            & (tab["trades"] >= MIN_TRADES)]
    if s.empty:
        return None
    return int(s.sort_values(["roc_mean", "D_s"], ascending=[False, False]).iloc[0]["D_s"])


def descriptive(desc: pd.DataFrame, sample: str) -> str:
    L = [f"# Post-hoc Idea 6: descriptive outputs ({sample})", "", f"**Label: {LABEL}.** Not variants.", ""]
    clean = desc[desc["skip"] == ""]
    sk = desc.loc[desc["skip"] != "", "skip"].value_counts()
    L += ["## a) Clean E and skip counts", "", f"Games: {len(desc)}. Clean E (traded or eligible): {len(clean)}.", ""]
    L += [f"- {k}: {v}" for k, v in sk.items()] + [""]
    x = clean["E_to_first_099_s"]
    L += ["## b) Time from E to the winner's first trade at >= 0.99", "",
          f"Games with such a trade: {int(x.notna().sum())} of {len(clean)} (none: {int(x.isna().sum())}). "
          f"Median {x.median():.0f} s, p90 {x.quantile(0.9):.0f} s, min {x.min():.0f} s, max {x.max():.0f} s.", ""]
    L += ["## c) Share of clean-E games with any winner trade <= 0.97 after E + D", ""]
    for d in DS:
        c = clean[f"any_le_097_after_{d}"].astype(bool)
        L.append(f"- E + {d} s: {int(c.sum())} of {len(clean)} ({c.mean():.1%})")
    L += ["", "## d) Sanity", ""]
    for d in DS:
        b = clean[clean[f"last_px_at_{d}"] < 0.90]
        L.append(f"- D = {d} s: winner's last trade at or before E + D below 0.90: {len(b)} games: "
                 + ", ".join(f"{r.game_id} ({r[f'last_px_at_{d}']:.2f})" for _, r in b.iterrows()))
    mm = clean[clean["kalshi_winner_payout"].notna() & (clean["kalshi_winner_payout"] != 1.0)]
    L += ["", f"- ESPN winner at E differs from Kalshi settlement (payout of ESPN winner's market != 1): {len(mm)} "
          "games: " + ", ".join(f"{r.game_id} ({r.kalshi_winner_payout})" for _, r in mm.iterrows()),
          f"- Clean-E games unsettled on Kalshi: {int(clean['kalshi_winner_payout'].isna().sum())}",
          f"- Median time from E to Kalshi's last trade in the file (clean-E games): "
          f"{clean['last_trade_after_E_s'].median():.0f} s", ""]
    return "\n".join(L)


# ---------- loading ----------

def training_games() -> tuple[list[A.Game], Path]:
    raw = DATA / "raw"
    games = A.load_games(raw / "kalshi_only_games.csv", raw / "kalshi_market_meta.csv", ticks_dir=raw / "kalshi_only")
    assert all(g.kickoff < A.SEAL for g in games), "training only"
    return games, raw / "kalshi_only"


def holdout_games() -> tuple[list[A.Game], Path]:
    """As Post-hoc Idea 4 (scripts/final_test_run.real_ctx construction)."""
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
    tmp = Path(tempfile.mkdtemp(prefix="posthoc_idea6_"))
    a_games.to_csv(tmp / "games.csv", index=False)
    st.assign(price_ranges=None).to_csv(tmp / "meta.csv", index=False)
    return A.load_games(tmp / "games.csv", tmp / "meta.csv", ticks_dir=hr / "kalshi", expect_preseason=None), hr / "kalshi"


def ticks(tdir: Path, g: A.Game) -> pd.DataFrame:
    f = tdir / f"{g.game_id}.parquet"
    return pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price", "size"])


def espn_for(g: A.Game, idrow) -> tuple[dict, str | None]:
    if idrow is None or pd.isna(idrow["espn_id"]):
        return {"skip": "no ESPN event id"}, None
    eid = str(int(float(idrow["espn_id"])))
    p = CACHE / f"{g.league.lower()}_{eid}.json"
    if not p.exists():
        return {"skip": "no ESPN summary"}, None
    s = json.loads(p.read_text())
    end = game_end(s)
    names = {idrow["k_home_code"]: idrow["k_home_name"], idrow["k_away_code"]: idrow["k_away_name"]}
    o = orient(s["header"]["competitions"][0], (names.get(g.home, g.home), g.home), (names.get(g.away, g.away), g.away))
    return end, o


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="run the holdout set ONCE (only on 'run idea6 holdout')")
    args = ap.parse_args()
    sample = "holdout" if args.holdout else "training"
    games, tdir = holdout_games() if args.holdout else training_games()
    ids = pd.read_csv(CACHE / f"ids_{sample}.csv", dtype={"espn_id": str})
    gsrc = (pd.read_csv(DATA / "raw" / "kalshi_only_games.csv") if not args.holdout else
            pd.read_csv(DATA / "holdout_raw" / "events.csv").rename(columns={"k_home_code": "home", "k_away_code": "away"}))
    ids = ids.merge(gsrc[["game_id", "home", "away"]].rename(columns={"home": "k_home_code", "away": "k_away_code"}),
                    on="game_id", how="left").set_index("game_id")
    print(f"{LABEL}\nsample {sample}: {len(games)} games", flush=True)
    rows, descs = [], []
    for i, g in enumerate(games):
        idrow = ids.loc[g.game_id] if g.game_id in ids.index else None
        if idrow is not None:
            idrow = idrow.copy()
            idrow["game_id"] = g.game_id
        end, o = espn_for(g, idrow)
        r, d = evaluate_game(ticks(tdir, g), g, end, o, final_test=args.holdout)
        rows += r
        descs.append(d)
        if i % 200 == 0:
            print(f"  {i}/{len(games)}", flush=True)
    rows, descs = pd.DataFrame(rows), pd.DataFrame(descs)
    OUT.mkdir(parents=True, exist_ok=True)
    tab = results_table(rows, sample)
    tab.to_csv(OUT / f"{sample}_results.csv", index=False)
    cols = ["game_id", "league", "D", "leg", "team", "E_ns", "t_ns", "day", "fill_ts", "fill_delay_s", "trade_px", "fill",
            "payout", "capacity", "fee_direct", "pnl_direct", "roc_direct", "fee_webull", "pnl_webull", "roc_webull",
            "fill_x2", "fee_direct_x2", "pnl_direct_x2", "fee_webull_x2", "pnl_webull_x2"]
    e = rows[rows["entered"].astype(bool)]
    e.reindex(columns=cols).assign(label=LABEL).to_csv(OUT / f"{sample}_trades.csv", index=False)
    descs.assign(label=LABEL).to_csv(OUT / f"{sample}_games.csv", index=False)
    (OUT / f"{sample}_descriptive.md").write_text(descriptive(descs, sample))
    sel = select_D(tab) if sample == "training" else None
    pd.set_option("display.width", 300, "display.max_columns", 60)
    print(f"selected D (training rule): {sel}")
    print(tab.drop(columns=["label", "losing_game_ids"]).round(4).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
