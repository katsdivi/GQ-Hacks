"""Post-hoc cost-side search, Rounds 11 to 17 (literature mechanisms; SPEC.md "Resumed again" sections).

post-hoc, exploratory; training only. Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/costside_lit.py <round>     round in 11..17
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

import costside_common as C
import costside_espn as E

NS = C.NS


def reg(rnd, rows):
    return [{**r, "round": rnd} for r in rows]


def cost(em):
    return "taker" if em == "taker" else "maker175 (alt maker0)"


def minute_decisions(st: pd.DataFrame, lo_min: float, hi_min: float):
    """For each game-minute boundary b from lo_min down to hi_min (min_left), the first play at or past it:
    (decision ns = wallclock + 60 s, play row)."""
    out = []
    reg_ = st[st.period.between(1, 4)]
    for b in np.arange(lo_min, hi_min - 1e-9, -1.0):
        x = reg_[reg_.min_left <= b + 1e-9]
        if x.empty:
            break
        r = x.iloc[0]
        out.append((int(r.wc) + 60 * NS, r))
    return out


def state_samples(games, states, gid_ok):
    """(game_id, week, min_left, lead_home, final_lead_home) per game-minute from Q1 start to end of regulation."""
    rows = []
    for g in games:
        st = states.get(g["game_id"])
        if st is None or not gid_ok(g):
            continue
        reg_ = st[st.period.between(1, 4)]
        if reg_.empty:
            continue
        last = reg_.iloc[-1]
        final = last.kh - last.ka
        for b in np.arange(60, 0.5, -1.0):
            x = reg_[reg_.min_left <= b]
            if x.empty:
                break
            r = x.iloc[0]
            rows.append((g["game_id"], r.min_left, r.kh - r.ka, final))
    return pd.DataFrame(rows, columns=["game_id", "min_left", "lead", "final"])


# ---------------- Round 11 ----------------

def r11(games, wk, hist, states):
    registry = reg(11, [{"trial": f"R11.MODEL.{em}", "method": "pregame-anchored in-game model (Clegg et al.)",
                         "params": "gap>=0.06, Q2 to 5 min left, >=5 prints/3 min, settle", "cost_line": cost(em)}
                        for em in ("taker", "maker")])
    samp = state_samples(games, states, lambda g: True)
    samp["week"] = samp.game_id.map(wk)
    samp = samp[samp.min_left > 0.5]
    samp["z"] = (samp.final - samp.lead) / np.sqrt(samp.min_left)
    rows, desc = [], []
    for g in games:
        w = wk[g["game_id"]]
        st = states.get(g["game_id"])
        if w < hist or st is None:
            continue
        past = samp[samp.week < w]
        if len(past) < 1000:
            continue
        s = float(past.z.std())
        K = E.kickoff_price(g)
        if not (0.02 <= K <= 0.98):
            continue
        m = s * np.sqrt(60) * norm.ppf(K)
        done = {"taker": False, "maker": False}
        for t, r in minute_decisions(st, 45, 5):
            if E.prints_between(g, t - 180 * NS, t) < 5:
                continue
            p = norm.cdf((r.kh - r.ka + m) / (s * np.sqrt(max(r.min_left, 0.5))))
            P = C.asof(*g["kph"], t)
            if P != P:
                continue
            gap = p - P
            desc.append({"game_id": g["game_id"], "gap": gap})
            if abs(gap) < 0.06 - 1e-9:
                continue
            team = g["home"] if gap > 0 else g["away"]
            for em in ("taker", "maker"):
                if done[em]:
                    continue
                f = E.entry(g, team, t, em)
                if f:
                    x = E.trade_row(f"R11.MODEL.{em}", g, team, t, f, extra={"week": w, "gap": abs(gap)})
                    if x:
                        rows.append(x)
                        done[em] = True
            if all(done.values()):
                break
    d = pd.DataFrame(rows)
    if len(d):
        d["gap_bucket"] = pd.cut(d.gap, [0.06, 0.10, 1.0], include_lowest=True).astype(str)
        print(d.groupby(["trial", "gap_bucket"]).pnl.agg(["count", "mean"]).round(3))
    return registry, d


# ---------------- Round 12 ----------------

def r12(games, wk, hist, states):
    cells = [(a, l) for a in ("NS", "ALL") for l in ("low", "high")]
    registry = [{"trial": f"R12.{a}.{l}.taker.{x}", "method": "change-vs-change underreaction (arXiv 2606.07811)",
                 "params": f"arm={a} liq={l} exit={x} ratio<0.6 |dWP|>=0.05", "cost_line": "taker"}
                for a, l in cells for x in ("H360", "settle")]
    registry += [{"trial": f"R12.NS.low.maker.{x}", "method": "change-vs-change underreaction (arXiv 2606.07811)",
                  "params": f"arm=NS liq=low exit={x} maker", "cost_line": cost("maker")} for x in ("H360", "settle")]
    registry = reg(12, registry)
    ev = []
    for g in games:
        st = states.get(g["game_id"])
        if st is None:
            continue
        st = st[st.period.between(1, 4)]
        wpv = st.wp.to_numpy(float)
        for i in range(1, len(st)):
            if wpv[i] != wpv[i] or wpv[i - 1] != wpv[i - 1]:
                continue
            dwp = wpv[i] - wpv[i - 1]
            if abs(dwp) < 0.05:
                continue
            te = int(st.wc.iloc[i])
            td = te + 60 * NS
            P1, P0 = C.asof(*g["kph"], td), C.asof(*g["kph"], te - 15 * NS)
            if P1 != P1 or P0 != P0:
                continue
            ev.append({"game_id": g["game_id"], "week": wk[g["game_id"]], "td": td, "dwp": dwp, "R": P1 - P0,
                       "ns": not bool(st.scoring.iloc[i]), "liq": E.prints_between(g, td - 600 * NS, td)})
    ev = pd.DataFrame(ev)
    ev = ev[ev.R / ev.dwp < 0.6]
    gi = {g["game_id"]: g for g in games}
    rows = []
    for w in sorted(ev.week.unique()):
        if w < hist:
            continue
        past = ev[ev.week < w]
        if past.empty:
            continue
        med = past.liq.median()
        cur = ev[ev.week == w].sort_values("td")
        for (gid), x in cur.groupby("game_id"):
            g = gi[gid]
            for a, l in cells:
                sel = x[((x.ns) | (a == "ALL")) & ((x.liq <= med) if l == "low" else (x.liq > med))]
                ems = ("taker", "maker") if (a, l) == ("NS", "low") else ("taker",)
                for em in ems:
                    for xn, h in (("H360", 360), ("settle", None)):
                        free = -1
                        for r in sel.itertuples():
                            if r.td < free:
                                continue
                            team = g["home"] if r.dwp > 0 else g["away"]
                            f = E.entry(g, team, int(r.td), em)
                            if not f:
                                continue
                            row = E.trade_row(f"R12.{a}.{l}.{em}.{xn}", g, team, int(r.td), f, h, {"week": w})
                            if row is None:
                                continue
                            rows.append(row)
                            if h is None:
                                break
                            free = row["exit_ts"] if row["exit_ts"] else 2 ** 62
    return registry, pd.DataFrame(rows)


# ---------------- Round 13 ----------------

def r13(games, wk, hist, states):
    registry = reg(13, [{"trial": f"R13.UDOG.{q}.{em}", "method": "surprise-lead underdog (Angelini et al.)",
                         "params": f"K<=0.30 first lead in {q}, settle", "cost_line": cost(em)}
                        for q in ("Q34", "Q12") for em in ("taker", "maker")])
    rows = []
    for g in games:
        st = states.get(g["game_id"])
        w = wk[g["game_id"]]
        if st is None or w < hist:
            continue
        K = E.kickoff_price(g)
        if K != K:
            continue
        if K <= 0.30:
            dog, sgn = g["home"], 1
        elif K >= 0.70:
            dog, sgn = g["away"], -1
        else:
            continue
        reg_ = st[st.period.between(1, 4)]
        lead = sgn * (reg_.kh - reg_.ka)
        for q, pers in (("Q34", (3, 4)), ("Q12", (1, 2))):
            x = reg_[(lead >= 1) & reg_.period.isin(pers)]
            if x.empty:
                continue
            t = int(x.wc.iloc[0]) + 60 * NS
            for em in ("taker", "maker"):
                f = E.entry(g, dog, t, em)
                if f:
                    r = E.trade_row(f"R13.UDOG.{q}.{em}", g, dog, t, f, extra={"week": w, "K_dog": min(K, 1 - K)})
                    if r:
                        rows.append(r)
    return registry, pd.DataFrame(rows)


# ---------------- Round 14 ----------------

def r14(games, wk, hist, states):
    registry = reg(14, [{"trial": f"R14.LEADER.{em}", "method": "disposition-effect lead state (QJF 2012)",
                         "params": "lead 3-14, Q2 to 8 min left, P<=cell rate-0.03, >=30 games", "cost_line": cost(em)}
                        for em in ("taker", "maker")])
    obs = []
    for g in games:
        st = states.get(g["game_id"])
        K = E.kickoff_price(g)
        if st is None or K != K or g["pay"][g["home"]] != g["pay"][g["home"]]:
            continue
        for t, r in minute_decisions(st, 45, 8):
            lead = r.kh - r.ka
            if not 3 <= abs(lead) <= 14:
                continue
            home_leads = lead > 0
            kl = K if home_leads else 1 - K
            cell = ("3-7" if abs(lead) <= 7 else "8-14", int(min(max(r.period, 2), 4)),
                    "<0.35" if kl < 0.35 else ("0.35-0.65" if kl <= 0.65 else ">0.65"))
            team = g["home"] if home_leads else g["away"]
            obs.append({"game_id": g["game_id"], "week": wk[g["game_id"]], "t": t, "cell": cell, "team": team,
                        "win": g["pay"][team]})
    obs = pd.DataFrame(obs)
    gi = {g["game_id"]: g for g in games}
    rows = []
    for gid, x in obs.groupby("game_id"):
        w = int(x.week.iloc[0])
        if w < hist:
            continue
        past = obs[obs.week < w]
        g = gi[gid]
        done = {"taker": False, "maker": False}
        for r in x.sort_values("t").itertuples():
            pc = past[past.cell == r.cell]
            if pc.game_id.nunique() < 30:
                continue
            rate = pc.groupby("game_id").win.first().mean()
            P = C.asof(*g["own"][r.team], r.t)
            if P != P or P > rate - 0.03 + 1e-9:
                continue
            for em in ("taker", "maker"):
                if done[em]:
                    continue
                f = E.entry(g, r.team, int(r.t), em)
                if f:
                    row = E.trade_row(f"R14.LEADER.{em}", g, r.team, int(r.t), f, extra={"week": w, "rate": rate})
                    if row:
                        rows.append(row)
                        done[em] = True
            if all(done.values()):
                break
    return registry, pd.DataFrame(rows)


# ---------------- Round 16 ----------------

def espn_event_times(st):
    m = st.scoring | st.to_end | st.period_change
    return np.sort(st.wc[m].to_numpy(np.int64))


def r16(games, wk, hist, states):
    registry = reg(16, [{"trial": f"R16.JUMP.{a}.{x}", "method": "non-play price jump (news proxy)",
                         "params": f"arm={a} exit={x} jump>=0.05/90s, decision t+20s", "cost_line": "taker"}
                        for a in ("thin_follow", "thick_fade") for x in ("H300", "settle")])
    ev = []
    for g in games:
        st = states.get(g["game_id"])
        if st is None:
            continue
        evt = espn_event_times(st)
        kts, kpx = g["kph"]
        tsz = micro_size(g["game_id"])
        ko = g["kickoff_ns"]
        last_t = -1
        for i in np.flatnonzero((kts >= ko + 20 * 60 * NS) & (kts <= ko + 4 * 3600 * NS)):
            t = int(kts[i])
            if t < last_t + 300 * NS:
                continue
            p0 = C.asof(kts, kpx, t - 90 * NS)
            if p0 != p0 or abs(kpx[i] - p0) < 0.05 - 1e-9:
                continue
            j = np.searchsorted(evt, t - 120 * NS, side="left")
            if j < len(evt) and evt[j] <= t:
                continue
            a, b = np.searchsorted(tsz[0], t - 90 * NS, side="left"), np.searchsorted(tsz[0], t, side="right")
            ev.append({"game_id": g["game_id"], "week": wk[g["game_id"]], "t": t, "dir": 1 if kpx[i] > p0 else -1,
                       "vol": float(tsz[1][a:b].sum())})
            last_t = t
    ev = pd.DataFrame(ev)
    gi = {g["game_id"]: g for g in games}
    rows = []
    for w in sorted(ev.week.unique()):
        past = ev[ev.week < w]
        if w < hist or past.empty:
            continue
        q25, q75 = past.vol.quantile(0.25), past.vol.quantile(0.75)
        for gid, x in ev[ev.week == w].groupby("game_id"):
            g = gi[gid]
            for arm, sel, sgn in (("thin_follow", x[x.vol <= q25], 1), ("thick_fade", x[x.vol >= q75], -1)):
                for xn, h in (("H300", 300), ("settle", None)):
                    free = -1
                    for r in sel.sort_values("t").itertuples():
                        d = r.t + 20 * NS
                        if d < free:
                            continue
                        team = g["home"] if r.dir * sgn > 0 else g["away"]
                        f = E.entry(g, team, d, "taker")
                        if not f:
                            continue
                        row = E.trade_row(f"R16.JUMP.{arm}.{xn}", g, team, d, f, h, {"week": w})
                        if row is None:
                            continue
                        rows.append(row)
                        if h is None:
                            break
                        free = row["exit_ts"] if row["exit_ts"] else 2 ** 62
    return registry, pd.DataFrame(rows)


_size_cache = {}


def micro_size(gid):
    if gid not in _size_cache:
        t = pd.read_parquet(C.DATA / "raw" / "kalshi_only" / f"{gid}.parquet", columns=["ts", "kind", "size"])
        t = t[t.kind == "trade"].sort_values("ts", kind="stable")
        _size_cache.clear()
        _size_cache[gid] = (t.ts.to_numpy(np.int64), t["size"].to_numpy(float))
    return _size_cache[gid]


# ---------------- Round 17 ----------------

def r17(games, wk, hist, states):
    registry = reg(17, [{"trial": "R17.IMPACT", "method": "big-print impact reversion (kill test)",
                         "params": "size>=p90 game-to-date, move>=0.03, no ESPN play 60 s, +20 s entry, 3 min exit",
                         "cost_line": "taker"},
                        {"trial": "R17.SUM104", "method": "intra-Kalshi two-team sum >= 1.04, buy NO both (kill test)",
                         "params": "sister print within 5 s, entries >= t+5 s", "cost_line": "taker"}])
    rows = []
    episodes = 0
    for g in games:
        w = wk[g["game_id"]]
        if w < hist:
            continue
        st = states.get(g["game_id"])
        if st is not None:
            t_all = pd.read_parquet(C.DATA / "raw" / "kalshi_only" / f"{g['game_id']}.parquet",
                                    columns=["ts", "kind", "price", "size"])
            t_all = t_all[t_all.kind == "trade"].sort_values("ts", kind="stable")
            ts, px, sz = t_all.ts.to_numpy(np.int64), t_all.price.to_numpy(float), t_all["size"].to_numpy(float)
            plays = np.sort(st.wc.to_numpy(np.int64))
            ko = g["kickoff_ns"]
            free = -1
            for i in range(200, len(ts)):
                t = int(ts[i])
                if t < ko + 20 * 60 * NS or t > ko + 4 * 3600 * NS or t < free:
                    continue
                if abs(px[i] - px[i - 1]) < 0.03 - 1e-9 or sz[i] < np.percentile(sz[:i], 90):
                    continue
                j = np.searchsorted(plays, t - 60 * NS, side="left")
                if j < len(plays) and plays[j] <= t:
                    continue
                team = g["away"] if px[i] > px[i - 1] else g["home"]
                f = E.entry(g, team, t + 15 * NS, "taker")      # first print >= t + 20 s
                if not f:
                    continue
                row = E.trade_row("R17.IMPACT", g, team, t, f, 180, {"week": w})
                if row:
                    rows.append(row)
                    free = row["exit_ts"] if row["exit_ts"] else 2 ** 62
        # SUM104
        h, a = g["home"], g["away"]
        (hts, hpx), (ats, apx) = g["own"][h], g["own"][a]
        if len(hts) and len(ats):
            for ts1, px1, ts2, px2 in ((hts, hpx, ats, apx), (ats, apx, hts, hpx)):
                pass
            t_all = np.union1d(hts, ats)
            ih = np.searchsorted(hts, t_all, side="right") - 1
            ia = np.searchsorted(ats, t_all, side="right") - 1
            ok = (ih >= 0) & (ia >= 0)
            t_all, ih, ia = t_all[ok], ih[ok], ia[ok]
            fresh = np.abs(hts[ih] - ats[ia]) <= 5 * NS
            hit = np.flatnonzero(fresh & (hpx[ih] + apx[ia] >= 1.04 - 1e-9))
            if len(hit):
                episodes += 1
                t = int(t_all[hit[0]])
                legs = []
                for team in (h, a):
                    ts, px = g["own"][team]
                    k = np.searchsorted(ts, t + 5 * NS, side="left")
                    if k >= len(ts) or ts[k] > t + 60 * NS:
                        break
                    no = min(round(1 - px[k] + 0.01, 4), 0.99)
                    legs.append((team, no))
                if len(legs) == 2 and all(g["pay"][x] == g["pay"][x] for x in (h, a)):
                    cost_ = sum(n for _, n in legs) * C.QTY
                    fees = sum(C.fee_taker(n) for _, n in legs)
                    payout = sum((1 - g["pay"][tm]) for tm, _ in legs) * C.QTY
                    pnl = payout - cost_ - fees
                    rows.append({"trial": "R17.SUM104", "game_id": g["game_id"], "t_ns": t, "day": C.et_date(t),
                                 "entry": cost_ / C.QTY / 2, "fee_entry": fees, "payout": np.nan, "pnl": round(pnl, 6),
                                 "cap": cost_ + fees, "pnl_alt": round(pnl, 6), "cap_alt": cost_ + fees, "week": w})
    print("SUM104 episodes:", episodes)
    return registry, pd.DataFrame(rows)


def main() -> None:
    rnd = int(sys.argv[1])
    games = C.load_games()
    wk, hist = C.week_index(games)
    states, tot = E.load_states(games)
    print("ESPN states:", tot, flush=True)
    fn = {11: r11, 12: r12, 13: r13, 14: r14, 16: r16, 17: r17}[rnd]
    registry, d = fn(games, wk, hist, states)
    pd.DataFrame(registry).to_csv(C.CACHE / f"registry_round{rnd}.csv", index=False)
    if d.empty:
        d = pd.DataFrame(columns=["trial", "game_id", "day", "pnl", "cap", "pnl_alt", "cap_alt"])
    d.to_parquet(C.CACHE / f"trades_round{rnd}.parquet")
    print("rows", len(d), d.trial.value_counts().to_dict() if len(d) else {})


if __name__ == "__main__":
    sys.exit(main())
