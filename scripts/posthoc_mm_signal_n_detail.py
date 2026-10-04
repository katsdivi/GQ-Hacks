"""Descriptive detail of the N (no-signal) maker on polymarket.com, from the cached fills of posthoc-mm-signal (b346230).

Label: descriptive, post-hoc, not pre-registered, one day. No new parameters, no new strategy, no API calls.
Verifies the cache reproduces 428 fills / $46.53 first. Books are re-read from the same local Vultr files with the
committed loader (scripts/posthoc_mm_signal.py) only to measure the quoted spread at each fill and the price paths.

Usage (cwd = repo root, PYTHONPATH=.:scripts): python scripts/posthoc_mm_signal_n_detail.py
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

import posthoc_mm_signal as M

NS = M.NS
OUT = Path("results/posthoc_mm_signal")
ROOT = M.ROOT


def espn_scores() -> list[dict]:
    rows = []
    for f in glob.glob(str(ROOT / "data/holdout_raw/espn/*.json")):
        for e in json.loads(Path(f).read_text()).get("events", []):
            c = (e.get("competitions") or [None])[0]
            if not c or len(c.get("competitors", [])) != 2:
                continue
            t = {x["homeAway"]: x for x in c["competitors"]}
            rows.append({"date": pd.Timestamp(c.get("date") or e["date"]).tz_convert("UTC"),
                         "home": t["home"]["team"].get("displayName", ""), "away": t["away"]["team"].get("displayName", ""),
                         "hs": t["home"].get("score"), "as": t["away"].get("score"),
                         "status": c["status"]["type"]["name"]})
    return rows


def md(df: pd.DataFrame, index: bool = True) -> str:
    d = df.reset_index() if index else df
    cols = [str(c) for c in d.columns]
    rows = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in d.itertuples(index=False):
        rows.append("| " + " | ".join(f"{v:.4g}" if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(rows)


def main() -> None:
    import holdout_mid as H
    import ingest.kalshi_only_train as T
    F = pd.read_parquet("data/mm_cache/fills.parquet")
    n = F[(F.venue == "polymarket.com") & (F.maker == "N")].sort_values(["game", "t"], kind="stable").copy()
    assert len(n) == 428 and round(n.pnl60.sum(), 2) == 46.53, "cache does not reproduce 428 fills / $46.53"
    n["payout"] = n["price"] + n["pnlset"] / (n["side"] * n["qty"])     # fee 0 on polymarket.com
    q = M.pm_windows()
    maps = H.load_maps(ROOT / "data/live/holdout_maps")
    ev = pd.read_csv(ROOT / "data/holdout_raw/events.csv").set_index("game_id")
    scores = espn_scores()
    ld = M.Loader()
    inv_rows, spread_rows, game_rows = [], [], []
    for _, a in q.iterrows():
        gid = a.game_id
        lo, hi, ko = int(a.window_start_ns), int(a.window_end_ns), int(a.ko.value)
        inst = H.instruments(a, maps)
        pt = ld.rows("polymarket", inst["polymarket"], lo, hi)
        pb = ld.book("polymarket", pt)
        home = gid.split("_")[-1].upper()
        kt = ld.rows("kalshi", f"{a.kalshi_ticker}-{home}", lo, hi)
        ktr = kt[(kt["kind"] == "trade") & kt["src_ts_ns"].notna()]
        last_k = int(ktr["src_ts_ns"].max()) if len(ktr) else hi
        g = n[n.game == gid]
        # (1) inventory path, time-weighted over the quoting window [lo, hi) minus the kickoff cut
        cut_lo, cut_hi = ko + M.CUT[0], ko + M.CUT[1]
        times = [lo] + g["t"].tolist() + [hi]
        inv = np.concatenate([[0.0], np.cumsum((g["side"] * g["qty"]).to_numpy(float))])
        dur_total = dur_cap = 0.0
        for i in range(len(times) - 1):
            s, e = max(times[i], lo), min(times[i + 1], hi)
            if e <= s:
                continue
            seg = (e - s) - max(0, min(e, cut_hi) - max(s, cut_lo))
            dur_total += seg
            if abs(inv[i]) >= M.INV_LIM - M.EPS:
                dur_cap += seg
        # (3) quoted spread at each fill (book just before the fill) and phase
        if len(g):
            i = pb.idx(g["t"].to_numpy(np.int64) - 1)
            ii = np.maximum(i, 0)
            sp = np.where(i >= 0, pb.ask[ii] - pb.bid[ii], np.nan)
            mid_lo, mid_hi = ko + 20 * 60 * NS, max(last_k, ko + 20 * 60 * NS)
            midpoint = (mid_lo + mid_hi) // 2
            phase = np.where(g["t"].to_numpy(np.int64) < ko, "pre-game",
                             np.where(g["t"].to_numpy(np.int64) < midpoint, "first half", "second half"))
            spread_rows.append(g.assign(spread_c=np.round(sp * 100, 6), phase=phase))
        # (2) FIFO round trips
        lots, rt_pnl, rt_q = [], 0.0, 0.0
        for r in g.itertuples():
            qleft = r.qty
            while qleft > M.EPS and lots and np.sign(lots[0][0]) != r.side:
                lq, lp = lots[0]
                m = min(abs(lq), qleft)
                buy_px, sell_px = (lp, r.price) if lq > 0 else (r.price, lp)
                rt_pnl += (sell_px - buy_px) * m
                rt_q += m
                qleft -= m
                lots[0] = (lq - np.sign(lq) * m, lp)
                if abs(lots[0][0]) <= M.EPS:
                    lots.pop(0)
            if qleft > M.EPS:
                lots.append((r.side * qleft, r.price))
        payout = float(g["payout"].iloc[0]) if len(g) else np.nan
        un_q = sum(l[0] for l in lots)
        un_pnl = sum(l[0] * (payout - l[1]) for l in lots) if lots else 0.0
        # what happened, from price paths
        mids = (pb.bid + pb.ask) / 2
        pre = pb.mid(np.array([ko - 5 * 60 * NS]))[0]
        late_lo = midpoint if len(g) else (ko + hi) // 2
        sel = (pb.ts >= late_lo) & ~np.isnan(mids)
        big = np.nan
        if sel.sum() > 1:
            s = pd.Series(mids[sel], index=pd.to_datetime(pb.ts[sel]))
            r10 = s.resample("10min").last().ffill()
            big = float(r10.diff().abs().max())
        e = ev.loc[gid] if gid in ev.index else None
        margin = ""
        if e is not None:
            best = None
            for sc in scores:
                if pd.isna(e.espn_kickoff) or abs((sc["date"] - pd.Timestamp(e.espn_kickoff)).total_seconds()) > 60:
                    continue
                s1 = T._name_score(e.k_home, e.k_home_code, {"displayName": sc["home"]}) + \
                    T._name_score(e.k_away, e.k_away_code, {"displayName": sc["away"]})
                if s1 >= 1.4 and (best is None or s1 > best[0]):
                    best = (s1, sc)
            if best:
                sc = best[1]
                margin = f"{sc['home']} {sc['hs']} - {sc['away']} {sc['as']} ({sc['status']})"
        game_rows.append({"game": gid, "fills": len(g), "contracts": float(g["qty"].sum()), "pnl60": float(g["pnl60"].sum()),
                          "pnlset": float(g["pnlset"].sum()),
                          "max_abs_inv": float(np.abs(inv).max()), "share_time_at_cap": dur_cap / dur_total if dur_total else np.nan,
                          "rt_contracts": rt_q, "rt_pnl": rt_pnl, "unmatched_contracts": float(un_q), "unmatched_settle_pnl": float(un_pnl),
                          "median_spread_c": float(np.nanmedian(spread_rows[-1]["spread_c"])) if len(g) else np.nan,
                          "pre_game_home_mid": float(pre), "home_payout": payout,
                          "largest_late_10min_move_c": round(100 * big, 1) if big == big else np.nan, "final_score": margin})
        print(f"{gid} fills={len(g)}", flush=True)
    G = pd.DataFrame(game_rows)
    S = pd.concat(spread_rows, ignore_index=True)
    S["bucket"] = np.where(S["spread_c"] <= 1.0 + 1e-6, "1c", np.where(S["spread_c"] <= 2.0 + 1e-6, "2c",
                           np.where(S["spread_c"] > 2.0, "3c+", "unknown")))
    by_b = S.groupby("bucket").agg(fills=("qty", "size"), contracts=("qty", "sum"), pnl60=("pnl60", "sum"),
                                   pnlset=("pnlset", "sum"))
    by_p = S.groupby("phase").agg(fills=("qty", "size"), contracts=("qty", "sum"), pnl60=("pnl60", "sum"),
                                  pnlset=("pnlset", "sum"))
    for t in (by_b, by_p):
        t["pnl60_c_per_contract"] = 100 * t["pnl60"] / t["contracts"]
        t["pnlset_c_per_contract"] = 100 * t["pnlset"] / t["contracts"]
    G.to_csv(OUT / "n_detail_games.csv", index=False)
    by_b.to_csv(OUT / "n_detail_spread.csv")
    by_p.to_csv(OUT / "n_detail_phase.csv")
    wf = G[G.fills > 0]
    top = wf.sort_values("pnl60", ascending=False).head(5)
    lines = ["# N maker on polymarket.com: inventory, round trips, spread and phase, top games",
             "", "**Label: descriptive, post-hoc, not pre-registered, one day.** From the cached N fills of b346230 "
             "(verified 428 fills, +60 s $46.53). Books re-read from the same local Vultr files with the committed loader.",
             "Phase split: ESPN halftime is not available in local holdout data, so the game window (kickoff + 20 min to the "
             "game's last Kalshi home-market trade in the window) is split at its midpoint; fills before kickoff are "
             "'pre-game'. Quoted spread = polymarket.com ask minus bid just before the fill. Time at cap is time-weighted "
             "over the quoting window, excluding the kickoff cut.", "",
             "## (1) Inventory", "",
             f"- games with fills: {len(wf)} of {len(G)}",
             f"- max absolute inventory per game: median {wf.max_abs_inv.median():.0f}, max {wf.max_abs_inv.max():.0f} contracts",
             f"- games that ever reached the +/- 50 cap: {(wf.max_abs_inv >= 50 - 1e-9).sum()}",
             f"- time-weighted share of the quoting window at the cap: median {wf.share_time_at_cap.median():.3f}, "
             f"mean {wf.share_time_at_cap.mean():.3f}, max {wf.share_time_at_cap.max():.3f}", "",
             "## (2) FIFO round trips", "",
             f"- matched round-trip contracts: {G.rt_contracts.sum():.0f}, realized P&L ${G.rt_pnl.sum():.2f} "
             f"({100 * G.rt_pnl.sum() / max(G.rt_contracts.sum(), 1):.2f} c per matched contract)",
             f"- unmatched inventory at the end: net {G.unmatched_contracts.sum():+.0f} contracts summed over games "
             f"(gross {G.unmatched_contracts.abs().sum():.0f}), settlement P&L ${G.unmatched_settle_pnl.sum():.2f}",
             f"- check: round trips + unmatched at settlement = ${G.rt_pnl.sum() + G.unmatched_settle_pnl.sum():.2f} vs "
             f"held-to-settlement P&L ${G.pnlset.sum():.2f}", "",
             "## (3) P&L per contract by quoted spread and by phase", "",
             md(by_b), "", md(by_p), "",
             "## (4) Top 5 games by +60 s P&L", "",
             md(top[["game", "fills", "contracts", "median_spread_c", "max_abs_inv", "share_time_at_cap", "pnl60", "pnlset",
                  "pre_game_home_mid", "home_payout", "largest_late_10min_move_c", "final_score"]], index=False), ""]
    for r in top.itertuples():
        fav = "home" if r.pre_game_home_mid >= 0.5 else "away"
        won = "home" if r.home_payout >= 0.5 else "away"
        kind = []
        if r.pre_game_home_mid == r.pre_game_home_mid and fav != won:
            kind.append("upset (pre-game favourite lost)")
        if r.largest_late_10min_move_c == r.largest_late_10min_move_c and r.largest_late_10min_move_c >= 20:
            kind.append(f"late swing ({r.largest_late_10min_move_c:.0f} c in 10 min in the second half)")
        if r.pre_game_home_mid == r.pre_game_home_mid and abs(r.pre_game_home_mid - 0.5) >= 0.35 and fav == won:
            kind.append("heavy favourite won (one-sided market)")
        lines.append(f"- {r.game}: pre-game home mid {r.pre_game_home_mid:.2f}, home settled {r.home_payout:.0f}; "
                     f"{'; '.join(kind) if kind else 'no late swing, no upset'}; score: {r.final_score or 'not in local ESPN files'}.")
    (OUT / "N_DETAIL.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
