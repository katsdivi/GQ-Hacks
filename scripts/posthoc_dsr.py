"""Deflated Sharpe for Strategy A (holdout) and the combined book with trials = final variants.csv row count.

post-hoc reporting addition; does not overwrite the pre-registered DSR values in results/holdout/numbers.json
(OOS.*.deflated_sharpe_total_22). No strategy is rerun: the OOS book is rebuilt by report_book.build from the
committed holdout outputs (results/holdout/strategy_a_rows.parquet, strategy_b_trades.parquet), exactly as
scripts/final_test_run.run does, with training capital bases and training trial Sharpes from
report_book.training_inputs(). Only n_total changes. As a check, n_total = 22 must reproduce the stored values.
The holdout costs-x2 B trades were not saved, so b2 = the x1 trades here; that only affects costs_x2 keys,
which are discarded (DSR does not use them).

Usage (cwd = repo root): python scripts/posthoc_dsr.py   -> results/posthoc/dsr_posthoc.json
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import report_book as RB  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
HR = ROOT / "data" / "holdout_raw"
AB_CUTOFF = pd.Timestamp("2026-10-03 20:00", tz="America/New_York")
SEL_B = (0.05, 10, 300)
STORED = ROOT / "results" / "holdout" / "numbers.json"
OUT = ROOT / "results" / "posthoc" / "dsr_posthoc.json"


def oos_dsr(n_total: int, rows, bt, kos, fac, bases, trial) -> dict:
    with tempfile.TemporaryDirectory() as d:
        num, _, _ = RB.build(rows.assign(theta=RB.A_THETA), bt, bt, SEL_B, kos, fac, Path(d), prefix="OOS.",
                             label="Out-of-sample", bases=bases, trial_srs=trial, png="x.png", n_total=n_total)
    return {k: v["value"] for k, v in num.items() if f"deflated_sharpe_total_{n_total}" in k}


def main() -> None:
    n_rows = len(pd.read_csv(ROOT / "experiments" / "variants.csv"))
    fac = pd.read_csv(ROOT / "data" / "raw" / "french" / "factors_daily.csv", parse_dates=["date"])
    t_rows, t_bt, t_b2, t_sel, t_kos = RB.training_inputs()
    with tempfile.TemporaryDirectory() as d:
        _, bases, trial = RB.build(t_rows, t_bt, t_b2, t_sel, t_kos, fac, Path(d), prefix="TRAIN.")
    rows = pd.read_parquet(ROOT / "results" / "holdout" / "strategy_a_rows.parquet")
    bt = pd.read_parquet(ROOT / "results" / "holdout" / "strategy_b_trades.parquet")
    pm = pd.read_csv(HR / "pm_map.csv")
    bg = pd.DataFrame({"game_id": pm["game_id"], "espn_kickoff": pm["kickoff"]})
    bg = bg[pd.to_datetime(bg["espn_kickoff"], utc=True) <= AB_CUTOFF]
    bg = bg[[(HR / "kalshi" / f"{g}.parquet").exists() and (HR / "polymarket" / f"{g}.parquet").exists()
             for g in bg["game_id"]]]
    kos = pd.concat([pd.Series(pd.to_datetime(rows["kickoff"], utc=True)),
                     pd.to_datetime(bg["espn_kickoff"], utc=True)], ignore_index=True)
    stored = json.loads(STORED.read_text())
    check = oos_dsr(22, rows, bt, kos, fac, bases, trial)
    for k, v in check.items():
        s = stored[k]["value"]
        assert abs(v - s) <= 1e-12 * max(1.0, abs(s)) or (s != 0 and abs(v / s - 1) < 1e-9), (k, v, s)
    new = oos_dsr(n_rows, rows, bt, kos, fac, bases, trial)
    hist = json.loads(OUT.read_text()).get("history", {}) if OUT.exists() else {}
    if OUT.exists() and not hist:                 # first run wrote no history: keep its line
        prev = json.loads(OUT.read_text())
        hist = {str(prev["n_trials"]): prev["values"]}
    hist[str(n_rows)] = new                       # earlier trial counts are kept, never overwritten
    out = {"n_trials": n_rows, "check_total_22_reproduced": check, "values": new,
           "stored_total_22": {k: stored[k]["value"] for k in check}, "history": hist}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
