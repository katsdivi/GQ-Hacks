"""Post-hoc cost-side search, Round 4 (SPEC.md Round 4: PAIRCALM h 0.02/0.03, REQUOTE, REQUOTECALM; 4 trials).

post-hoc, exploratory; training only. Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/costside_round4.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import costside_common as C
import costside_round2 as R2


def registry() -> list[dict]:
    r = [{"trial": f"R4.PAIRCALM.h{h}", "method": "passive pairs in calm slots, taker hedge of orphans",
          "params": f"h={h} W=900s calm=walk-forward median", "cost_line": "maker175 + taker (alt maker0)"}
         for h in (0.02, 0.03)]
    r += [{"trial": "R4.REQUOTE", "method": "passive pairs, passive orphan completion then taker hedge",
           "params": "h=0.02 L2=min(0.99-e1, other last)", "cost_line": "maker175 + taker (alt maker0)"},
          {"trial": "R4.REQUOTECALM", "method": "R4.REQUOTE in calm slots", "params": "h=0.02 calm",
           "cost_line": "maker175 + taker (alt maker0)"}]
    return [{**x, "round": 4} for x in r]


def slots(g):
    ko = g["kickoff_ns"]
    return range(ko + 20 * 60 * C.NS, ko + 4 * 3600 * C.NS, 900 * C.NS)


def calm_flags(games, wk):
    rows = [(g["game_id"], t, wk[g["game_id"]], R2.kvol(g, t)) for g in games for t in slots(g)]
    d = pd.DataFrame(rows, columns=["game_id", "t", "week", "v"])
    med = {w: d[d.week < w]["v"].median() for w in sorted(d.week.unique())}
    d["calm"] = [v <= med[w] if med[w] == med[w] else False for v, w in zip(d.v, d.week)]
    return {(a, b): c for a, b, c in zip(d.game_id, d.t, d.calm)}


def slot_pnl(g, t, h, requote):
    hm, aw = g["home"], g["away"]
    fills = {}
    for team in (hm, aw):
        ts, px = g["own"][team]
        last = C.asof(ts, px, t)
        if last != last:
            continue
        f = C.maker_entry(ts, px, t, round(last - h, 4), 900)
        if f:
            fills[team] = f
    if not fills:
        return None
    pays = {x: g["pay"][x] for x in (hm, aw)}
    if any(v != v for v in pays.values()):
        return None
    if len(fills) == 1 and requote:
        (team, (f1, e1)), = fills.items()
        other = aw if team == hm else hm
        ots, opx = g["own"][other]
        lo = C.asof(ots, opx, f1)
        if lo == lo:
            l2 = round(min(0.99 - e1, lo), 4)
            # passive completion: only trades after f1 + 1 s and up to t + 900 s
            rem = (t + 900 * C.NS - f1) / C.NS
            f2 = C.maker_entry(ots, opx, f1, l2, rem) if rem > 1 else None
            if f2:
                fills[other] = f2
    pnl = pnl0 = cap = cap0 = 0.0
    for team, (_, e) in fills.items():
        fm = C.fee_maker175(e)
        pnl += (pays[team] - e) * C.QTY - fm
        pnl0 += (pays[team] - e) * C.QTY
        cap += e * C.QTY + fm
        cap0 += e * C.QTY
    if len(fills) == 1:
        (team, (f1, e1)), = fills.items()
        other = aw if team == hm else hm
        ots, opx = g["own"][other]
        t0 = (t + 900 * C.NS - C.NS) if requote else f1
        hf = C.taker_entry(ots, opx, t0, 60)
        if hf is not None:
            ft = C.fee_taker(hf[1])
            pnl += (pays[other] - hf[1]) * C.QTY - ft
            pnl0 += (pays[other] - hf[1]) * C.QTY - ft
            cap += hf[1] * C.QTY + ft
            cap0 += hf[1] * C.QTY + ft
    return {"game_id": g["game_id"], "t_ns": t, "day": C.et_date(t), "pnl": round(pnl, 6), "cap": cap,
            "pnl_alt": round(pnl0, 6), "cap_alt": cap0, "payout": np.nan, "legs": len(fills)}


def main() -> None:
    games = C.load_games()
    wk, hist = C.week_index(games)
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round4.csv", index=False)
    calm = calm_flags(games, wk)
    rows = []
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        for t in slots(g):
            c = calm.get((g["game_id"], t), False)
            for trial, h, rq, need_calm in (("R4.PAIRCALM.h0.02", 0.02, False, True),
                                            ("R4.PAIRCALM.h0.03", 0.03, False, True),
                                            ("R4.REQUOTE", 0.02, True, False), ("R4.REQUOTECALM", 0.02, True, True)):
                if need_calm and not c:
                    continue
                r = slot_pnl(g, t, h, rq)
                if r:
                    rows.append({**r, "trial": trial, "week": wk[g["game_id"]]})
    d = pd.DataFrame(rows)
    print(d.groupby(["trial", "legs"]).pnl.agg(["count", "sum"]).round(2), flush=True)
    d.to_parquet(C.CACHE / "trades_round4.parquet")


if __name__ == "__main__":
    sys.exit(main())
