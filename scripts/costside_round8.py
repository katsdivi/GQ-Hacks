"""Post-hoc cost-side search, Round 8 (SPEC.md Round 8: team prior from past Kalshi closing errors; 6 trials).

post-hoc, exploratory; training only. Usage: PYTHONPATH=.:scripts python scripts/costside_round8.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import costside_common as C
import costside_round1 as R1

CONFIGS = [(1, "taker"), (3, "taker"), (3, "maker")]


def registry() -> list[dict]:
    r = [{"trial": f"R8.PRIOR.{d}.k{k}.{em}", "method": "team prior from past Kalshi closing errors",
          "params": f"{d} |prior|>=0.10 k={k} exec={em}", "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"}
         for d in ("under", "over") for k, em in CONFIGS]
    return [{**x, "round": 8} for x in r]


def closing_errors(games) -> pd.DataFrame:
    rows = []
    for g in games:
        ko = g["kickoff_ns"]
        for team in (g["home"], g["away"]):
            ts, px = g["own"][team]
            i = np.searchsorted(ts, ko, side="right") - 1
            pay = g["pay"][team]
            if i < 0 or ko - ts[i] > 600 * C.NS or pay != pay:
                continue
            rows.append({"league": g["league"], "team": team, "ko": ko, "err": pay - float(px[i])})
    return pd.DataFrame(rows).sort_values("ko")


def prior(err: pd.DataFrame, league, team, t, k) -> float:
    x = err[(err.league == league) & (err.team == team) & (err.ko + 6 * 3600 * C.NS < t)]
    return float(x.err.tail(k).mean()) if len(x) >= k else np.nan


def main() -> None:
    games = C.load_games()
    wk, hist = C.week_index(games)
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round8.csv", index=False)
    err = closing_errors(games)
    rows = []
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        t = g["kickoff_ns"] - 300 * C.NS
        for k, em in CONFIGS:
            pr = {tm: prior(err, g["league"], tm, t, k) for tm in (g["home"], g["away"])}
            under = [(v, tm) for tm, v in pr.items() if v == v and v >= 0.10 - 1e-9]
            over = [(v, tm) for tm, v in pr.items() if v == v and v <= -0.10 + 1e-9]
            picks = {}
            if under:
                picks["under"] = max(under)[1]
            if over:
                tm = min(over)[1]
                picks["over"] = g["away"] if tm == g["home"] else g["home"]
            for d, team in picks.items():
                ts, px = g["own"][team]
                pay = g["pay"][team]
                if pay != pay:
                    continue
                if em == "taker":
                    f = C.taker_entry(ts, px, t, 300)
                    fe, f0 = (C.fee_taker(f[1]), C.fee_taker(f[1])) if f else (0, 0)
                else:
                    last = C.asof(ts, px, t)
                    f = C.maker_entry(ts, px, t, last, 300) if last == last else None
                    fe, f0 = (C.fee_maker175(f[1]), 0.0) if f else (0, 0)
                if f:
                    rows.append(R1.row(f"R8.PRIOR.{d}.k{k}.{em}", g, team, t, f[1], fe, f0, pay,
                                       extra={"week": wk[g["game_id"]]}))
    pd.DataFrame(rows).to_parquet(C.CACHE / "trades_round8.parquet")
    print("rows", len(rows))


if __name__ == "__main__":
    sys.exit(main())
