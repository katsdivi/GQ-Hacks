"""Descriptive check of the N (no-signal) maker on polymarket.com from the committed posthoc-mm-signal run (b346230).

descriptive, post-hoc, not pre-registered, one day. No new parameters, no new strategy. Reads the per-fill rows
written by that run (data/mm_cache/fills.parquet, gitignored) and first verifies they reproduce results.csv
(N fills 428, P&L +60 s 46.53); otherwise it stops.

Usage (cwd = repo root): python scripts/posthoc_mm_signal_n_check.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED, NBOOT = 20261004, 2000
OUT = Path("results/posthoc_mm_signal")


def boot_pc(g: pd.DataFrame, col: str):
    p, q = g[col].to_numpy(float), g["qty"].to_numpy(float)
    est = p.sum() / q.sum()
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(p), (NBOOT, len(p)))
    bs = p[idx].sum(1) / q[idx].sum(1)
    return float(est), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main() -> None:
    F = pd.read_parquet("data/mm_cache/fills.parquet")
    n = F[(F.venue == "polymarket.com") & (F.maker == "N")].copy()
    res = pd.read_csv(OUT / "results.csv")
    r = res[(res.venue == "polymarket.com")].iloc[0]
    assert len(n) == 428 == int(r.N_fills), "fill count does not match results.csv"
    assert round(n.pnl60.sum(), 2) == round(float(r.N_pnl60), 2) == 46.53, "P&L +60 s does not match results.csv"
    n["adverse60"] = n["as60"] * n["qty"]                 # side x (mid(t+60) - mid before fill) x qty
    n["spread"] = n["pnl60"] - n["adverse60"]             # side x (mid before fill - price) x qty (fee 0)
    nan = int(n[["pnl60", "as60"]].isna().any(axis=1).sum())
    g = n.groupby("game")[["pnl60", "pnlset", "qty", "spread", "adverse60"]].sum()
    out = {"label": "descriptive, post-hoc, not pre-registered, one day",
           "source": "posthoc-mm-signal b346230, data/mm_cache/fills.parquet (verified: 428 fills, +60 s $46.53)",
           "fills": len(n), "contracts": float(n.qty.sum()), "games_with_fills": len(g), "games_in_run": 88,
           "fills_with_nan_mark": nan}
    for col in ("pnl60", "pnlset"):
        e, lo, hi = boot_pc(g, col)
        out[f"{col}_c_per_contract"] = [round(100 * e, 3), round(100 * lo, 3), round(100 * hi, 3)]
        top5 = g[col].sort_values(ascending=False).index[:5]
        ge, glo, ghi = boot_pc(g.drop(top5), col)
        out[f"{col}_excl_top5_c_per_contract"] = [round(100 * ge, 3), round(100 * glo, 3), round(100 * ghi, 3)]
        out[f"{col}_share_games_positive"] = round(float((g[col] > 0).mean()), 3)
        out[f"{col}_share_games_positive_of_88"] = round(float((g[col] > 0).sum() / 88), 3)
        out[f"{col}_breakeven_maker_fee_c_per_contract"] = round(100 * float(g[col].sum() / g["qty"].sum()), 3)
    both = n[n.pnl60.notna() & n.as60.notna()]
    q = both.qty.sum()
    n = both
    out["split_note"] = ("split uses fills with both a mid just before the fill and a mid at +60 s; "
                         f"{int(F[(F.venue == 'polymarket.com') & (F.maker == 'N')].pnl60.isna().sum())} fills have no +60 s mid "
                         "(excluded from the +60 s P&L in the committed run too) and 2 more have no pre-fill mid "
                         "(their +60 s P&L, -$1.00, is in the $46.53 but not in the split)")
    out["split_fills"] = len(both)
    out["spread_captured_usd"] = round(float(n.spread.sum()), 2)
    out["spread_captured_c_per_contract"] = round(100 * float(n.spread.sum() / q), 3)
    out["mark_to_mid_60s_usd"] = round(float(n.adverse60.sum()), 2)
    out["mark_to_mid_60s_c_per_contract"] = round(100 * float(n.adverse60.sum() / q), 3)
    out["maker_fee"] = ("0, no rebate: Gamma market metadata cached by posthoc-idea11 (wt-idea11/data/pm_resolution/"
                        "<condition>.json, 84 of 84 markets) has feeType zero_fees, feeSchedule rate 0, rebateRate 0, "
                        "takerOnly true. The same files also carry makerBaseFee 1000 and takerBaseFee 1000, whose meaning "
                        "is not documented in the repo; under feeType zero_fees they are read as inactive.")
    (OUT / "n_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
