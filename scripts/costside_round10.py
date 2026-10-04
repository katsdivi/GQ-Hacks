"""Post-hoc cost-side search, Round 10 (SPEC.md Round 10: Elo strength from past outcomes vs Kalshi; 4 trials).

post-hoc, exploratory; training only. Usage: PYTHONPATH=.:scripts python scripts/costside_round10.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import costside_common as C
import costside_round1 as R1

K_ELO = 20.0
HFA = {"CFB": 50.0, "NFL": 65.0}


def registry() -> list[dict]:
    r = [{"trial": f"R10.ELO.e{e}.{em}", "method": "Elo from past outcomes vs Kalshi pre-game",
          "params": f"e={e} exec={em} K=20 HFA=50/65", "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"}
         for e in (0.05, 0.10) for em in ("taker", "maker")]
    return [{**x, "round": 10} for x in r]


def elo_p(ra, rb, hfa):
    return 1.0 / (1.0 + 10 ** (-(ra + hfa - rb) / 400.0))


def main() -> None:
    games = sorted(C.load_games(), key=lambda g: g["kickoff_ns"])
    wk, hist = C.week_index(games)
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round10.csv", index=False)
    rating, n = {}, {}
    pending = []           # (settle_time, league, home, away, result_home)
    rows = []
    for g in games:
        t = g["kickoff_ns"] - 300 * C.NS
        # apply every result settled before t (kickoff + 6 h < t)
        keep = []
        for st, lg, h, a, res in pending:
            if st < t:
                ra, rb = rating.get((lg, h), 1500.0), rating.get((lg, a), 1500.0)
                exp = elo_p(ra, rb, HFA[lg])
                rating[(lg, h)] = ra + K_ELO * (res - exp)
                rating[(lg, a)] = rb - K_ELO * (res - exp)
                n[(lg, h)] = n.get((lg, h), 0) + 1
                n[(lg, a)] = n.get((lg, a), 0) + 1
            else:
                keep.append((st, lg, h, a, res))
        pending = keep
        lg, h, a = g["league"], g["home"], g["away"]
        ph = g["pay"][h]
        if wk[g["game_id"]] >= hist and n.get((lg, h), 0) >= 3 and n.get((lg, a), 0) >= 3:
            p_home = elo_p(rating[(lg, h)], rating[(lg, a)], HFA[lg])
            gaps = {}
            for team, p in ((h, p_home), (a, 1 - p_home)):
                ts, px = g["own"][team]
                i = np.searchsorted(ts, t, side="right") - 1
                if i >= 0 and t - ts[i] <= 600 * C.NS:
                    gaps[team] = p - float(px[i])
            if gaps:
                team = max(gaps, key=gaps.get)
                pay = g["pay"][team]
                for e in (0.05, 0.10):
                    if gaps[team] < e - 1e-9 or pay != pay:
                        continue
                    ts, px = g["own"][team]
                    for em in ("taker", "maker"):
                        if em == "taker":
                            f = C.taker_entry(ts, px, t, 300)
                            fe = (C.fee_taker(f[1]), C.fee_taker(f[1])) if f else None
                        else:
                            last = C.asof(ts, px, t)
                            f = C.maker_entry(ts, px, t, last, 300) if last == last else None
                            fe = (C.fee_maker175(f[1]), 0.0) if f else None
                        if f:
                            rows.append(R1.row(f"R10.ELO.e{e}.{em}", g, team, t, f[1], fe[0], fe[1], pay,
                                               extra={"week": wk[g["game_id"]], "gap": gaps[team]}))
        if ph == ph:
            pending.append((g["kickoff_ns"] + 6 * 3600 * C.NS, lg, h, a, float(ph)))
    pd.DataFrame(rows).to_parquet(C.CACHE / "trades_round10.parquet")
    print("rows", len(rows))


if __name__ == "__main__":
    sys.exit(main())
