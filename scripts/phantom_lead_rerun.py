"""Robustness, post-run: residue levels removed. Reruns ONLY the v2 lead test (game lags, placebo, Mann-Whitney,
Holm decision) exactly as scripts/final_test_run.lead -> holdout_mid.run_all(holdout_run=True), with one change:
every recorded book row (kind bid or ask) with 0 < size < 0.01 contracts is dropped when rows are read. On the
top-of-book recordings that leaves that side empty at that snapshot (mid undefined there, never filled across).

Inputs are the frozen ones the run used (scripts/final_test_run.real_ctx): Vultr then Mac machines, frozen GAPS
tables and heartbeats, data/live/holdout_candidates.csv, holdout_maps. Writes ONLY results/robustness_phantom/.
results/holdout/ is read for the comparison only.

Usage (cwd = repo root, PYTHONPATH=.:scripts): nice -n 19 python scripts/phantom_lead_rerun.py
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow.dataset as ds

import holdout_mid as H

LABEL = "robustness, post-run: residue levels removed"
ROOT = Path("/Users/divyamkataria/GQ HACKS/staleline")
OUT = Path("results/robustness_phantom")
RESIDUE = 0.01
COUNTS: dict[str, list[int]] = {}


class ResidueFreeMachine(H.Machine):
    def rows(self, venue: str, market: str, lo_ns: int, hi_ns: int) -> pd.DataFrame:
        fs = self.files(venue)
        if not fs:
            return pd.DataFrame(columns=["ts", "venue", "market_id", "kind", "price"])
        d = ds.dataset(fs, format="parquet")
        f = (ds.field("market_id") == market) & (ds.field("ts") >= lo_ns) & (ds.field("ts") <= hi_ns)
        t = d.to_table(filter=f, columns=["ts", "venue", "market_id", "kind", "price", "size"]).to_pandas()
        drop = t["kind"].isin(["bid", "ask"]) & (t["size"] > 0) & (t["size"] < RESIDUE)
        c = COUNTS.setdefault(venue, [0, 0])
        c[0] += len(t)
        c[1] += int(drop.sum())
        return t.loc[~drop, ["ts", "venue", "market_id", "kind", "price"]].reset_index(drop=True)


def main() -> None:
    live = ROOT / "data" / "live"
    vroot, mroot = ROOT / "data" / "vultr", ROOT / "data" / "mac"
    machines = [ResidueFreeMachine("vultr", vroot, vroot / "GAPS_vultr.md", vroot / "heartbeats"),
                ResidueFreeMachine("mac", ROOT, mroot / "GAPS_mac.md", mroot / "heartbeats")]
    cands = pd.read_csv(live / "holdout_candidates.csv")
    maps = H.load_maps(live / "holdout_maps")
    res = H.run_all(cands, maps, machines, holdout_run=True)
    OUT.mkdir(parents=True, exist_ok=True)
    pre = json.loads((ROOT / "results" / "holdout" / "lead_decisions.json").read_text())
    rows = []
    for t in H.TESTS:
        res[t]["per_game"].assign(label=LABEL).to_csv(OUT / f"lead_{t}_per_game.csv", index=False)
        res[t]["placebo"].assign(label=LABEL).to_csv(OUT / f"lead_{t}_placebo.csv", index=False)
        old = pd.read_csv(ROOT / "results" / "holdout" / f"lead_{t}_per_game.csv")
        oq = old[old["qualifying"].fillna(False).astype(bool)]
        nq = res[t]["per_game"]
        nq = nq[nq.get("qualifying", pd.Series(False, index=nq.index)).fillna(False).astype(bool)]
        d = res[t]["decision"]
        rows.append({"test": t, "label": LABEL,
                     "pre_result": pre[t]["result"], "robust_result": d.get("result"),
                     "pre_n_qualifying": pre[t]["n_qualifying"], "robust_n_qualifying": d.get("n_qualifying"),
                     "pre_median_corrected_lag_s": pre[t]["median_corrected_lag_s"],
                     "robust_median_corrected_lag_s": d.get("median_corrected_lag_s"),
                     "pre_median_game_lag_s": float(oq["lag_s"].median()),
                     "robust_median_game_lag_s": float(nq["lag_s"].median()),
                     "pre_mann_whitney_p": pre[t]["mann_whitney_p"], "robust_mann_whitney_p": d.get("mann_whitney_p"),
                     "pre_placebo_median_s": pre[t]["placebo_median_s"],
                     "robust_placebo_median_s": d.get("placebo_median_s"),
                     "pre_share_positive": pre[t]["share_positive"], "robust_share_positive": d.get("share_positive"),
                     "pre_holm_level": pre[t]["holm_level"], "robust_holm_level": d.get("holm_level"),
                     "games_lag_changed": int(oq.set_index("game_id")["lag_s"].sub(
                         nq.set_index("game_id")["lag_s"]).abs().gt(0).sum())})
    cmp_ = pd.DataFrame(rows)
    cmp_.to_csv(OUT / "lead_comparison.csv", index=False)
    (OUT / "lead_decisions.json").write_text(json.dumps(
        {"label": LABEL, "rows_read_and_dropped": COUNTS, **{t: res[t]["decision"] for t in H.TESTS}},
        indent=1, default=str))
    print(LABEL)
    print("rows read / dropped per venue:", COUNTS)
    print(cmp_.T.to_string())


if __name__ == "__main__":
    main()
