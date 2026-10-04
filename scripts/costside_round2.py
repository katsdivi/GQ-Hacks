"""Post-hoc cost-side search, Round 2 (SPEC.md Round 2: ARB, CONS, VOL, TP; 16 trials).

post-hoc, exploratory; training only. Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/costside_round2.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

import costside_common as C
import costside_round1 as R1

SEARCH_TRADES = "../wt-search/results/posthoc_search/trades.csv"


def registry() -> list[dict]:
    r = [{"trial": f"R2.ARB.S{s}", "method": "Kalshi two-market complement arbitrage", "params": f"S<={s}",
          "cost_line": "taker"} for s in (0.95, 0.97)]
    r += [{"trial": f"R2.CONS.{l}.W{w}", "method": "search 2-leg pre-game consensus + maker",
           "params": f"limit={l} W={w}", "cost_line": "maker175 (alt maker0)"} for l in ("A1", "A2") for w in (60, 300)]
    r += [{"trial": f"R2.VOL.{rg}.{em}", "method": "polymarket.com lead by Kalshi vol regime (walk-forward median)",
           "params": f"regime={rg} exec={em} d=0.05 s=15 settle",
           "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"} for rg in ("low", "high")
          for em in ("taker", "maker")]
    r += [{"trial": f"R2.TP.{e}.tp{tp}", "method": "take-profit exit", "params": f"entry={e} tp={tp} stop=60min",
           "cost_line": "maker175 (alt maker0)"} for e in ("I12", "I9", "C1") for tp in (0.03, 0.06)]
    assert len(r) == 16
    return [{**x, "round": 2} for x in r]


def arb(games, wk, hist):
    out = []
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        h, a = g["home"], g["away"]
        hts, hpx = g["own"][h]
        ats, apx = g["own"][a]
        if len(hts) == 0 or len(ats) == 0:
            continue
        t_all = np.union1d(hts, ats)
        ih = np.searchsorted(hts, t_all, side="right") - 1
        ia = np.searchsorted(ats, t_all, side="right") - 1
        ok = (ih >= 0) & (ia >= 0)
        t_all, ih, ia = t_all[ok], ih[ok], ia[ok]
        fresh = (t_all - hts[ih] <= 10 * C.NS) & (t_all - ats[ia] <= 10 * C.NS)
        tot = hpx[ih] + apx[ia]
        for s in (0.95, 0.97):
            hit = np.flatnonzero(fresh & (tot <= s + 1e-9))
            if len(hit) == 0:
                continue
            t = int(t_all[hit[0]])
            legs = []
            for team, (ts, px) in ((h, (hts, hpx)), (a, (ats, apx))):
                f = C.taker_entry(ts, px, t, 60)
                pay = g["pay"][team]
                if f and pay == pay:
                    legs.append(R1.row(f"R2.ARB.S{s}", g, team, t, f[1], C.fee_taker(f[1]), C.fee_taker(f[1]), pay,
                                       extra={"week": wk[g["game_id"]], "legs_filled": None}))
            for x in legs:
                x["legs_filled"] = len(legs)
            out += legs
    return out


def cons(games, wk, hist):
    gi = {g["game_id"]: g for g in games}
    d = pd.read_csv(SEARCH_TRADES)
    d = d[d.trial == "a_consensus_m2_pre_hyp"].sort_values("t_ns").groupby("game_id").tail(1)
    out = []
    for r in d.itertuples():
        g = gi.get(r.game_id)
        if g is None or wk[g["game_id"]] < hist or r.team not in g["own"]:
            continue
        ts, px = g["own"][r.team]
        last = C.asof(ts, px, int(r.t_ns))
        pay = g["pay"][r.team]
        if last != last or pay != pay:
            continue
        for lim in ("A1", "A2"):
            for w in (60, 300):
                f = C.maker_entry(ts, px, int(r.t_ns), round(last - (0.01 if lim == "A2" else 0), 4), w)
                if f:
                    out.append(R1.row(f"R2.CONS.{lim}.W{w}", g, r.team, int(r.t_ns), f[1], C.fee_maker175(f[1]),
                                      0.0, pay, extra={"week": wk[g["game_id"]]}))
    return out


def kvol(g, t):
    kts, kpx = g["kph"]
    i0, i1 = np.searchsorted(kts, t - 600 * C.NS, side="left"), np.searchsorted(kts, t, side="right")
    x = kpx[i0:i1]
    return float(np.abs(np.diff(x)).sum()) if len(x) > 1 else 0.0


def vol(games, wk, hist):
    sigs = []
    for g in games:
        if g["pm"] is None:
            continue
        for t, dirn in R1.c1_signals(g, 0.05, 15):
            sigs.append((g, t, dirn, wk[g["game_id"]], kvol(g, t)))
    sv = pd.DataFrame([(s[3], s[4]) for s in sigs], columns=["week", "v"])
    out = []
    by_game = {}
    for g, t, dirn, w, v in sigs:
        if w < hist:
            continue
        past = sv[sv.week < w]["v"]
        if past.empty:
            continue
        rg = "high" if v > past.median() else "low"
        by_game.setdefault((g["game_id"], rg), (g, []))[1].append((t, dirn))
    for (gid, rg), (g, ss) in by_game.items():
        team_of = lambda dirn, g=g: g["home"] if dirn > 0 else g["away"]
        for em in ("taker", "maker"):
            out += R1.run_sequential(g, sorted(ss), team_of, f"R2.VOL.{rg}.{em}", em, None,
                                     {"week": wk[g["game_id"]]})
    return out


def tp_exit(ts, px, fill_ts, entry, tp):
    lo, hi = fill_ts + 1, fill_ts + 3600 * C.NS
    i, j = np.searchsorted(ts, lo, side="left"), np.searchsorted(ts, hi, side="right")
    hit = np.flatnonzero(px[i:j] >= entry + tp - 1e-9)
    if len(hit) == 0:
        return None
    k = i + hit[0]
    return int(ts[k]), max(round(px[k] - 0.01, 4), 0.01)


def tp(games, wk, hist):
    gi = {g["game_id"]: g for g in games}
    sig = R1.load_signals()
    entries = []
    for name, lim, w in (("I12", "A1", 300), ("I9", "A2", 300)):
        for r in sig[sig.sig == name].itertuples():
            g = gi.get(r.game_id)
            if g is None or wk[g["game_id"]] < hist or r.team not in g["own"]:
                continue
            ts, px = g["own"][r.team]
            last = C.asof(ts, px, r.t_ns)
            if last != last:
                continue
            f = C.maker_entry(ts, px, r.t_ns, round(last - (0.01 if lim == "A2" else 0), 4), w)
            if f:
                entries.append((name, g, r.team, r.t_ns, f))
    for g in games:
        if g["pm"] is None or wk[g["game_id"]] < hist:
            continue
        for t, dirn in R1.c1_signals(g, 0.05, 15):
            team = g["home"] if dirn > 0 else g["away"]
            ts, px = g["own"][team]
            last = C.asof(ts, px, t)
            f = C.maker_entry(ts, px, t, last, 60) if last == last else None
            if f:
                entries.append(("C1", g, team, t, f))
                break                       # Round 1 C1 settle trials: one trade per game
    out = []
    for name, g, team, t, (fill_ts, entry) in entries:
        ts, px = g["own"][team]
        pay = g["pay"][team]
        for tpv in (0.03, 0.06):
            ex = tp_exit(ts, px, fill_ts, entry, tpv)
            if ex is None:
                if pay != pay:
                    continue
                out.append(R1.row(f"R2.TP.{name}.tp{tpv}", g, team, t, entry, C.fee_maker175(entry), 0.0, pay,
                                  extra={"week": wk[g["game_id"]], "held": True}))
            else:
                out.append(R1.row(f"R2.TP.{name}.tp{tpv}", g, team, t, entry, C.fee_maker175(entry), 0.0, None,
                                  exit_px=ex[1], extra={"week": wk[g["game_id"]], "held": False}))
    return out


def main() -> None:
    games = C.load_games()
    wk, hist = C.week_index(games)
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round2.csv", index=False)
    rows = arb(games, wk, hist)
    print("ARB", len(rows), flush=True)
    rows += cons(games, wk, hist)
    print("CONS", len(rows), flush=True)
    rows += vol(games, wk, hist)
    print("VOL", len(rows), flush=True)
    rows += tp(games, wk, hist)
    print("TP", len(rows), flush=True)
    pd.DataFrame(rows).to_parquet(C.CACHE / "trades_round2.parquet")


if __name__ == "__main__":
    sys.exit(main())
