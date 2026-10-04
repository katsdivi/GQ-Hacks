"""Part 1 (descriptive, truncated recordings, outside HYPOTHESIS_v4 rule; not test set 1).

Runs the committed HYPOTHESIS_v4 maker (scripts/posthoc_mm_v4.py at 1d3d68a, Arm A min_spread 0, Arm B min_spread
0.03, F1 strict trade-through, maker fee 0) once on the RECORDED portion of the 6 Oct 3 games kicking off after
20:00 ET. Vultr data ends at about 00:34 ET Oct 4, so quoting stops at the last recorded book update.
Window: kickoff - 90 min (holdout_mid PRE_S, same as the posthoc-mm-signal windows) to min(kickoff + 4.5 h, end of
recording). +60 s marks only where a mid exists at or before the end of recording; later fills count 0 at +60 s
and are counted separately. Settlement: data/holdout_raw/settlements.csv only (no API calls); unsettled = NaN.
No synthetic data is mixed in.

Usage (cwd = repo root, PYTHONPATH=.:scripts): python scripts/mm_v4_truncated.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import posthoc_mm_v4 as M

LABEL = "descriptive, truncated recordings, outside HYPOTHESIS_v4 rule; not test set 1"
GAMES = ["cfb_20261004_fres_wsu", "cfb_20261004_bay_asu", "cfb_20261004_ewu_ucd", "cfb_20261004_txst_sdsu",
         "cfb_20261004_cin_ariz", "cfb_20261004_sjsu_haw"]
OUT = Path("results/posthoc_mm_v4_extra/truncated")
NS = M.NS
GAME_LEN_S = 3.5 * 3600          # nominal game length for "share of game covered" (kickoff to about kickoff + 3.5 h)


def md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    f = lambda v: f"{v:.4g}" if isinstance(v, float) else str(v)
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] +
                     ["| " + " | ".join(f(v) for v in r) + " |" for r in df.itertuples(index=False)])


def write_md(T: pd.DataFrame, P: pd.DataFrame) -> None:
    lines = [f"# HYPOTHESIS_v4 maker on truncated late Oct 3 games ({LABEL})", "",
             "Committed maker code scripts/posthoc_mm_v4.py (1d3d68a), one run, unedited. Recordings end about 00:34 ET Oct 4,",
             "so these games are cut mid-play; this is NOT test set 1 and is not evidence for or against HYPOTHESIS_v4.",
             "No synthetic data mixed in. Settlement only from data/holdout_raw/settlements.csv (no API calls).", "",
             "## Totals", "", md(T), "", "## Per game", "", md(P.drop(columns=["label"]))]
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main() -> None:
    import sys
    if "--md-only" in sys.argv:          # rebuild RESULTS.md from the CSVs written by the single run (no recompute)
        write_md(pd.read_csv(OUT / "totals.csv"), pd.read_csv(OUT / "per_game.csv"))
        return
    import holdout_mid as H
    OUT.mkdir(parents=True, exist_ok=True)
    c = pd.read_csv(M.ROOT / "data/live/holdout_candidates.csv").set_index("game_id")
    maps = H.load_maps(M.ROOT / "data/live/holdout_maps")
    sett = pd.read_csv(M.ROOT / "data/holdout_raw/settlements.csv")
    ld = M.Loader()
    rows, per = [], []
    for gid in GAMES:
        a = c.loc[gid]
        a = a.copy()
        a["game_id"] = gid
        ko = pd.Timestamp(a.kickoff_utc).value
        inst = H.instruments(a, maps)
        lo, hi0 = ko - H.PRE_S * NS, ko + H.POST_S * NS
        pt = ld.rows("polymarket", inst["polymarket"], lo, hi0)
        pb = ld.book("polymarket", pt)
        rec_end = int(pb.ts.max()) if len(pb.ts) else lo
        hi = min(hi0, rec_end + 1)
        tr = pt[(pt["kind"] == "trade") & pt["src_ts_ns"].notna()].sort_values("src_ts_ns", kind="stable")
        tts, tpx, tsz = (tr["src_ts_ns"].astype("int64").to_numpy(), tr["price"].to_numpy(float),
                         tr["size"].to_numpy(float))
        ks = sett[(sett.game_id == gid) & (sett.side == "home")]["settlement_value_dollars"]
        payout = float(ks.iloc[0]) if len(ks) and ks.iloc[0] == ks.iloc[0] else np.nan
        ingame_s = max(0.0, (rec_end - (ko + M.CUT[1])) / NS)
        for arm, ms in (("A", 0.0), ("B", 0.03)):
            fl = M.simulate(pb, tts, tpx, tsz, lo, hi, ko, None, None, "F1", min_spread=ms)
            sc = M.score(fl, pb, payout, M.PM_FEE)
            late = (sc["t"] + 60 * NS > rec_end) if len(sc) else pd.Series(dtype=bool)
            if len(sc):
                sc.loc[late, "pnl60"] = 0.0
                sc["pnl60"] = sc["pnl60"].fillna(0.0)
            sc["game"], sc["arm"], sc["late60"] = gid, arm, late if len(sc) else []
            rows.append(sc)
            q = float(sc["qty"].sum()) if len(sc) else 0.0
            per.append({"label": LABEL, "game": gid, "arm": arm, "kickoff_et": pd.Timestamp(ko, tz="UTC")
                        .tz_convert("America/New_York").strftime("%H:%M"),
                        "recording_end_et": pd.Timestamp(rec_end, tz="UTC").tz_convert("America/New_York").strftime("%H:%M"),
                        "ingame_recorded_min": round(ingame_s / 60, 1),
                        "share_game_covered": round(min(1.0, max(0.0, (rec_end - ko) / NS) / GAME_LEN_S), 3),
                        "trades_in_recording": int(len(tts)), "fills": int(len(sc)), "contracts": q,
                        "fills_mark_after_cutoff": int(late.sum()) if len(sc) else 0,
                        "pnl60_usd": float(sc["pnl60"].sum()) if len(sc) else 0.0,
                        "pnl60_c_per_contract": float(sc["pnl60"].sum() / q * 100) if q else np.nan,
                        "settled": payout == payout,
                        "pnlset_usd": float(sc["pnlset"].sum()) if (len(sc) and payout == payout) else np.nan})
        print(f"{gid} rec_end={per[-1]['recording_end_et']} trades={len(tts)}", flush=True)
    P = pd.DataFrame(per)
    P.to_csv(OUT / "per_game.csv", index=False)
    F = pd.concat([r for r in rows if len(r)], ignore_index=True) if any(len(r) for r in rows) else pd.DataFrame()
    tot = []
    for arm in ("A", "B"):
        x = P[P.arm == arm]
        q = x["contracts"].sum()
        tot.append({"arm": arm, "games": len(x), "fills": int(x["fills"].sum()), "contracts": q,
                    "pnl60_usd": x["pnl60_usd"].sum(), "pnl60_c_per_contract": x["pnl60_usd"].sum() / q * 100 if q else np.nan,
                    "fills_mark_after_cutoff": int(x["fills_mark_after_cutoff"].sum()),
                    "pnlset_usd_settled_games_only": x["pnlset_usd"].sum(min_count=1)})
    T = pd.DataFrame(tot)
    T.to_csv(OUT / "totals.csv", index=False)
    write_md(T, P)


if __name__ == "__main__":
    main()
