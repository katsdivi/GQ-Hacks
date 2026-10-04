"""Data-quality check: book levels with 0 < size < 0.01 contracts (floating-point residue, not a real quote).

Read-only on results/holdout/ and the recorded books. Item 2 of the check (a to d), Kalshi and polymarket.com,
on the 88 qualifying polymarket.com lead-test games (window, machine and book-wipe exclusion per game from
results/holdout/lead_polymarket.com_per_game.csv; game set cross-checked against data/live/holdout_windows.csv
at feadc99).

The recordings are TOP OF BOOK only: the collector writes one bid row and one ask row (best level price and
size, P(home) terms) per snapshot change. So "level update" here means a recorded top-of-book row, and
"dropping a residue level" can only make that side EMPTY at that snapshot (the next level is not recorded);
the mid is then undefined there, never filled across the empty side (Amendment 2 rule).

Usage (cwd = repo root, PYTHONPATH=.:scripts): nice -n 19 python scripts/phantom_check.py
Writes results/robustness_phantom/item2_per_game.csv and item2_summary.csv.
"""
from __future__ import annotations

import glob
import io
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds

import holdout_mid as H
import xcorr_lead as X

ROOT = Path("/Users/divyamkataria/GQ HACKS/staleline")
VROOT = ROOT / "data" / "vultr"
OUT = Path("results/robustness_phantom")
NS = H.NS
RESIDUE = 0.01
BOOK = ["bid", "ask"]


def is_residue(size: pd.Series) -> pd.Series:
    return (size > 0) & (size < RESIDUE)


def load(venue: str, markets: set[str]) -> pd.DataFrame:
    fs = sorted(glob.glob(str(VROOT / "data" / "live" / venue / "*" / "*.parquet")))
    d = ds.dataset(fs, format="parquet")
    f = ds.field("market_id").isin(sorted(markets)) & ds.field("kind").isin(BOOK)
    t = d.to_table(filter=f, columns=["ts", "venue", "market_id", "kind", "price", "size"]).to_pandas()
    return t.sort_values("ts", kind="stable").reset_index(drop=True)


def grid_flags(rows: pd.DataFrame, lo_g: int, hi_g: int) -> pd.Series:
    """Per 1 s grid point: True if the as-of top-of-book state (last snapshot at or before the end of the
    second) has a best bid or best ask with 0 < size < 0.01. Same backward carry as xcorr_lead.mid_grid."""
    w = rows.pivot_table(index="ts", columns="kind", values="size", aggfunc="last", dropna=False).sort_index()
    for k in BOOK:
        if k not in w:
            w[k] = np.nan
    flag = (is_residue(w["bid"].fillna(0)) | is_residue(w["ask"].fillna(0))).astype(float)
    g = w.index.to_numpy() // NS
    last = pd.Series(flag.to_numpy(), index=g).groupby(level=0).last()
    full = np.arange(min(last.index.min(), lo_g), hi_g + 1, dtype="int64")
    return last.reindex(full).ffill().fillna(0).astype(bool).loc[lo_g:hi_g]


def in_excl(idx: np.ndarray, ex: tuple[int, int]) -> np.ndarray:
    return (idx >= ex[0]) & (idx <= ex[1])


def game_stats(rows: pd.DataFrame, venue: str, lo_ns: int, end_ns: int, ex: tuple[int, int]) -> dict:
    r = rows[(rows.ts >= lo_ns) & (rows.ts < end_ns)]
    lo_g, hi_g = lo_ns // NS, end_ns // NS - 1
    res = is_residue(r["size"])
    clean = r[~res]
    g_all = X.mid_grid(X.mid_snapshots(r, venue)).reindex(np.arange(lo_g, hi_g + 1))
    g_cln = X.mid_grid(X.mid_snapshots(clean, venue)).reindex(np.arange(lo_g, hi_g + 1))
    idx = g_all.index.to_numpy()
    keep = ~in_excl(idx, ex)
    a, c = g_all.to_numpy(), g_cln.to_numpy()
    both_nan = np.isnan(a) & np.isnan(c)
    differ = ~both_nan & ~(np.abs(a - c) <= 1e-12)
    flags = grid_flags(r, lo_g, hi_g).reindex(idx, fill_value=False).to_numpy() if len(r) else np.zeros(len(idx), bool)
    both_def = differ & ~np.isnan(a) & ~np.isnan(c)
    return {
        f"{venue}_rows": len(r), f"{venue}_residue_rows": int(res.sum()),
        f"{venue}_grid_s": int(keep.sum()),
        f"{venue}_grid_residue_top": int((flags & keep).sum()),
        f"{venue}_mid_differ": int((differ & keep).sum()),
        f"{venue}_mid_differ_to_undefined": int((differ & keep & ~np.isnan(a) & np.isnan(c)).sum()),
        f"{venue}_mid_differ_both_defined": int((both_def & keep).sum()),
        f"{venue}_mean_abs_diff_both_defined": float(np.abs(a - c)[both_def & keep].mean()) if (both_def & keep).any() else 0.0,
        f"{venue}_mid_changes_all": X.n_mid_changes(g_all, [ex]),
        f"{venue}_mid_changes_clean": X.n_mid_changes(g_cln, [ex]),
    }


def main() -> None:
    per = pd.read_csv(ROOT / "results" / "holdout" / "lead_polymarket.com_per_game.csv")
    q = per[per["qualifying"].fillna(False).astype(bool)].copy()
    win = pd.read_csv(io.StringIO(subprocess.run(["git", "show", "feadc99:data/live/holdout_windows.csv"],
                                                 capture_output=True, text=True, check=True).stdout))
    wq = win[(win.venue == "polymarket") & win.qualifying.astype(bool) & ~win.excluded_outage.astype(bool)
             & ~win.excluded_no_rows.astype(bool) & ~win.excluded_no_instrument.astype(bool)
             & ~win.not_qualifying_mid_changes.astype(bool)]
    assert set(wq.game_id) == set(q.game_id), (len(wq), len(q))
    assert (q.machine == "vultr").all(), q.machine.value_counts()
    cands = pd.read_csv(ROOT / "data" / "live" / "holdout_candidates.csv").set_index("game_id")
    maps = H.load_maps(ROOT / "data" / "live" / "holdout_maps")
    inst = {g: H.instruments(cands.loc[[g]].reset_index().iloc[0], maps) for g in q.game_id}
    print(f"{len(q)} games; loading books", flush=True)
    kb = load("kalshi", {i["kalshi"] for i in inst.values()})
    pb = load("polymarket", {i["polymarket"] for i in inst.values()})
    print(f"kalshi rows {len(kb)}, polymarket rows {len(pb)}", flush=True)
    kg, pg = dict(tuple(kb.groupby("market_id"))), dict(tuple(pb.groupby("market_id")))
    out = []
    for r in q.itertuples():
        i = inst[r.game_id]
        lo, end, ex = int(r.window_start_ns), int(r.window_end_ns), (int(r.excl_lo_g), int(r.excl_hi_g))
        row = {"game_id": r.game_id, "window_start_ns": lo, "window_end_ns": end}
        row.update(game_stats(kg.get(i["kalshi"], kb.iloc[:0]), "kalshi", lo, end, ex))
        row.update(game_stats(pg.get(i["polymarket"], pb.iloc[:0]), "polymarket", lo, end, ex))
        out.append(row)
    d = pd.DataFrame(out)
    for v in ("kalshi", "polymarket"):
        d[f"{v}_share_mid_differ"] = d[f"{v}_mid_differ"] / d[f"{v}_grid_s"]
    OUT.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT / "item2_per_game.csv", index=False)
    s = []
    for v in ("kalshi", "polymarket"):
        s.append({"venue": v, "games": len(d), "rows": int(d[f"{v}_rows"].sum()),
                  "residue_rows": int(d[f"{v}_residue_rows"].sum()),
                  "share_residue_rows": d[f"{v}_residue_rows"].sum() / max(d[f"{v}_rows"].sum(), 1),
                  "grid_s": int(d[f"{v}_grid_s"].sum()),
                  "share_grid_residue_top": d[f"{v}_grid_residue_top"].sum() / d[f"{v}_grid_s"].sum(),
                  "share_grid_mid_differ": d[f"{v}_mid_differ"].sum() / d[f"{v}_grid_s"].sum(),
                  "mid_differ_to_undefined": int(d[f"{v}_mid_differ_to_undefined"].sum()),
                  "mid_differ_both_defined": int(d[f"{v}_mid_differ_both_defined"].sum()),
                  "max_game_share_mid_differ": float(d[f"{v}_share_mid_differ"].max()),
                  "games_share_mid_differ_gt_0.1pct": int((d[f"{v}_share_mid_differ"] > 0.001).sum()),
                  "mid_changes_all_total": int(d[f"{v}_mid_changes_all"].sum()),
                  "mid_changes_clean_total": int(d[f"{v}_mid_changes_clean"].sum()),
                  "games_mid_changes_differ": int((d[f"{v}_mid_changes_all"] != d[f"{v}_mid_changes_clean"]).sum()),
                  "games_clean_below_50_changes": int((d[f"{v}_mid_changes_clean"] < H.MIN_CHANGES).sum())})
    s = pd.DataFrame(s)
    s.to_csv(OUT / "item2_summary.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(s.T.to_string())


if __name__ == "__main__":
    main()
