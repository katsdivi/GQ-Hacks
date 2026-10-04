"""Wilson 95% CIs and the preset placebo-design rule from the per-rep sim rows (synthetic only).
Run: python tests/sim_wilson.py docs/results/sim/b/placebo_design_reps.csv
Writes placebo_design_wilson.csv next to the input and prints the rule verdict.
Rule (fixed before the run): Design 2 only if its full-rule false-positive Wilson upper bound <= 6% at every n
under BOTH the zero-lag null ("zero") and the shared-shift null ("shift_iid"), both venues; else Design 1."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

Z = 1.959964


def wilson(k: int, n: int) -> tuple[float, float]:
    p = k / n
    d = 1 + Z * Z / n
    c, h = (p + Z * Z / (2 * n)) / d, Z * np.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def table(r: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (v, s, n, d), g in r.groupby(["venue", "scenario", "n", "design"]):
        out = {"venue": v, "scenario": s, "n": n, "design": d, "reps": len(g), "n_placebo_median": int(g.n_placebo.median())}
        for col, name in (("kalshi", "kalshi_leads"), ("reverse", "other_leads"), ("mw_sig", "mw_p_lt_0.05")):
            k = int(g[col].sum())
            lo, hi = wilson(k, len(g))
            out.update({f"{name}_k": k, f"{name}_rate": k / len(g), f"{name}_lo": lo, f"{name}_hi": hi})
        rows.append(out)
    return pd.DataFrame(rows)


def verdict(t: pd.DataFrame) -> str:
    d2 = t[(t.design == "D2") & t.scenario.isin(["zero", "shift_iid"])]
    return "Design 2" if (d2.kalshi_leads_hi <= 0.06).all() else "Design 1"


if __name__ == "__main__":
    src = Path(sys.argv[1])
    r = pd.read_csv(src)
    r["mw_sig"] = r["mw_p"] < 0.05
    t = table(r)
    t.to_csv(src.with_name("placebo_design_wilson.csv"), index=False)
    for v in sorted(t.venue.unique()):
        print(v, "alone:", verdict(t[t.venue == v]))
    print("both venues (rule as applied):", verdict(t))
