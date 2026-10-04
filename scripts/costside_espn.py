"""Post-hoc cost-side search: parsed ESPN game states for Rounds 11 to 17 (Kalshi orientation, strict defect filter).

post-hoc, exploratory; training only. Cache: data/costside_cache/espn_states.pkl (gitignored).
"""
from __future__ import annotations

import json
import pickle

import numpy as np
import pandas as pd

import costside_common as C
import costside_round7 as R7

TO_RESULTS = R7.TO_RESULTS


def clock_sec(p) -> float:
    v = (p.get("clock") or {}).get("displayValue", "0:00")
    try:
        mm, ss = v.split(":")
        return int(mm) * 60 + float(ss)
    except ValueError:
        return np.nan


def parse(g, idrow):
    stats = {"no summary": 0, "mapping": 0, "defect": 0, "ok": 0}
    e = R7.load_espn(g, idrow, stats)
    if e is None:
        return None, stats
    d = json.loads((R7.ESPN / f"{g['league'].lower()}_{idrow.espn_id}.json").read_text())
    comp = d["header"]["competitions"][0]
    espn_home_is_kalshi_home = e["id2code"][str([c for c in comp["competitors"] if c["homeAway"] == "home"][0]["team"]["id"])] == g["home"]
    wp = {str(x["playId"]): x.get("homeWinPercentage") for x in (d.get("winprobability") or [])}
    rows = []
    for dr in e["drives"]:
        plays = [p for p in dr.get("plays", []) if p.get("wallclock")]
        for j, p in enumerate(plays):
            hs, as_ = p.get("homeScore"), p.get("awayScore")
            if hs is None or as_ is None:
                continue
            kh, ka = (hs, as_) if espn_home_is_kalshi_home else (as_, hs)
            w = wp.get(str(p.get("id")))
            if w is not None and not espn_home_is_kalshi_home:
                w = 1 - w
            per = (p.get("period") or {}).get("number", 0)
            rows.append({"wc": R7.ns(p["wallclock"]), "period": per, "clock": clock_sec(p), "kh": kh, "ka": ka,
                         "scoring": bool(p.get("scoringPlay")), "wp": w,
                         "to_end": (j == len(plays) - 1) and dr.get("result") in TO_RESULTS,
                         "text": (p.get("text") or "")[:60]})
    df = pd.DataFrame(rows)
    if df.empty:
        return None, stats
    df["min_left"] = (4 - df.period) * 15 + df.clock / 60
    df["period_change"] = df.period.diff().fillna(0) != 0
    return df.reset_index(drop=True), stats


def load_states(games):
    f = C.CACHE / "espn_states.pkl"
    if f.exists():
        return pickle.loads(f.read_bytes())
    ids = pd.read_csv(R7.ESPN / "ids_training.csv").drop_duplicates("game_id").set_index("game_id")
    out, tot = {}, {"no summary": 0, "mapping": 0, "defect": 0, "ok": 0, "no id": 0}
    for g in games:
        if g["game_id"] not in ids.index or ids.loc[g["game_id"], "espn_id"] != ids.loc[g["game_id"], "espn_id"]:
            tot["no id"] += 1
            continue
        idrow = ids.loc[g["game_id"]].copy()
        idrow["espn_id"] = int(float(idrow["espn_id"]))
        df, st = parse(g, idrow)
        for k, v in st.items():
            tot[k] += v
        if df is not None:
            out[g["game_id"]] = df
    f.write_bytes(pickle.dumps((out, tot)))
    return out, tot


def kickoff_price(g) -> float:
    kts, kpx = g["kph"]
    ko = g["kickoff_ns"]
    m = (kts >= ko - 300 * C.NS) & (kts <= ko)
    return float(np.median(kpx[m])) if m.any() else np.nan


def entry(g, team, t, mode, delay_s=5.0):
    """Research entry: first own print >= t + 5 s within 60 s, +1 c (taker); maker: limit = own last print at t,
    trade-through in (t + 5 s, t + 60 s]."""
    ts, px = g["own"][team]
    if mode == "taker":
        lo = t + int(delay_s * C.NS)
        i = np.searchsorted(ts, lo, side="left")
        if i >= len(ts) or ts[i] > t + 60 * C.NS:
            return None
        f = min(round(px[i] + 0.01, 4), 0.99)
        return (int(ts[i]), f, C.fee_taker(f), C.fee_taker(f)) if f < 0.99 else None
    last = C.asof(ts, px, t)
    if last != last or not (0.01 <= last <= 0.98):
        return None
    lo, hi = t + int(delay_s * C.NS), t + 60 * C.NS
    i, j = np.searchsorted(ts, lo, side="right"), np.searchsorted(ts, hi, side="right")
    hit = np.flatnonzero(px[i:j] <= last - 0.01 + 1e-9)
    if len(hit) == 0:
        return None
    return int(ts[i + hit[0]]), round(last, 4), C.fee_maker175(last), 0.0


def trade_row(trial, g, team, t, f, exit_h=None, extra=None):
    fill_ts, e, fe, f0 = f
    pay = g["pay"][team]
    ex = C.exit_at(*g["own"][team], fill_ts, exit_h) if exit_h else None
    if ex is None:
        if pay != pay:
            return None
        pnl, pnl0, payout = (pay - e) * C.QTY - fe, (pay - e) * C.QTY - f0, pay
        held = True
    else:
        fx = C.fee_taker(ex[1])
        pnl, pnl0, payout, held = (ex[1] - e) * C.QTY - fe - fx, (ex[1] - e) * C.QTY - f0 - fx, np.nan, False
    r = {"trial": trial, "game_id": g["game_id"], "team": team, "t_ns": t, "day": C.et_date(t), "entry": e,
         "fee_entry": fe, "payout": payout, "pnl": round(pnl, 6), "cap": e * C.QTY + fe, "pnl_alt": round(pnl0, 6),
         "cap_alt": e * C.QTY + f0, "held": held, "exit_ts": ex[0] if ex else None}
    if extra:
        r.update(extra)
    return r


def prints_between(g, a, b) -> int:
    kts, _ = g["kph"]
    return int(np.searchsorted(kts, b, side="right") - np.searchsorted(kts, a, side="left"))
