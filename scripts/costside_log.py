"""Post-hoc cost-side search: cumulative trials log and multiple-testing correction over ALL rounds so far.

post-hoc, exploratory; training only. Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/costside_log.py
Reads data/costside_cache/registry_round*.csv and trades_round*.parquet; writes
results/posthoc_costside/trials_log.csv and correction.json, and prints the stop-condition check.
"""
from __future__ import annotations

import glob
import json

import numpy as np
import pandas as pd

import costside_common as C


def main() -> None:
    reg = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(str(C.CACHE / "registry_round*.csv")))],
                    ignore_index=True)
    tr = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(C.CACHE / "trades_round*.parquet")))],
                   ignore_index=True)
    rows, series = [], {}
    for r in reg.itertuples():
        d = tr[tr.trial == r.trial]
        m = C.metrics(d)
        alt = d.assign(pnl=d.pnl_alt, cap=d.cap_alt) if len(d) else d
        ma = C.metrics(alt) if len(d) else {}
        rows.append({"round": r.round, "trial": r.trial, "method": r.method, "params": r.params,
                     "cost_line": r.cost_line, **m,
                     "alt_roc": ma.get("roc"), "alt_roc_lo": ma.get("roc_lo"), "alt_roc_hi": ma.get("roc_hi"),
                     "alt_c_per_contract": ma.get("c_per_contract")})
        series[r.trial] = d.groupby("day")["pnl"].sum() if len(d) else pd.Series(dtype=float)
    log = pd.DataFrame(rows)
    mt = C.multiple_testing({k: v for k, v in series.items()})
    log["holm_p"] = log.trial.map(mt.get("holm", {}))
    log["raw_p"] = log.trial.map(mt.get("raw_p", {}))
    log["label"] = "post-hoc, exploratory; training only; walk-forward test weeks"
    stop = log[(log.roc_lo > 0) & (log.trades >= 100) & (log.excl5_pnl > 0)]
    stop_ok = (not stop.empty) and mt.get("rc_p", 1) < 0.05
    log = log.sort_values(["round", "roc"], ascending=[True, False])
    log.to_csv(C.OUT / "trials_log.csv", index=False)
    best_is = log.sort_values("roc", ascending=False).iloc[0]
    out = {"cumulative_trials": int(len(reg)), "rc_p_best_by_t": mt.get("rc_p"), "best_by_t": mt.get("best_by_t"),
           "best_t": mt.get("best_t"), "dsr_best": mt.get("dsr_best"), "days": mt.get("days"),
           "holm_survivors_005": [k for k, v in mt.get("holm", {}).items() if v < 0.05],
           "stop_candidates": stop.trial.tolist(), "stop_condition_met": bool(stop_ok),
           "in_sample_best_by_roc": {"trial": best_is.trial, "roc": best_is.roc, "roc_lo": best_is.roc_lo,
                                     "roc_hi": best_is.roc_hi, "trades": int(best_is.trades)}}
    (C.OUT / "correction.json").write_text(json.dumps(out, indent=1, default=float))
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print(json.dumps(out, indent=1, default=float))
    print(log[["trial", "trades", "roc", "roc_lo", "roc_hi", "c_per_contract", "alt_roc", "excl5_pnl", "holm_p"]]
          .sort_values("roc", ascending=False).head(15).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
