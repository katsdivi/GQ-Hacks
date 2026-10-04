"""Post-hoc cost-side search, Round 9 (SPEC.md Round 9: independent filters on the two best maker signals; 5 trials).

post-hoc, exploratory; training only. Usage: PYTHONPATH=.:scripts python scripts/costside_round9.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import costside_common as C
import costside_round6 as R6
import costside_round7 as R7
import costside_round8 as R8


def registry() -> list[dict]:
    r = [{"trial": f"R9.VOLLOW.{f}", "method": "R2.VOL.low.maker + independent filter", "params": f"filter={f}",
          "cost_line": "maker175 (alt maker0)"} for f in ("prior", "espncalm", "imb", "regular")]
    r += [{"trial": "R9.PRIOR.pm", "method": "R8.PRIOR.over.k3.maker + polymarket.com agreement",
           "params": "pm price >= Kalshi last at t", "cost_line": "maker175 (alt maker0)"}]
    return [{**x, "round": 9} for x in r]


def main() -> None:
    games = C.load_games()
    gi = {g["game_id"]: g for g in games}
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round9.csv", index=False)
    vol = pd.read_parquet(C.CACHE / "trades_round2.parquet")
    vol = vol[vol.trial == "R2.VOL.low.maker"]
    pri = pd.read_parquet(C.CACHE / "trades_round8.parquet")
    pri = pri[pri.trial == "R8.PRIOR.over.k3.maker"]
    err = R8.closing_errors(games)
    ids = pd.read_csv(R7.ESPN / "ids_training.csv").drop_duplicates("game_id").set_index("game_id")
    out = []
    espn_cache = {}
    for r in vol.itertuples():
        g = gi[r.game_id]
        base = r._asdict()
        base.pop("Index")
        p = R8.prior(err, g["league"], r.team, r.t_ns, 3)
        if p != p or p >= 0:
            out.append({**base, "trial": "R9.VOLLOW.prior"})
        if r.game_id not in espn_cache:
            idrow = ids.loc[r.game_id].copy()
            e = None
            if idrow["espn_id"] == idrow["espn_id"]:
                idrow["espn_id"] = int(float(idrow["espn_id"]))
                e = R7.load_espn(g, idrow, {"no summary": 0, "mapping": 0, "defect": 0, "ok": 0})
            espn_cache[r.game_id] = e
        e = espn_cache[r.game_id]
        if e is not None:
            evts = [R7.ns(p["wallclock"]) for p in e["plays"] if p.get("scoringPlay")]
            for dr in e["drives"]:
                if dr.get("result") in R7.TO_RESULTS and dr.get("plays"):
                    w = [p for p in dr["plays"] if p.get("wallclock")]
                    if w:
                        evts.append(R7.ns(w[-1]["wallclock"]))
            if not any(r.t_ns - 120 * C.NS <= x <= r.t_ns for x in evts):
                out.append({**base, "trial": "R9.VOLLOW.espncalm"})
        ts, px, sz, sg = R6.micro(r.game_id)
        j0, j1 = np.searchsorted(ts, r.t_ns - 60 * C.NS, side="left"), np.searchsorted(ts, r.t_ns, side="right")
        tot = sz[j0:j1].sum()
        I = (sz[j0:j1] * sg[j0:j1]).sum() / tot if tot > 0 else 0.0
        dirn = 1 if r.team == g["home"] else -1
        if tot < 500 or I * dirn >= -0.5:
            out.append({**base, "trial": "R9.VOLLOW.imb"})
        d = pd.Timestamp(r.t_ns, unit="ns", tz="UTC").tz_convert("America/New_York").date()
        cut = pd.Timestamp("2025-12-13").date() if g["league"] == "CFB" else pd.Timestamp("2026-01-10").date()
        if d < cut:
            out.append({**base, "trial": "R9.VOLLOW.regular"})
    for r in pri.itertuples():
        g = gi[r.game_id]
        if g["pm"] is None:
            continue
        pts, ppx = g["pm"]
        i = np.searchsorted(pts, r.t_ns, side="right") - 1
        if i < 0 or r.t_ns - pts[i] > 600 * C.NS:
            continue
        pm_team = ppx[i] if r.team == g["home"] else 1 - ppx[i]
        ts, px = g["own"][r.team]
        last = C.asof(ts, px, r.t_ns)
        if last == last and pm_team >= last - 1e-9:
            base = r._asdict()
            base.pop("Index")
            out.append({**base, "trial": "R9.PRIOR.pm"})
    d = pd.DataFrame(out)
    print(d.trial.value_counts())
    d.to_parquet(C.CACHE / "trades_round9.parquet")


if __name__ == "__main__":
    sys.exit(main())
