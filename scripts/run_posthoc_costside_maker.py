"""Runner for results/posthoc_costside_maker/SPEC.md. Training only (kickoff < 2026-08-01)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import strategy_a as A
import posthoc_costside_maker as M

ROOT = Path("/Users/divyamkataria/GQ HACKS/staleline/data/raw")
OUT = Path("results/posthoc_costside_maker")
(OUT / "per_trade").mkdir(parents=True, exist_ok=True)

GRID = {}
for h in (1, 2):
    for cap in (10, 30):
        for end in ("settle", "exit"):
            GRID[f"M1_h{h}_cap{cap}_{end}"] = dict(mech="M1", window="pre", h=h, cap=cap, W_min=5, thr=0.0, end=end)
for h in (1, 2, 3):
    for cap in (10, 30):
        for end in ("settle", "exit"):
            GRID[f"M2_h{h}_cap{cap}_{end}"] = dict(mech="M2", window="in", h=h, cap=cap, W_min=5, thr=0.0, end=end)
for w in ("pre", "late"):
    for thr in (0.85, 0.90):
        GRID[f"M3_{w}_thr{int(thr*100)}"] = dict(mech="M3", window=w, h=1, cap=10, W_min=5, thr=thr, end="settle")
for w in ("pre", "in"):
    for h in (1, 2):
        for W in (5, 15):
            GRID[f"M4_{w}_h{h}_W{W}"] = dict(mech="M4", window=w, h=h, cap=10, W_min=W, thr=0.0, end="settle")
assert len(GRID) == 32

games = A.load_games(ROOT / "kalshi_only_games.csv", ROOT / "kalshi_market_meta.csv", ticks_dir=ROOT / "kalshi_only")
rows, skips = [], {}
for g in games:
    assert g.kickoff < A.SEAL
    if g.kickoff_source not in A.KICKOFF_SOURCES or g.exclude or g.result != g.result:
        skips[g.game_id] = "skip"
        continue
    tr = pd.read_parquet(ROOT / "kalshi_only" / f"{g.game_id}.parquet", columns=["ts", "market_id", "kind", "price"])
    arrs = {}
    for t in (g.home, g.away):
        o = A.own_market_trades(tr, g, t)
        if o.empty:
            break
        arrs[t] = (o["ts"].to_numpy(np.int64), o["price"].round(4).to_numpy(float))
    if len(arrs) < 2:
        skips[g.game_id] = "skip"
        continue
    k = g.kickoff.value
    et = g.kickoff.tz_convert("America/New_York")
    base = {"game_id": g.game_id, "date": et.date(), "league": g.league,
            "wk": (et.tz_localize(None).normalize() - pd.Timedelta(days=et.dayofweek))}
    for tid, p in GRID.items():
        p = dict(p, tick=g.tick)
        fills, orders = M.simulate(arrs, [g.home, g.away], k, g.result, g.home, p)
        rows.append({**base, "trial": tid, **M.game_row(fills, orders, arrs, k, p)})
df = pd.DataFrame(rows)
print("games used", df.game_id.nunique(), "skipped", len(skips), flush=True)
df.to_parquet(OUT / "per_trade" / "game_rows.parquet")

weeks = sorted(df["wk"].unique())
assert len(weeks) == 25
test_weeks = weeks[6:]
wk_idx = {w: i for i, w in enumerate(weeks)}
df["wi"] = df["wk"].map(wk_idx)
test = df[df.wi >= 6]
allg = df

# selectors
SEL = {"WF-M1": "M1", "WF-M2": "M2", "WF-M3": "M3", "WF-M4": "M4"}
sel_rows = []
sel_log = []
for sid, mech in SEL.items():
    ids = [t for t, p in GRID.items() if p["mech"] == mech]
    for wi in range(6, 25):
        past = df[(df.trial.isin(ids)) & (df.wi < wi)]
        agg = past.groupby("trial").agg(pnl=("pnl_m175", "sum"), c=("contracts", "sum"))
        agg = agg[agg.c >= 30]
        best = None
        if len(agg):
            agg["cpc"] = agg.pnl / agg.c
            b = agg.cpc.idxmax()
            if agg.cpc[b] > 0:
                best = b
        sel_log.append({"sel": sid, "week_idx": wi, "chosen": best})
        cur = df[(df.wi == wi) & (df.trial.isin(ids))]
        if best is None:
            z = cur[cur.trial == ids[0]].copy()
            for c in ("orders", "fills", "contracts", "pnl_m0", "cap_m0", "pnl_m175", "cap_m175", "exits", "out_q",
                      "px_q", "pairs", "pair_cost", "pair_pnl_m175"):
                z[c] = 0
            z["trial"] = sid
            sel_rows.append(z)
        else:
            c = cur[cur.trial == best].copy()
            c["trial"] = sid
            sel_rows.append(c)
sel = pd.concat(sel_rows)
pd.DataFrame(sel_log).to_csv(OUT / "per_trade" / "selector_choices.csv", index=False)

res, daily = [], []
for tid in list(GRID) + list(SEL):
    d = test[test.trial == tid] if tid in GRID else sel[sel.trial == tid]
    s = M.summarize(d.reset_index(drop=True))
    if tid in GRID:
        sa = M.summarize(allg[allg.trial == tid].reset_index(drop=True))
        s["roc_m175_allweeks"] = sa["roc_m175"]
    p = GRID.get(tid, {})
    res.append({"trial_id": tid, "round": 1, "method": tid.split("_")[0], "params": str(
        {k: v for k, v in p.items() if k != "tick"}) if p else f"selector over {SEL[tid]} grid", **s})
    dd = d.groupby("date").agg(pnl=("pnl_m175", "sum"), pnl_maker0=("pnl_m0", "sum")).reset_index()
    dd.insert(0, "trial_id", tid)
    dd = dd.rename(columns={"date": "et_date"})
    daily.append(dd)
R = pd.DataFrame(res)
R = R.rename(columns={"contracts": "contracts_n", "fills": "trades", "roc_m175": "roc", "roc_ci_lo": "roc_ci_lo",
                      "roc_ci_hi": "roc_ci_hi", "c_per_contract_m175": "c_per_contract"})
R.to_csv(OUT / "trials_log_full.csv", index=False)
cols = ["trial_id", "round", "method", "params", "trades", "roc", "roc_ci_lo", "roc_ci_hi", "c_per_contract",
        "excl_top5_roc"]
R[cols + [c for c in R.columns if c not in cols]].to_csv(OUT / "trials_log.csv", index=False)
pd.concat(daily).to_csv(OUT / "daily_pnl.csv", index=False)
print(R.sort_values("roc_ci_lo", ascending=False)[["trial_id", "trades", "fill_rate", "adverse_sel", "roc", "roc_ci_lo",
      "roc_ci_hi", "c_per_contract", "c_per_contract_m0", "roc_m0", "excl_top5_roc"]].to_string())
