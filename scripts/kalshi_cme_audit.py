"""Audit of the Kalshi-CME Stage 1 and maker results (descriptive; no new trials).

Usage (cwd = repo root, PYTHONPATH=.:scripts): python scripts/kalshi_cme_audit.py
Writes results/posthoc_kalshi_cme/audit_*.csv (no prices) and prints the audit numbers used in AUDIT.md.
"""
from __future__ import annotations

import json
import sys

import databento as db
import numpy as np
import pandas as pd

import kalshi_cme_maker as M
import kalshi_cme_stage1 as S

NS = S.NS


def load():
    m = pd.read_csv(S.DATA / "cme_train_v2" / "map.csv")
    m = m[m["cme_mbp10_rows_in_window"] > 0]
    mbp = db.DBNStore.from_file(S.DATA / "cme_train_v2" / "jan_mbp1.dbn.zst").to_df().reset_index()
    for c in ("ts_event", "ts_recv"):
        mbp[c] = mbp[c].dt.as_unit("ns").astype("int64")
    tr = pd.read_parquet(S.DATA / "fg_cg_train_trades.parquet").reset_index()
    for c in ("ts_event", "ts_recv"):
        tr[c] = tr[c].dt.as_unit("ns").astype("int64")
    ko = pd.concat([pd.read_csv(S.DATA / "kalshi_only_games.csv"),
                    pd.read_csv(S.DATA / "cme_train_v2" / "kalshi_games.csv")]).drop_duplicates("game_id")
    ko = ko.set_index("game_id")
    return m, mbp, tr, ko


def main() -> None:
    m, mbp, tr, ko = load()
    out = {}
    # 1. timestamps: Databento receive minus exchange time
    out["mbp_recv_minus_event_ms"] = {q: float(np.percentile((mbp.ts_recv - mbp.ts_event) / 1e6, q)) for q in (10, 50, 90)}
    out["trades_recv_minus_event_ms"] = {q: float(np.percentile((tr.ts_recv - tr.ts_event) / 1e6, q)) for q in (10, 50, 90)}
    games, cover, orient = {}, [], []
    for gid, grp in m.groupby("game_id"):
        r = ko.loc[gid]
        k0 = pd.Timestamp(r.kickoff_utc_espn).value
        kp = S.DATA / ("kalshi_only" if grp["kalshi_dir"].iloc[0] == "kalshi_only" else "cme_train_v2/kalshi") \
            / f"{gid}.parquet"
        kts, kpx = S.kalshi_phome(kp)
        res = float(r.settlement_result)
        con = {}
        for row in grp.itertuples():
            side = "home" if row.team == r.home else "away"
            x = mbp[mbp.symbol == row.symbol].sort_values(["ts_event", "sequence"])
            y = tr[tr.symbol == row.symbol].sort_values("ts_event")
            lo, hi = k0 - 2 * 3600 * NS, k0 + 5 * 3600 * NS
            xw, yw = x[(x.ts_event >= lo) & (x.ts_event <= hi)], y[(y.ts_event >= lo) & (y.ts_event <= hi)]
            cover.append({"symbol": row.symbol, "game": gid, "mbp_first_h": (xw.ts_event.min() - k0) / 3.6e12,
                          "mbp_last_h": (xw.ts_event.max() - k0) / 3.6e12, "trades_first_h": (yw.ts_event.min() - k0) / 3.6e12,
                          "trades_last_h": (yw.ts_event.max() - k0) / 3.6e12, "mbp_rows": len(xw), "prints": len(yw),
                          "print_size_median": float(yw["size"].median()) if len(yw) else np.nan,
                          "print_size_p90": float(yw["size"].quantile(.9)) if len(yw) else np.nan,
                          "bid_size_median": float(xw.bid_sz_00.median()), "ask_size_median": float(xw.ask_sz_00.median())})
            payout = res if side == "home" else 1 - res
            last_px = float(yw.price.iloc[-1]) if len(yw) else np.nan
            b = S.Book(x)
            last_mid = b.mid(hi)
            orient.append({"symbol": row.symbol, "game": gid, "team": row.team, "side": side, "payout": payout,
                           "last_print": last_px, "last_mid_in_window": last_mid,
                           "consistent": (abs(last_px - payout) < 0.5) if last_px == last_px else None})
            con[row.symbol] = (side, b, y.ts_event.to_numpy(np.int64), y.price.to_numpy(float),
                               y["size"].to_numpy(float), payout)
        games[gid] = {"k0": k0, "kts": kts, "kpx": kpx, "con": con}
    C = pd.DataFrame(cover)
    O = pd.DataFrame(orient)
    C.to_csv(S.OUT / "audit_coverage.csv", index=False)
    O.drop(columns=["last_print", "last_mid_in_window"]).to_csv(S.OUT / "audit_orientation.csv", index=False)
    out["orientation_consistent"] = int(O.consistent.fillna(False).sum())
    out["orientation_checked"] = int(O.consistent.notna().sum())
    sig = {g: S.signals(v["kts"], v["kpx"], v["k0"] - 2 * 3600 * NS, v["k0"] + 5 * 3600 * NS, 0.05)
           for g, v in games.items()}

    # 2/3. fill bounds, print activity, offset sensitivity (real signals only)
    rows = []
    for shift in (-2, -1, 0, 1, 2):
        for gid, g in games.items():
            for tk, d in sig[gid]:
                for sym, (side, bk, tts, tpx, tsz, payout) in g["con"].items():
                    t = tk + shift * NS                       # CME clock = Kalshi clock + shift
                    if t < bk.ts[0]:
                        continue
                    dd = d if side == "home" else -d
                    b, a, bs, as_ = bk.at(t)
                    limit, queue = (b, bs) if dd > 0 else (a, as_)
                    if not (limit == limit and queue >= 1):
                        continue
                    for W in (5, 30):
                        i = np.searchsorted(tts, t, side="right")
                        j = np.searchsorted(tts, t + W * NS, side="right")
                        p, z = tpx[i:j], tsz[i:j]
                        thr = (p < limit - S.EPS) if dd > 0 else (p > limit + S.EPS)
                        at_or = (p <= limit + S.EPS) if dd > 0 else (p >= limit - S.EPS)
                        f_strict = bool(thr.any())
                        f_upper = bool(at_or.any())
                        q_upper = float(min(10.0, z[at_or].sum())) if f_upper else 0.0
                        vol = np.cumsum(np.where(at_or, z, 0.0))
                        hitq = np.flatnonzero(vol >= queue + 10)
                        f_queue = len(hitq) > 0
                        ft = {"strict": tts[i + np.flatnonzero(thr)[0]] if f_strict else None,
                              "upper": tts[i + np.flatnonzero(at_or)[0]] if f_upper else None,
                              "queue": tts[i + hitq[0]] if f_queue else None}
                        rec = {"shift_s": shift, "game": gid, "sym": sym, "t": t, "W": W, "dir": dd, "limit": limit,
                               "queue_ahead": queue, "prints_in_W": int(j - i), "vol_at_or_through": float(vol[-1]) if len(vol) else 0.0}
                        for name, filled in (("strict", f_strict), ("upper", f_upper), ("queue", f_queue)):
                            qty = 10.0 if name != "upper" else q_upper
                            rec[f"{name}_filled"] = filled
                            if filled:
                                b6, a6, _, _ = bk.at(int(ft[name]) + 60 * NS)
                                xp = b6 if dd > 0 else a6
                                rec[f"{name}_qty"] = qty
                                rec[f"{name}_pnl_settle"] = ((payout - limit) * dd - S.FEE) * qty
                                rec[f"{name}_pnl_t60"] = (((xp - limit) * dd - 2 * S.FEE) * qty) if xp == xp else np.nan
                        rows.append(rec)
    A = pd.DataFrame(rows)
    A.drop(columns=["limit"]).to_parquet(S.CACHE / "audit_attempts.parquet", index=False)
    summ = []
    for (shift, W), g in A.groupby(["shift_s", "W"]):
        row = {"shift_s": shift, "W": W, "attempts": len(g), "any_print_in_W": float((g.prints_in_W > 0).mean()),
               "median_queue_ahead": float(g.queue_ahead.median())}
        for name in ("strict", "upper", "queue"):
            f = g[g[f"{name}_filled"]]
            row[f"{name}_fill_rate"] = float(len(f) / len(g))
            for ex in ("settle", "t60"):
                x = f.dropna(subset=[f"{name}_pnl_{ex}"])
                q = x[f"{name}_qty"].sum()
                row[f"{name}_{ex}_c_per_contract"] = float(x[f"{name}_pnl_{ex}"].sum() / q * 100) if q > 0 else np.nan
        summ.append(row)
    Sm = pd.DataFrame(summ)
    Sm.to_csv(S.OUT / "audit_fill_bounds.csv", index=False)
    # print activity per minute around signals (shift 0)
    a0 = A[(A.shift_s == 0) & (A.W == 30)]
    out["prints_per_30s_around_signals"] = {q: float(np.percentile(a0.prints_in_W, q)) for q in (25, 50, 75, 90)}
    out["prints_overall_per_min_in_window"] = float(C.prints.sum() / (7 * 60 * len(C)))
    pd.set_option("display.width", 300, "display.max_columns", 40)
    print(json.dumps(out, indent=1, default=float))
    print(C.round(2).to_string(index=False))
    print(O.to_string(index=False))
    print(Sm.round(4).to_string(index=False))
    # hand check: 5 real signals with prints in W (shift 0, W 30)
    hc = a0[a0.prints_in_W > 0].sample(5, random_state=1)
    for r in hc.itertuples():
        side, bk, tts, tpx, tsz, payout = games[r.game]["con"][r.sym]
        i = np.searchsorted(tts, r.t, side="right")
        j = np.searchsorted(tts, r.t + 30 * NS, side="right")
        kts, kpx = games[r.game]["kts"], games[r.game]["kpx"]
        ik = np.searchsorted(kts, r.t, side="right") - 1
        w = kpx[np.searchsorted(kts, r.t - 10 * NS, side="left"):ik + 1]
        print(f"\nHAND {r.game} {r.sym} t={pd.Timestamp(r.t, tz='UTC')} dir={r.dir:+d} Kalshi P(home) 10s range "
              f"{w.min():.2f}->{kpx[ik]:.2f}; CME book at t bid/ask {bk.at(r.t)[:2]} sizes {bk.at(r.t)[2:]}; "
              f"limit {r.limit} queue {r.queue_ahead:.0f}")
        for k in range(i, j):
            print(f"   print +{(tts[k] - r.t) / 1e9:6.2f}s px {tpx[k]:.2f} size {tsz[k]:.0f}")
        print(f"   strict {r.strict_filled} upper {r.upper_filled} queue {r.queue_filled}")


if __name__ == "__main__":
    sys.exit(main())
