"""Post-run holdout diagnostics h2-h5 (EXPLORATORY, post-run; they do not change any pre-registered result).

Polymarket US Time & Sales (20261003 file, 17:00 ET Oct 2 to 16:59 ET Oct 3) against the run's laggard fills and
the recorded Polymarket US book. Every number is partial: before 17:00 ET Oct 3.

Read-only on the staleline checkout; writes only results/holdout_diag/h2_*, h3_*, h4_*, h5_*.

Usage: PYTHONPATH=.:scripts python scripts/holdout_diag_h.py {h2,orient,h3,h4,h5,h4delay}
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import holdout_mid as H  # noqa: E402
import laggard as L  # noqa: E402
import final_test_run as F  # noqa: E402

NS = 1_000_000_000
SL = Path("/Users/divyamkataria/GQ HACKS/staleline")
OUT = ROOT / "results" / "holdout_diag"
CSV = Path("/private/tmp/claude-501/-Users-divyamkataria-GQ-HACKS/4b6ada3b-5914-4e79-b685-97dc6f2dd657/scratchpad/"
           "pmus_tns/20261003-time-and-sales.csv")
HDR = "exploratory, post-run, partial: before 17:00 ET Oct 3"
CUT = pd.Timestamp("2026-10-03 17:00", tz="America/New_York").value
TOL = 1e-9
ET = "America/New_York"
G_ADDED = (0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0)

H3_RULE = (
    "h3 rule (fixed before computing): for each T&S trade in a game's laggard window (home price p, venue time tv), "
    "take the last recorded snapshot with ts <= tv (old book). Classify p against old best bid and old best ask "
    "with |difference| <= 1e-9. If p equals exactly one of them, that is the side. Scan the recorded snapshots with "
    "ts > tv and ts - tv <= 30 s in time order; the delay is ts of the FIRST snapshot whose value on that side "
    "differs from the old value (NaN vs a number counts as a change, NaN vs NaN does not) minus tv. Excluded as "
    "ambiguous, by reason: no_old_book (no snapshot with ts <= tv), matches_both, matches_neither, no_change_30s.")
H4_RULE = (
    "h4 rule: a fill leg is CONFIRMED if some T&S trade on that slug printed at home price <= our price + 1e-9 for "
    "a buy of home, or >= our price - 1e-9 for a sell of home, with venue time in [fill time - 1 s, fill time + 2 s] "
    "(inclusive). Entry: buy home at entry_px if direction == +1 else sell home at entry_px. Exit: the opposite side "
    "at exit_px. Fill times are entry_fill_ns / exit_fill_ns of the trade row.")


def ctx():
    vroot, mroot = SL / "data" / "vultr", SL / "data" / "mac"
    machines = {"vultr": H.Machine("vultr", vroot, vroot / "GAPS_vultr.md", vroot / "heartbeats"),
                "mac": H.Machine("mac", SL, mroot / "GAPS_mac.md", mroot / "heartbeats")}
    cands = pd.read_csv(SL / "data" / "live" / "holdout_candidates.csv").set_index("game_id")
    maps = H.load_maps(SL / "data" / "live" / "holdout_maps")
    return machines, cands, maps


def inst(cands, maps, gid):
    return H.instruments(cands.loc[[gid]].reset_index().iloc[0], maps)


def md(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v) for v in row) + " |")
    return "\n".join(lines)


def write(path: Path, text: str) -> None:
    path.write_text(HDR + "\n" + text)


def write_csv(path: Path, df: pd.DataFrame) -> None:
    with open(path, "w") as fh:
        fh.write(HDR + "\n")
        df.to_csv(fh, index=False)


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, skiprows=1)


def subset(t: pd.DataFrame, lat: float) -> pd.DataFrame:
    s = t[(t.venue == "polymarket_us") & t["filled"].astype(bool) & (t.latency_s == lat) & (t.exit_fill_ns < CUT)]
    return s.reset_index(drop=True)


def run_trades() -> pd.DataFrame:
    return pd.read_csv(SL / "results" / "holdout" / "laggard_trades.csv")


def games():
    """The 39 games of the 1 s subset: slug, long_is_away, machine, laggard window [lo, hi)."""
    machines, cands, maps = ctx()
    s1 = subset(run_trades(), 1.0)
    pg = pd.read_csv(SL / "results" / "holdout" / "lead_Polymarket US_per_game.csv").set_index("game_id")
    pmap = json.load(open(SL / "data" / "live" / "holdout_maps" / "polymarket_us_map.json"))
    rows = []
    for gid in sorted(s1.game_id.unique()):
        r = pg.loc[gid]
        slug = inst(cands, maps, gid)["polymarket_us"]
        pin = None if pd.isna(r.pin_start_g) else int(r.pin_start_g)
        machine = s1.loc[s1.game_id == gid, "machine"].iloc[0]
        rows.append({"game_id": gid, "slug": slug, "long_is_away": bool(pmap[slug]["long_is_away"]),
                     "machine": machine, "lo": int(r.window_start_ns),
                     "hi": int(L.trading_end_ns(pd.Timestamp(r.kickoff_utc).value, pin))})
    return pd.DataFrame(rows), machines


def load_book(machines, g) -> pd.DataFrame:
    m = machines[g.machine]
    rows = F.rows_with_size(m, "polymarket_us", g.slug, g.lo - 3600 * NS, g.hi + 120 * NS)
    return L.book(rows, "polymarket_us")


def tns() -> pd.DataFrame:
    d = read_csv(OUT / "h2_tns_trades_39_games.csv")
    return d


# ---------- h2 ----------

def h2() -> None:
    gs, _ = games()
    slugs = set(gs.slug)
    keep, tmin, tmax, n_all = [], None, None, 0
    frac, offs = set(), set()
    for ch in pd.read_csv(CSV, chunksize=1_000_000, dtype={"Symbol": "string", "Transaction Time": "string"}):
        n_all += len(ch)
        tt = ch["Transaction Time"]
        smp = tt.iloc[:: max(1, len(tt) // 200)]
        for x in smp:
            m = re.match(r".*T\d\d:\d\d:\d\d\.(\d+)(.*)$", x)
            frac.add(len(m.group(1)) if m else 0)
            offs.add(m.group(2) if m else x[-6:])
        ts = pd.to_datetime(tt, format="ISO8601", utc=True)
        a, b = ts.min(), ts.max()
        tmin = a if tmin is None or a < tmin else tmin
        tmax = b if tmax is None or b > tmax else tmax
        f = ch[ch["Symbol"].isin(slugs)]
        if len(f):
            keep.append(f.assign(tv=pd.to_datetime(f["Transaction Time"], format="ISO8601", utc=True)
                                 .dt.as_unit("ns").astype("int64")))
    d = pd.concat(keep, ignore_index=True)
    d = d.merge(gs[["slug", "game_id", "long_is_away"]], left_on="Symbol", right_on="slug")
    p = pd.to_numeric(d["Last Price"])
    d = pd.DataFrame({"game_id": d.game_id, "slug": d.slug, "transaction_time": d["Transaction Time"], "tv": d.tv,
                      "long_price": p, "long_is_away": d.long_is_away,
                      "home_price": np.where(d.long_is_away, 1 - p, p), "qty": pd.to_numeric(d["Last Quantity"])})
    d = d.sort_values(["game_id", "tv"], kind="stable").reset_index(drop=True)
    write_csv(OUT / "h2_tns_trades_39_games.csv", d)
    cnt = []
    for g in gs.itertuples():
        x = d[(d.slug == g.slug)]
        w = x[(x.tv >= g.lo) & (x.tv < g.hi)]
        cnt.append({"game_id": g.game_id, "slug": g.slug, "long_is_away": g.long_is_away,
                    "window_start_et": pd.Timestamp(g.lo, tz="UTC").tz_convert(ET).isoformat(),
                    "window_end_et": pd.Timestamp(g.hi, tz="UTC").tz_convert(ET).isoformat(),
                    "tns_trades_in_file": len(x), "tns_trades_in_window": len(w),
                    "tns_trades_in_window_before_cut": int((w.tv < CUT).sum()),
                    "qty_in_window": float(w.qty.sum())})
    cnt = pd.DataFrame(cnt)
    write_csv(OUT / "h2_per_game_counts.csv", cnt)
    txt = (f"\n# h2 Time & Sales file\n\n- file: 20261003-time-and-sales.csv, {CSV.stat().st_size} bytes, {n_all} rows\n"
           f"- venue timestamp field: 'Transaction Time'; fractional digits seen (sampled): {sorted(frac)}; "
           f"offset strings seen (sampled): {sorted(offs)}\n"
           f"- min Transaction Time: {tmin.tz_convert(ET).isoformat()} ET\n"
           f"- max Transaction Time: {tmax.tz_convert(ET).isoformat()} ET\n"
           f"- games: {len(gs)}; slugs with long_is_away True: {int(gs.long_is_away.sum())}, False: "
           f"{int((~gs.long_is_away).sum())}\n"
           f"- laggard window per game = [window_start_ns from lead_Polymarket US_per_game.csv, "
           f"laggard.trading_end_ns(kickoff, pin_start_g)), same as part_g\n"
           f"- T&S trades kept (39 slugs, whole file): {len(d)}; inside windows: {int(cnt.tns_trades_in_window.sum())}\n"
           f"- price units: Last Price min {p.min()}, max {p.max()}\n\n"
           + md(cnt) + "\n")
    write(OUT / "h2_tns_file.md", txt)
    print(txt)


# ---------- orientation check ----------

def orient() -> None:
    gs, machines = games()
    d = tns()
    rows = []
    for g in gs.itertuples():
        x = d[(d.slug == g.slug) & (d.tv >= g.lo) & (d.tv < g.hi)]
        if not len(x):
            continue
        q = load_book(machines, g)
        ts = q.ts.to_numpy()
        i = np.searchsorted(ts, x.tv.to_numpy(), side="right") - 1
        ok = i >= 0
        bid, ask = q.bid.to_numpy()[i[ok]], q.ask.to_numpy()[i[ok]]
        hp = x.home_price.to_numpy()[ok]
        lp = x.long_price.to_numpy()[ok]
        unflipped = lp  # never flip
        inA = (hp >= bid - 0.005) & (hp <= ask + 0.005)
        inB = (unflipped >= bid - 0.005) & (unflipped <= ask + 0.005)
        age = x.tv.to_numpy()[ok] - ts[i[ok]]
        fr = age <= NS                                   # prints within 1 s after the snapshot's receipt ts
        win = q[(q.ts >= g.lo) & (q.ts < g.hi)].ts.to_numpy()
        gap = np.diff(win) / NS
        rows.append({"game_id": g.game_id, "long_is_away": g.long_is_away, "n_prints": int(ok.sum()),
                     "n_prints_fresh_le_1s": int(fr.sum()),
                     "fresh_share_inside_A": float(inA[fr].mean()) if fr.any() else np.nan,
                     "fresh_share_inside_B": float(inB[fr].mean()) if fr.any() else np.nan,
                     "snapshots_in_window": len(win),
                     "snapshot_gap_median_s": float(np.median(gap)) if len(gap) else np.nan,
                     "snapshot_gap_p10_s": float(np.quantile(gap, 0.1)) if len(gap) else np.nan,
                     "share_gaps_lt_2s": float((gap < 2).mean()) if len(gap) else np.nan,
                     "share_inside_A_flip_if_long_away": float(inA.mean()),
                     "share_inside_B_never_flip": float(inB.mean()),
                     "snapshots": len(q), "snapshots_bid_nan": int(q.bid.isna().sum()),
                     "snapshots_ask_nan": int(q.ask.isna().sum())})
    r = pd.DataFrame(rows)
    write_csv(OUT / "h2_orientation_check.csv", r)
    print(r.to_string(index=False))
    fw = r.n_prints_fresh_le_1s
    print("fresh pooled A", (r.fresh_share_inside_A.fillna(0) * fw).sum() / fw.sum(),
          "fresh pooled B", (r.fresh_share_inside_B.fillna(0) * fw).sum() / fw.sum(), "n fresh", fw.sum())
    print("pooled A", (r.share_inside_A_flip_if_long_away * r.n_prints).sum() / r.n_prints.sum(),
          "pooled B", (r.share_inside_B_never_flip * r.n_prints).sum() / r.n_prints.sum())


# ---------- h3 ----------

def h3() -> None:
    write(OUT / "h3_rule.md", "\n" + H3_RULE + "\n")      # rule written before any computation
    gs, machines = games()
    d = tns()
    rows = []
    for g in gs.itertuples():
        x = d[(d.slug == g.slug) & (d.tv >= g.lo) & (d.tv < g.hi)]
        if not len(x):
            continue
        q = load_book(machines, g)
        ts, bid, ask = q.ts.to_numpy(), q.bid.to_numpy(), q.ask.to_numpy()
        for t in x.itertuples():
            tv, p = int(t.tv), float(t.home_price)
            i = int(np.searchsorted(ts, tv, side="right")) - 1
            rec = {"game_id": g.game_id, "tv": tv, "home_price": p, "delay_s": np.nan, "side": "", "reason": ""}
            if i < 0:
                rows.append({**rec, "reason": "no_old_book"})
                continue
            ob, oa = bid[i], ask[i]
            mb = (not np.isnan(ob)) and abs(p - ob) <= TOL
            ma = (not np.isnan(oa)) and abs(p - oa) <= TOL
            if mb and ma:
                rows.append({**rec, "reason": "matches_both"})
                continue
            if not (mb or ma):
                rows.append({**rec, "reason": "matches_neither"})
                continue
            side, old, arr = ("bid", ob, bid) if mb else ("ask", oa, ask)
            delay = np.nan
            j = i + 1
            while j < len(ts) and ts[j] - tv <= 30 * NS:
                v = arr[j]
                changed = (np.isnan(v) != np.isnan(old)) or (not np.isnan(v) and abs(v - old) > TOL)
                if changed:
                    delay = (ts[j] - tv) / NS
                    break
                j += 1
            if np.isnan(delay):
                rows.append({**rec, "side": side, "reason": "no_change_30s"})
            else:
                rows.append({**rec, "side": side, "delay_s": delay, "reason": "matched"})
    r = pd.DataFrame(rows)
    write_csv(OUT / "h3_trade_delays.csv", r)
    m = r[r.reason == "matched"]
    pgm = m.groupby("game_id")["delay_s"].agg(n_matched="size", median_s="median").reset_index()
    pga = r[r.reason != "matched"].groupby("game_id").size().rename("n_ambiguous").reset_index()
    pgt = pgm.merge(pga, on="game_id", how="outer").fillna({"n_matched": 0, "n_ambiguous": 0})
    write_csv(OUT / "h3_per_game_medians.csv", pgt)
    reasons = r.reason.value_counts().to_dict()
    summ = {"n_trades_in_windows": len(r), "n_matched": len(m),
            "n_ambiguous": int((r.reason != "matched").sum()),
            **{f"n_{k}": int(v) for k, v in reasons.items() if k != "matched"},
            "delay_median_s": float(m.delay_s.median()), "delay_p10_s": float(m.delay_s.quantile(0.10)),
            "delay_p90_s": float(m.delay_s.quantile(0.90)), "delay_mean_s": float(m.delay_s.mean()),
            "n_matched_bid_side": int((m.side == "bid").sum()), "n_matched_ask_side": int((m.side == "ask").sum()),
            "share_delay_le_1s": float((m.delay_s <= 1).mean()), "share_delay_le_2s": float((m.delay_s <= 2).mean())}
    write_csv(OUT / "h3_summary.csv", pd.DataFrame([summ]))
    write(OUT / "h3_rule.md", "\n" + H3_RULE + "\n\n" + md(pd.DataFrame([summ]).T.reset_index().set_axis(['stat','value'], axis=1)) + "\n\n"
          + md(pgt) + "\n")
    print(pd.DataFrame([summ]).T.to_string())
    print(pgt.to_string(index=False))


# ---------- h4 ----------

def confirm(s: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    """Adds entry_conf, exit_conf, both_conf and the nearest confirming (or nearest any) print per leg."""
    gs, _ = games()
    slug = dict(zip(gs.game_id, gs.slug))
    by = {k: (v.tv.to_numpy(), v.home_price.to_numpy()) for k, v in d.groupby("slug")}
    out = []
    for r in s.itertuples():
        rec = {}
        tv, hp = by.get(slug.get(r.game_id), (np.array([], dtype="int64"), np.array([])))
        for leg, t, px, buy in (("entry", r.entry_fill_ns, r.entry_px, r.direction == 1),
                                ("exit", r.exit_fill_ns, r.exit_px, r.direction != 1)):
            w = (tv >= t - NS) & (tv <= t + 2 * NS)
            ok = w & ((hp <= px + TOL) if buy else (hp >= px - TOL))
            rec[f"{leg}_conf"] = bool(ok.any())
            rec[f"{leg}_n_prints_window"] = int(w.sum())
            pick = ok if ok.any() else w
            if pick.any():
                k = np.flatnonzero(pick)[np.argmin(np.abs(tv[pick] - t))]
                rec[f"{leg}_tns_ts"], rec[f"{leg}_tns_home_price"] = int(tv[k]), float(hp[k])
            else:
                rec[f"{leg}_tns_ts"], rec[f"{leg}_tns_home_price"] = np.nan, np.nan
        out.append(rec)
    c = pd.DataFrame(out, index=s.index)
    s = pd.concat([s, c], axis=1)
    s["both_conf"] = s.entry_conf & s.exit_conf
    return s


def stats(f: pd.DataFrame, label: str) -> dict:
    if not len(f):
        return {"set": label, "n_fills": 0}
    pg = f.groupby("game_id")
    e = pg["edge_cents_per_contract"]
    lo, hi = L.game_bootstrap_ci(e.sum().to_numpy(), e.size().to_numpy())
    pnl = pg["pnl_cents"].sum()
    top5 = pnl.sort_values(ascending=False).index[:5]
    rest = f[~f.game_id.isin(top5)]
    return {"set": label, "n_fills": len(f), "n_games": int(pg.ngroups),
            "mean_net_c_per_contract": float(f.edge_cents_per_contract.mean()),
            "ci95_low": lo, "ci95_high": hi,
            "share_games_pnl_pos": float((pnl > 0).mean()),
            "mean_net_c_excl_top5_games": float(rest.edge_cents_per_contract.mean()) if len(rest) else np.nan,
            "n_fills_excl_top5": len(rest)}


def h4_block(t: pd.DataFrame, lats, tag: str, src: str) -> pd.DataFrame:
    d = tns()
    rows, legs = [], []
    for lat in lats:
        s = confirm(subset(t, lat), d)
        s["latency_s"] = lat
        legs.append(s)
        base = {"source": src, "latency_s": lat, "share_entry_confirmed": float(s.entry_conf.mean()),
                "share_exit_confirmed": float(s.exit_conf.mean()), "share_both_confirmed": float(s.both_conf.mean())}
        rows.append({**base, **stats(s, "all subset fills")})
        rows.append({**base, **stats(s[s.both_conf], "both legs confirmed")})
    r = pd.DataFrame(rows)
    write_csv(OUT / f"h4_{tag}_summary.csv", r)
    write_csv(OUT / f"h4_{tag}_legs.csv", pd.concat(legs, ignore_index=True))
    return r


def h4() -> None:
    t = run_trades()
    r = h4_block(t, (1.0, 2.0), "run", "results/holdout/laggard_trades.csv")
    curve = pd.read_csv(SL / "results" / "holdout" / "laggard_latency_curve.csv")
    full = curve[(curve.venue == "polymarket_us") & curve.latency_s.isin([1.0, 2.0])]
    write(OUT / "h4_rule.md", "\n" + H4_RULE + "\n\nTop 5 games = the 5 largest per-game sums of pnl_cents. CI = "
          "laggard.game_bootstrap_ci(per-game sum, per-game n) of edge_cents_per_contract.\n\n"
          + md(r) + "\n\nFull run (all fills, no 17:00 cut), laggard_latency_curve.csv:\n\n"
          + md(full) + "\n")
    print(r.T.to_string())
    print(full.to_string(index=False))


def h4delay() -> None:
    p, c = OUT / "g_laggard_trades.parquet", OUT / "g_latency_curves.csv"
    t0 = time.time()
    last = -1
    while True:
        if p.exists():
            sz = p.stat().st_size
            if c.exists() or sz == last:
                break
            last = sz
        if time.time() - t0 > 40 * 60:
            write(OUT / "h4_delay_adjusted.md", "\ng_laggard_trades.parquet did not appear within 40 min.\n")
            print("timeout")
            return
        time.sleep(60)
    time.sleep(5)
    d = float(read_csv(OUT / "h3_summary.csv")["delay_median_s"].iloc[0])
    t = pd.read_parquet(p)
    pu = t[t.venue == "polymarket_us"]
    avail = sorted(pu.latency_s.unique())
    pick = [min(avail, key=lambda a: (abs(a - (b + d)), a)) for b in (1.0, 2.0)]
    chk = len(subset(t, 1.0))
    r = h4_block(t, pick, "delay_adjusted", "results/holdout_diag/g_laggard_trades.parquet")
    write(OUT / "h4_delay_adjusted.md",
          f"\nh3 median delay d = {d} s. Available polymarket_us latencies: {avail}. Nearest to 1 + d = {1 + d}: "
          f"{pick[0]}; nearest to 2 + d = {2 + d}: {pick[1]} (lower on a tie). Consistency: parquet 1 s subset "
          f"n = {chk} (run file: 604).\n\n" + H4_RULE + "\n\n" + md(r) + "\n")
    print(d, avail, pick, chk)
    print(r.T.to_string())


# ---------- h5 ----------

def h5() -> None:
    gs, machines = games()
    s = read_csv(OUT / "h4_run_legs.csv")
    s = s[s.latency_s == 1.0]
    both = s[s.both_conf.astype(bool)].sample(5, random_state=20261003)
    unc = s[~s.both_conf.astype(bool)].sample(5, random_state=20261003)
    gmap = {g.game_id: g for g in gs.itertuples()}
    books = {}
    rows = []

    def et(ns):
        return "" if pd.isna(ns) else pd.Timestamp(int(ns), tz="UTC").tz_convert(ET).strftime("%Y-%m-%d %H:%M:%S.%f")

    for grp, x in (("both confirmed", both), ("unconfirmed (>= 1 leg)", unc)):
        for r in x.itertuples():
            if r.game_id not in books:
                books[r.game_id] = load_book(machines, gmap[r.game_id])
            q = books[r.game_id]
            i = int(np.searchsorted(q.ts.to_numpy(), int(r.entry_fill_ns), side="right")) - 1
            rows.append({"group": grp, "game_id": r.game_id, "decision_et": et((r.entry_g + 1) * NS),
                         "direction": int(r.direction), "entry_fill_et": et(r.entry_fill_ns), "entry_px": r.entry_px,
                         "entry_confirmed": bool(r.entry_conf), "entry_tns_et": et(r.entry_tns_ts),
                         "entry_tns_home_px": r.entry_tns_home_price, "entry_prints_in_window": r.entry_n_prints_window,
                         "exit_fill_et": et(r.exit_fill_ns), "exit_px": r.exit_px, "exit_reason": r.exit_reason,
                         "exit_confirmed": bool(r.exit_conf), "exit_tns_et": et(r.exit_tns_ts),
                         "exit_tns_home_px": r.exit_tns_home_price, "exit_prints_in_window": r.exit_n_prints_window,
                         "fee_entry": r.fee_entry, "fee_exit": r.fee_exit,
                         "net_c_per_contract": r.edge_cents_per_contract,
                         "entry_snapshot_et": et(q.ts.iloc[i]) if i >= 0 else "",
                         "entry_snapshot_bid": q.bid.iloc[i] if i >= 0 else np.nan,
                         "entry_snapshot_ask": q.ask.iloc[i] if i >= 0 else np.nan})
    r = pd.DataFrame(rows)
    write_csv(OUT / "h5_sample_fills.csv", r)
    write(OUT / "h5_sample_fills.md", "\nT&S columns: the confirming print nearest in time to the fill, or, if the "
          "leg is unconfirmed, the nearest print in [fill - 1 s, fill + 2 s] (blank if none). random_state 20261003.\n\n"
          + md(r) + "\n")
    print(r.to_string(index=False))


if __name__ == "__main__":
    {"h2": h2, "orient": orient, "h3": h3, "h4": h4, "h5": h5, "h4delay": h4delay}[sys.argv[1]]()
