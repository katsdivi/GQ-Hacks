"""Post-hoc cost-side search, Round 5 (SPEC.md Round 5: PAIRPRE, SL, ANCHOR; 7 trials).

post-hoc, exploratory; training only. Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/costside_round5.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import costside_common as C
import costside_round1 as R1
import costside_round4 as R4


def registry() -> list[dict]:
    r = [{"trial": f"R5.PAIRPRE.h{h}", "method": "pre-game passive pairs, taker hedge of orphans",
          "params": f"h={h} W=900s slots ko-2h..ko-15min", "cost_line": "maker175 + taker (alt maker0)"}
         for h in (0.01, 0.02)]
    r += [{"trial": f"R5.SL.{s}.sl{sl}", "method": "stop-loss exit", "params": f"entries={s} sl={sl}",
           "cost_line": "maker175 entry + taker exit (alt maker0)"}
          for s in ("R2.VOL.low.maker", "R1.A.I12.A1.W300") for sl in (0.10, 0.20)]
    r += [{"trial": "R5.ANCHOR", "method": "polymarket.com-anchored one-sided maker quote",
           "params": "gap>=0.03 slots 5min W=300s first fill per game", "cost_line": "maker175 (alt maker0)"}]
    assert len(r) == 7
    return [{**x, "round": 5} for x in r]


def pairpre(games, wk, hist):
    out = []
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        ko = g["kickoff_ns"]
        for t in range(ko - 2 * 3600 * C.NS, ko - 15 * 60 * C.NS + 1, 900 * C.NS):
            for h in (0.01, 0.02):
                r = R4.slot_pnl(g, t, h, False)
                if r:
                    out.append({**r, "trial": f"R5.PAIRPRE.h{h}", "week": wk[g["game_id"]]})
    return out


def sl_rows(games):
    gi = {g["game_id"]: g for g in games}
    old = pd.concat([pd.read_parquet(C.CACHE / "trades_round1.parquet"), pd.read_parquet(C.CACHE / "trades_round2.parquet")])
    out = []
    for s, w in (("R2.VOL.low.maker", 60), ("R1.A.I12.A1.W300", 300)):
        for r in old[old.trial == s].itertuples():
            g = gi[r.game_id]
            ts, px = g["own"][r.team]
            last = C.asof(ts, px, r.t_ns)
            f = C.maker_entry(ts, px, r.t_ns, last, w)
            assert f is not None and abs(f[1] - r.entry) < 1e-9, "fill must reproduce"
            fill_ts, e = f
            i = np.searchsorted(ts, fill_ts, side="right")
            for sl in (0.10, 0.20):
                hit = np.flatnonzero(px[i:] <= e - sl + 1e-9)
                fm = C.fee_maker175(e)
                if len(hit):
                    xp = max(round(px[i + hit[0]] - 0.01, 4), 0.01)
                    fx = C.fee_taker(xp)
                    pnl, pnl0, pay = (xp - e) * C.QTY - fm - fx, (xp - e) * C.QTY - fx, np.nan
                else:
                    pnl, pnl0, pay = (r.payout - e) * C.QTY - fm, (r.payout - e) * C.QTY, r.payout
                out.append({"trial": f"R5.SL.{s}.sl{sl}", "game_id": r.game_id, "t_ns": r.t_ns, "day": r.day,
                            "entry": e, "fee_entry": fm, "payout": pay, "pnl": round(pnl, 6), "cap": e * C.QTY + fm,
                            "pnl_alt": round(pnl0, 6), "cap_alt": e * C.QTY})
    return out


def anchor(games, wk, hist):
    out = []
    for g in games:
        if g["pm"] is None or wk[g["game_id"]] < hist:
            continue
        pts, ppx = g["pm"]
        ko = g["kickoff_ns"]
        done = False
        for t in range(ko + 20 * 60 * C.NS, ko + 4 * 3600 * C.NS, 300 * C.NS):
            i = np.searchsorted(pts, t, side="right") - 1
            if i < 0 or t - pts[i] > 60 * C.NS:
                continue
            for team, fair in ((g["home"], ppx[i]), (g["away"], 1 - ppx[i])):
                ts, px = g["own"][team]
                last = C.asof(ts, px, t)
                if last != last or fair < last + 0.03 - 1e-9:
                    continue
                f = C.maker_entry(ts, px, t, last, 300)
                pay = g["pay"][team]
                if f and pay == pay:
                    out.append(R1.row("R5.ANCHOR", g, team, t, f[1], C.fee_maker175(f[1]), 0.0, pay,
                                      extra={"week": wk[g["game_id"]]}))
                    done = True
                    break
            if done:
                break
    return out


def main() -> None:
    games = C.load_games()
    wk, hist = C.week_index(games)
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round5.csv", index=False)
    rows = pairpre(games, wk, hist)
    d = pd.DataFrame(rows)
    if len(d):
        print(d.groupby(["trial", "legs"]).pnl.agg(["count", "sum"]).round(2), flush=True)
    rows += sl_rows(games)
    rows += anchor(games, wk, hist)
    pd.DataFrame(rows).to_parquet(C.CACHE / "trades_round5.parquet")


if __name__ == "__main__":
    sys.exit(main())
