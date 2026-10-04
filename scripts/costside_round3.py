"""Post-hoc cost-side search, Round 3 (SPEC.md Round 3: PAIR, FEE, FAV, VOLX; 11 trials).

post-hoc, exploratory; training only. Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/costside_round3.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import costside_common as C
import costside_round1 as R1
import costside_round2 as R2


def registry() -> list[dict]:
    r = [{"trial": f"R3.PAIR.{m}", "method": "passive both-side pairs, orphan handling", "params": f"orphan={m} h=0.02 W=900s slots=15min",
          "cost_line": "maker175 maker legs + taker (alt maker0)"} for m in ("HEDGENOW", "HEDGEDL", "CUT")]
    r += [{"trial": f"R3.FEE.{s}", "method": "100-contract order fee rounding", "params": f"fills of {s}",
           "cost_line": "maker175 per 100 (alt maker0)"} for s in ("R2.VOL.low.maker", "R1.A.A.A1.W300",
                                                               "R1.C1.d0.05.s15.maker.settle")]
    r += [{"trial": "R3.FAV", "method": "favourite 0.80-0.90 at kickoff - 5 min, maker", "params": "limit=last W=300s",
           "cost_line": "maker175 (alt maker0)"}]
    r += [{"trial": f"R3.VOLX.{s}.{rg}", "method": "calm-market filter on maker signal", "params": f"signal={s} regime={rg}",
           "cost_line": "maker175 (alt maker0)"} for s in ("I12", "I9") for rg in ("low", "high")]
    assert len(r) == 11
    return [{**x, "round": 3} for x in r]


def pair_rows(games, wk, hist):
    out, orphans = [], []
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        h, a = g["home"], g["away"]
        ko = g["kickoff_ns"]
        for t in range(ko + 20 * 60 * C.NS, ko + 4 * 3600 * C.NS, 900 * C.NS):
            fills = {}
            for team in (h, a):
                ts, px = g["own"][team]
                last = C.asof(ts, px, t)
                if last != last:
                    continue
                f = C.maker_entry(ts, px, t, round(last - 0.02, 4), 900)
                if f:
                    fills[team] = f
            if not fills:
                continue
            pays = {x: g["pay"][x] for x in (h, a)}
            if any(v != v for v in pays.values()):
                continue
            for mode in ("HEDGENOW", "HEDGEDL", "CUT"):
                pnl = pnl0 = cap = cap0 = 0.0
                for team, (fts, e) in fills.items():
                    fm, f0 = C.fee_maker175(e), 0.0
                    pnl += (pays[team] - e) * C.QTY - fm
                    pnl0 += (pays[team] - e) * C.QTY - f0
                    cap += e * C.QTY + fm
                    cap0 += e * C.QTY
                if len(fills) == 1:
                    (team, (fts, e)), = fills.items()
                    other = a if team == h else h
                    if mode == "CUT":
                        ts, px = g["own"][team]
                        ex = C.exit_at(ts, px, t, 900)
                        if ex is not None:
                            adj = (ex[1] - pays[team]) * C.QTY - C.fee_taker(ex[1])
                            pnl += adj
                            pnl0 += adj
                    else:
                        ots, opx = g["own"][other]
                        t0 = fts if mode == "HEDGENOW" else t + 900 * C.NS - C.NS
                        hf = C.taker_entry(ots, opx, t0, 60)
                        if hf is not None:
                            ft = C.fee_taker(hf[1])
                            adj = (pays[other] - hf[1]) * C.QTY - ft
                            pnl += adj
                            pnl0 += adj
                            cap += hf[1] * C.QTY + ft
                            cap0 += hf[1] * C.QTY + ft
                    if mode == "HEDGENOW":
                        orphans.append({"game_id": g["game_id"], "fill": e, "payout": pays[team]})
                out.append({"trial": f"R3.PAIR.{mode}", "game_id": g["game_id"], "t_ns": t, "day": C.et_date(t),
                            "pnl": round(pnl, 6), "cap": cap, "pnl_alt": round(pnl0, 6), "cap_alt": cap0,
                            "payout": np.nan, "legs": len(fills), "week": wk[g["game_id"]]})
    return out, pd.DataFrame(orphans)


def fee_rows():
    old = pd.concat([pd.read_parquet(C.CACHE / "trades_round1.parquet"), pd.read_parquet(C.CACHE / "trades_round2.parquet")])
    out = []
    for s in ("R2.VOL.low.maker", "R1.A.A.A1.W300", "R1.C1.d0.05.s15.maker.settle"):
        d = old[old.trial == s]
        for r in d.itertuples():
            f100 = C.fee_maker175(r.entry, 100) / 10
            out.append({"trial": f"R3.FEE.{s}", "game_id": r.game_id, "t_ns": r.t_ns, "day": r.day, "entry": r.entry,
                        "fee_entry": f100, "payout": r.payout, "pnl": round((r.payout - r.entry) * C.QTY - f100, 6),
                        "cap": r.entry * C.QTY + f100, "pnl_alt": round((r.payout - r.entry) * C.QTY, 6),
                        "cap_alt": r.entry * C.QTY})
    return out


def fav_rows(games, wk, hist):
    out = []
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        t = g["kickoff_ns"] - 300 * C.NS
        for team in (g["home"], g["away"]):
            ts, px = g["own"][team]
            i = np.searchsorted(ts, t, side="right") - 1
            if i < 0 or t - ts[i] > 600 * C.NS or not (0.80 <= px[i] < 0.90):
                continue
            pay = g["pay"][team]
            f = C.maker_entry(ts, px, t, float(px[i]), 300)
            if f and pay == pay:
                out.append(R1.row("R3.FAV", g, team, t, f[1], C.fee_maker175(f[1]), 0.0, pay,
                                  extra={"week": wk[g["game_id"]]}))
    return out


def volx_rows(games, wk, hist):
    gi = {g["game_id"]: g for g in games}
    sig = R1.load_signals()
    out = []
    for name, lim in (("I12", "A1"), ("I9", "A2")):
        rows = []
        for r in sig[sig.sig == name].itertuples():
            g = gi.get(r.game_id)
            if g is None or r.team not in g["own"]:
                continue
            rows.append((g, r.team, r.t_ns, wk[g["game_id"]], R2.kvol(g, r.t_ns)))
        sv = pd.DataFrame([(x[3], x[4]) for x in rows], columns=["week", "v"])
        for g, team, t, w, v in rows:
            if w < hist:
                continue
            past = sv[sv.week < w]["v"]
            if past.empty:
                continue
            rg = "high" if v > past.median() else "low"
            ts, px = g["own"][team]
            last = C.asof(ts, px, t)
            pay = g["pay"][team]
            if last != last or pay != pay:
                continue
            f = C.maker_entry(ts, px, t, round(last - (0.01 if lim == "A2" else 0), 4), 300)
            if f:
                out.append(R1.row(f"R3.VOLX.{name}.{rg}", g, team, t, f[1], C.fee_maker175(f[1]), 0.0, pay,
                                  extra={"week": w}))
    return out


def main() -> None:
    games = C.load_games()
    wk, hist = C.week_index(games)
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round3.csv", index=False)
    rows, orph = pair_rows(games, wk, hist)
    print("PAIR", len(rows), flush=True)
    if len(orph):
        print(f"orphans {len(orph)}: win rate {orph.payout.mean():.3f} vs mean fill {orph.fill.mean():.3f}", flush=True)
        orph.to_parquet(C.CACHE / "orphans_round3.parquet")
    rows += fee_rows()
    rows += fav_rows(games, wk, hist)
    rows += volx_rows(games, wk, hist)
    print("total", len(rows), flush=True)
    pd.DataFrame(rows).to_parquet(C.CACHE / "trades_round3.parquet")


if __name__ == "__main__":
    sys.exit(main())
