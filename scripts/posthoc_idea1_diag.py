"""IDEA 1 diagnostic, not a variant. POST-HOC, EXPLORATORY (formed after seeing the holdout).

1) Matched-quantity P&L per trade, from the existing trade log only (results/posthoc_latency/idea1_trades.csv):
   q = min(q_home, q_away); P&L = q x 1 (hedged pair payout) - q x (price_home + price_away) - fee(price_home, q)
   - fee(price_away, q), excluding the unwind. The log has no fee column, so fees on q are recomputed with the
   same function (costs.fee via posthoc_idea1.order_fee). Game bootstrap: 2,000 draws, seed 20261003, per-game
   sums over all 88 games (games with no trade contribute 0).
2) Opportunity durations: the existing outputs hold only duration quantiles, so the opportunity runs are
   recomputed with the committed signal functions (posthoc_idea1.signal_table and runs) on the same data. No
   fills, no attempts, no P&L. The recomputed median and p90 are checked against idea1_results.csv.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import posthoc_idea1 as P

OUT = P.OUT


def main():
    t = pd.read_csv(OUT / "idea1_trades.csv")
    games = P.load_games()
    gids = [g["game_id"] for g in games]
    n = len(gids)
    rows = []
    for sched in P.SCHEDULES:
        for L in P.LATENCIES:
            d = t[(t.schedule == sched) & (t.latency_s == L)].copy()
            q = np.minimum(d.q_home, d.q_away)
            fees = [P.order_fee(ph, qq, sched) + P.order_fee(pa, qq, sched)
                    for ph, pa, qq in zip(d.price_home, d.price_away, q)]
            d["q"] = q
            d["matched_pnl"] = q * (1 - d.price_home - d.price_away) - np.array(fees)
            pg = d.groupby("game_id")["matched_pnl"].apply(np.array).to_dict()
            pg_tr = [pg.get(g, np.array([])) for g in gids]
            pg_pnl = np.array([x.sum() for x in pg_tr])
            (tlo, thi), (mlo, mhi) = P.boot(pg_pnl, pg_tr, np.random.default_rng(P.BOOT_SEED))
            m = d["matched_pnl"].to_numpy()
            rows.append(dict(label="POST-HOC EXPLORATORY; diagnostic, not a variant", schedule=sched,
                             latency_s=L, games=n, trades=len(d), matched_contracts=float(q.sum()),
                             median_matched_size=float(np.median(q)) if len(q) else np.nan,
                             matched_pnl_total=float(m.sum()), pnl_ci_lo=tlo, pnl_ci_hi=thi,
                             matched_pnl_mean=float(m.mean()) if len(m) else np.nan, mean_ci_lo=mlo,
                             mean_ci_hi=mhi, matched_fees_total=float(np.sum(fees)),
                             trades_excess_gt5=int((d.excess > 5).sum()), trades_excess_ge9=int((d.excess >= 9).sum())))
    res = pd.DataFrame(rows)
    # opportunity durations (signal only)
    rws = P.load_rows(games)
    e = pd.DataFrame(columns=["recv_ns", "kind", "price", "size"])
    dur = {s: [] for s in P.SCHEDULES}
    for g in games:
        h = P.snapshots(rws.get(g["home_tk"], e), away=False)
        a = P.snapshots(rws.get(g["away_tk"], e), away=True)
        if h.empty or a.empty:
            continue
        for s in P.SCHEDULES:
            sig = P.signal_table(h, a, g["lo"], g["hi"], g["ko"], s)
            dur[s].append(pd.concat([P.runs(sig, "yes", g["hi"]), P.runs(sig, "no", g["hi"])])["dur_s"].to_numpy(float))
    for s in P.SCHEDULES:
        x = np.concatenate(dur[s])
        k = res.schedule == s
        res.loc[k, "opps_total"] = len(x)
        res.loc[k, "opp_dur_median_s"] = np.median(x)
        res.loc[k, "opp_dur_p90_s"] = np.percentile(x, 90)
        for thr in (0.25, 0.5, 1.0):
            res.loc[k, f"share_opps_ge_{thr}s"] = float((x >= thr).mean())
            res.loc[k, f"n_opps_ge_{thr}s"] = int((x >= thr).sum())
    res.to_csv(OUT / "idea1_diagnostic_matched.csv", index=False)
    print(res.to_string())


if __name__ == "__main__":
    main()
