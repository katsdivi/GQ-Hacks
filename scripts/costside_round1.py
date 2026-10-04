"""Post-hoc cost-side search, Round 1 (SPEC.md Round 1: blocks A, B, C1, C3, C4; C2 skipped).

post-hoc, exploratory; training only. Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/costside_round1.py
Writes per-trade rows to data/costside_cache/trades_round1.parquet (gitignored); summaries via costside_log.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

import costside_common as C

WT = Path("/Users/divyamkataria/GQ HACKS")
SIGNAL_FILES = {
    "I7": (WT / "wt-idea7/results/posthoc_idea7/training_trades.csv", lambda d: d[(d.k == 0.02) & (d.leg == "signal")]),
    "I8": (WT / "wt-idea8/results/posthoc_idea8/training_trades.csv", lambda d: d[(d.x == 0.2) & (d.leg == "fade")]),
    "I9": (WT / "wt-idea9/results/posthoc_idea9/training_trades.csv",
           lambda d: d[(d.k == 0.10) & (d.delay == 60) & (d.leg == "signal")]),
    "I12": (WT / "wt-idea12/results/posthoc_idea12/training_trades.csv", lambda d: d[(d.k == 0.03) & (d.leg == "signal")]),
    "I13": (WT / "wt-idea13/results/posthoc_idea13/training_trades.csv", lambda d: d[(d.e == 0.02) & (d.leg == "signal")]),
}


def load_signals() -> pd.DataFrame:
    out = []
    a = pd.read_parquet(C.DATA.parent / "out/strategy_a/rows.parquet")
    a = a[(a.theta == 0.8) & (~a.placebo.astype(bool)) & (a.entered.astype(bool) | (a.skip == "no post-decision trade"))]
    out.append(pd.DataFrame({"sig": "A", "game_id": a.game_id, "team": a.team,
                             "t_ns": (pd.to_datetime(a.kickoff, utc=True) - pd.Timedelta(minutes=5)).astype("int64")}))
    for name, (f, flt) in SIGNAL_FILES.items():
        d = flt(pd.read_csv(f))
        d = d[d.team.notna() & d.t_ns.notna()]
        out.append(pd.DataFrame({"sig": name, "game_id": d.game_id, "team": d.team, "t_ns": d.t_ns.astype("int64")}))
    s = pd.concat(out, ignore_index=True)
    # Ideas 7 and 12 store team as "home"/"away": map to Kalshi codes (fix after the first round-1 run, disclosed)
    ko = pd.read_csv(C.DATA / "raw" / "kalshi_only_games.csv").set_index("game_id")
    ha = s.team.isin(["home", "away"])
    s.loc[ha, "team"] = [ko.loc[g, t] if g in ko.index else None for g, t in zip(s.game_id[ha], s.team[ha])]
    return s[s.team.notna()]


def row(trial, g, team, t, entry, fee_e, fee_e0, payout, exit_px=None, extra=None):
    b = C.book_trade(entry, fee_e, payout, exit_px)
    b0 = C.book_trade(entry, fee_e0, payout, exit_px)
    r = {"trial": trial, "game_id": g["game_id"], "team": team, "t_ns": t, "day": C.et_date(t), "entry": entry,
         "fee_entry": fee_e, "payout": payout if exit_px is None else np.nan, "pnl": b["pnl"], "cap": b["cap"],
         "pnl_alt": b0["pnl"], "cap_alt": b0["cap"]}
    if extra:
        r.update(extra)
    return r


def block_a(games, sig, wk):
    """24 trials + B1/B2 inputs. Returns trades, diagnostics rows."""
    gi = {g["game_id"]: g for g in games}
    trades, diag = [], []
    for s in sorted(sig.sig.unique()):
        ss = sig[sig.sig == s]
        for lim_name in ("A1", "A2"):
            for w in (60, 300):
                trial = f"R1.A.{s}.{lim_name}.W{w}"
                for r in ss.itertuples():
                    g = gi.get(r.game_id)
                    if g is None or r.team not in g["own"]:
                        diag.append({"trial": trial, "game_id": r.game_id, "status": "no data"})
                        continue
                    ts, px = g["own"][r.team]
                    last = C.asof(ts, px, r.t_ns)
                    pay = g["pay"][r.team]
                    if last != last:
                        diag.append({"trial": trial, "game_id": r.game_id, "status": "no last trade"})
                        continue
                    lim = round(last - (0.01 if lim_name == "A2" else 0.0), 4)
                    f = C.maker_entry(ts, px, r.t_ns, lim, w)
                    diag.append({"trial": trial, "game_id": r.game_id, "status": "filled" if f else "unfilled",
                                 "payout": pay, "limit": lim})
                    if f is None or pay != pay:
                        continue
                    trades.append(row(trial, g, r.team, r.t_ns, f[1], C.fee_maker175(f[1]), C.fee_maker0(f[1]), pay,
                                      extra={"sig": s, "week": wk[g["game_id"]]}))
    return pd.DataFrame(trades), pd.DataFrame(diag)


def block_b(games, sig, wk, hist):
    """Fee-band walk-forward over the 6 signals; B1 taker (5 min window), B2 maker A2 W300."""
    gi = {g["game_id"]: g for g in games}
    cand = []
    for r in sig.itertuples():
        g = gi.get(r.game_id)
        if g is None or r.team not in g["own"]:
            continue
        ts, px = g["own"][r.team]
        pay = g["pay"][r.team]
        if pay != pay:
            continue
        tk = C.taker_entry(ts, px, r.t_ns, 300)
        if tk:
            cand.append(row("B1", g, r.team, r.t_ns, tk[1], C.fee_taker(tk[1]), C.fee_taker(tk[1]), pay,
                            extra={"sig": r.sig, "week": wk[g["game_id"]]}))
        last = C.asof(ts, px, r.t_ns)
        if last == last:
            mk = C.maker_entry(ts, px, r.t_ns, round(last - 0.01, 4), 300)
            if mk:
                cand.append(row("B2", g, r.team, r.t_ns, mk[1], C.fee_maker175(mk[1]), 0.0, pay,
                                extra={"sig": r.sig, "week": wk[g["game_id"]]}))
    cand = pd.DataFrame(cand)
    cand["band"] = np.where(cand.entry <= 0.10, "low", np.where(cand.entry >= 0.90, "high", "mid"))
    cand = cand[cand.band != "mid"]
    out = []
    for trial in ("B1", "B2"):
        c = cand[cand.trial == trial]
        for w in sorted(c.week.unique()):
            if w < hist:
                continue
            past = c[c.week < w]
            stats = past.groupby(["sig", "band"])["pnl"].agg(["mean", "count"])
            ok = set(stats[(stats["mean"] > 0) & (stats["count"] >= 10)].index)
            cur = c[c.week == w]
            out.append(cur[[(s, b) in ok for s, b in zip(cur.sig, cur.band)]].assign(trial=f"R1.{trial}"))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def run_sequential(g, sigs, team_of, trial, exec_mode, exit_h, extra=None):
    """sigs: sorted array of (t, direction). One open position at a time."""
    rows, free = [], -1
    for t, dirn in sigs:
        if t < free:
            continue
        team = team_of(dirn)
        ts, px = g["own"][team]
        pay = g["pay"][team]
        if exec_mode == "taker":
            f = C.taker_entry(ts, px, t, 60)
            fe = (lambda p: C.fee_taker(p), lambda p: C.fee_taker(p))
        else:
            last = C.asof(ts, px, t)
            f = C.maker_entry(ts, px, t, last, 60) if last == last else None
            fe = (C.fee_maker175, C.fee_maker0)
        if f is None:
            continue
        fill_ts, entry = f
        if exit_h is None:
            if pay != pay:
                break
            rows.append(row(trial, g, team, t, entry, fe[0](entry), fe[1](entry), pay, extra=extra))
            break                                   # hold to settlement: one trade per game
        ex = C.exit_at(ts, px, fill_ts, exit_h)
        if ex is None:
            if pay != pay:
                break
            rows.append(row(trial, g, team, t, entry, fe[0](entry), fe[1](entry), pay,
                            extra={**(extra or {}), "held": True}))
            break
        rows.append(row(trial, g, team, t, entry, fe[0](entry), fe[1](entry), None, exit_px=ex[1],
                        extra={**(extra or {}), "held": False}))
        free = ex[0]
    return rows


def c1_signals(g, d, s):
    ko = g["kickoff_ns"]
    lo, hi = ko + 20 * 60 * C.NS, ko + 4 * 3600 * C.NS
    pts, ppx = g["pm"]
    kts, kpx = g["kph"]
    if len(pts) == 0 or len(kts) == 0:
        return []
    m = (pts >= lo) & (pts <= hi)
    t = pts[m]
    p = ppx[m]
    i30 = np.searchsorted(pts, t - 30 * C.NS, side="right") - 1
    prev = np.where(i30 >= 0, ppx[np.maximum(i30, 0)], np.nan)
    mv = p - prev
    ik = np.searchsorted(kts, t, side="right") - 1
    iks = np.searchsorted(kts, t - s * C.NS, side="right") - 1
    kt = np.where(ik >= 0, kpx[np.maximum(ik, 0)], np.nan)
    ks = np.where(iks >= 0, kpx[np.maximum(iks, 0)], np.nan)
    recent = np.where(ik >= 0, t - kts[np.maximum(ik, 0)] <= 120 * C.NS, False)
    ok = (np.abs(mv) >= d - 1e-9) & (kt == ks) & recent
    return [(int(a), 1 if b > 0 else -1) for a, b in zip(t[ok], mv[ok])]


def c3_signals(g, mode):
    ko = g["kickoff_ns"]
    lo, hi = ko + 20 * 60 * C.NS, ko + 4 * 3600 * C.NS
    kts, kpx = g["kph"]
    m = (kts >= lo) & (kts <= hi)
    t, p = kts[m], kpx[m]
    i30 = np.searchsorted(kts, t - 30 * C.NS, side="right") - 1
    prev = np.where(i30 >= 0, kpx[np.maximum(i30, 0)], np.nan)
    mv = p - prev
    ok = np.abs(mv) >= 0.05 - 1e-9
    sgn = np.sign(mv[ok]).astype(int) * (1 if mode == "mom" else -1)
    return [(int(a), int(b)) for a, b in zip(t[ok], sgn)]


def block_c(games, wk, hist):
    out = []
    exits = {"H60": 60, "H300": 300, "settle": None}
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        team_of = lambda dirn, g=g: g["home"] if dirn > 0 else g["away"]
        ex = {"week": wk[g["game_id"]]}
        if g["pm"] is not None:
            for d in (0.02, 0.03, 0.05):
                for s in (5, 15):
                    sigs = c1_signals(g, d, s)
                    for em in ("taker", "maker"):
                        for en, h in exits.items():
                            out += run_sequential(g, sigs, team_of, f"R1.C1.d{d}.s{s}.{em}.{en}", em, h, ex)
        for mode in ("mom", "rev"):
            sigs = c3_signals(g, mode)
            for em in ("taker", "maker"):
                for en, h in exits.items():
                    out += run_sequential(g, sigs, team_of, f"R1.C3.{mode}.{em}.{en}", em, h, ex)
        t = g["kickoff_ns"] + 20 * 60 * C.NS
        for team in (g["home"], g["away"]):
            ts, px = g["own"][team]
            i = np.searchsorted(ts, t, side="right") - 1
            if i < 0 or t - ts[i] > 600 * C.NS:
                continue
            p = px[i]
            bands = [(0.01, 0.20), (0.20, 0.40), (0.40, 0.60), (0.60, 0.80), (0.80, 0.99)]
            for lo, hi in bands:
                if lo <= p < hi:
                    f = C.taker_entry(ts, px, t, 60)
                    pay = g["pay"][team]
                    if f and pay == pay:
                        out.append(row(f"R1.C4.b{lo:.2f}-{hi:.2f}", g, team, t, f[1], C.fee_taker(f[1]),
                                       C.fee_taker(f[1]), pay, extra={**ex, "asof": p}))
    return pd.DataFrame(out)


def registry() -> list[dict]:
    r = []
    for s in ("A", "I12", "I13", "I7", "I8", "I9"):
        for lim in ("A1", "A2"):
            for w in (60, 300):
                r.append({"trial": f"R1.A.{s}.{lim}.W{w}", "method": "maker execution of existing signal",
                          "params": f"signal={s} limit={lim} W={w}s", "cost_line": "maker175 (alt maker0)"})
    r += [{"trial": "R1.B1", "method": "fee-band walk-forward", "params": "taker, bands P<=0.10/P>=0.90",
           "cost_line": "taker"},
          {"trial": "R1.B2", "method": "fee-band walk-forward", "params": "maker A2 W300, bands P<=0.10/P>=0.90",
           "cost_line": "maker175 (alt maker0)"}]
    for d in (0.02, 0.03, 0.05):
        for s in (5, 15):
            for em in ("taker", "maker"):
                for en in ("H60", "H300", "settle"):
                    r.append({"trial": f"R1.C1.d{d}.s{s}.{em}.{en}", "method": "polymarket.com leads Kalshi",
                              "params": f"d={d} s={s} exec={em} exit={en}",
                              "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"})
    for mode in ("mom", "rev"):
        for em in ("taker", "maker"):
            for en in ("H60", "H300", "settle"):
                r.append({"trial": f"R1.C3.{mode}.{em}.{en}", "method": "Kalshi own large move",
                          "params": f"mode={mode} exec={em} exit={en}",
                          "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"})
    for lo, hi in [(0.01, 0.20), (0.20, 0.40), (0.40, 0.60), (0.60, 0.80), (0.80, 0.99)]:
        r.append({"trial": f"R1.C4.b{lo:.2f}-{hi:.2f}", "method": "in-game price band at kickoff + 20 min",
                  "params": f"band=[{lo},{hi})", "cost_line": "taker"})
    assert len(r) == 79
    return [{**x, "round": 1} for x in r]


def main() -> None:
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round1.csv", index=False) if C.CACHE.mkdir(parents=True, exist_ok=True) is None else None
    games = C.load_games()
    wk, hist = C.week_index(games)
    print(f"games {len(games)}, B-set with pm {sum(g['pm'] is not None for g in games)}", flush=True)
    sig = load_signals()
    sig = sig[sig.game_id.map(lambda x: wk.get(x, -1) >= hist)]
    print("signals in test weeks:", sig.sig.value_counts().to_dict(), flush=True)
    a, diag = block_a(games, sig, wk)
    print("A done", len(a), flush=True)
    b = block_b(games, load_signals(), wk, hist)
    print("B done", len(b), flush=True)
    c = block_c(games, wk, hist)
    print("C done", len(c), flush=True)
    allt = pd.concat([a, b, c], ignore_index=True)
    C.CACHE.mkdir(parents=True, exist_ok=True)
    allt.to_parquet(C.CACHE / "trades_round1.parquet")
    diag.to_parquet(C.CACHE / "diag_round1.parquet")


if __name__ == "__main__":
    sys.exit(main())
