"""B cross-venue orientation check (docs/holdout_run_disclosure.md, "B orientation check (rule fixed before the
holdout run)").

For every Strategy B game, Kalshi P(home) K and polymarket.com P(home) PM at each B decision time of the selected
setting (k = 5 c, m = 10 s, T = 300 s): every entry and every exit decision, filled or not. K and PM are Strategy
B's own grid prices (strategy_b.venue_grid: trailing 3 s median of trades, carried forward) at the label the
decision uses (a decision stamped (g + 1) s uses label g).
  FLAGGED (likely orientation flip): at the game's median decision time, |K - PM| > 0.20 AND |K - (1 - PM)| < 0.05
    AND |K - 0.5| > 0.10.
  Reported for all games: the median over games of each game's median |K - PM| over its decision times, and the
    count of games whose median |K - PM| > 0.10.
Note: B decides only where |K - PM| >= k (5 c) for m seconds, so |K - PM| at decision times is large by
construction; the kickoff - 5 min check in run_strategy_b.py --check is the unselected version.

Usage: python scripts/b_orientation_check.py --training   (reads out/strategy_b/trades.parquet and data/ticks/)
       python scripts/b_orientation_check.py --trades <B trades parquet> --kalshi-dir <dir> --pm-dir <dir>
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import strategy_b as B

NS = B.NS
SEL = (0.05, 10, 300)


def game_check(dec_ns: np.ndarray, kt: pd.DataFrame, pt: pd.DataFrame) -> dict:
    labels = np.sort(dec_ns) // NS - 1
    lo_g, hi_g = int(labels.min()), int(labels.max())
    kp, _ = B.venue_grid(kt, "kalshi", lo_g, hi_g)
    pp, _ = B.venue_grid(pt, "polymarket", lo_g, hi_g)
    k, p = kp[labels - lo_g], pp[labels - lo_g]
    ok = ~(np.isnan(k) | np.isnan(p))
    if not ok.any():
        return {"n_decisions": len(labels), "evaluable": False}
    k, p, lab = k[ok], p[ok], labels[ok]
    i = len(lab) // 2                       # median decision time (by time order; lower middle for even counts)
    km, pm = float(k[i]), float(p[i])
    flagged = abs(km - pm) > 0.20 and abs(km - (1 - pm)) < 0.05 and abs(km - 0.5) > 0.10
    return {"n_decisions": len(labels), "evaluable": True, "median_abs_diff": float(np.median(np.abs(k - p))),
            "K_at_median": km, "PM_at_median": pm, "flagged": bool(flagged)}


def run(trades: pd.DataFrame, kdir: Path, pdir: Path, kfmt: str, pfmt: str) -> pd.DataFrame:
    t = trades[(trades["k"] == SEL[0]) & (trades["m"] == SEL[1]) & (trades["T"] == SEL[2])]
    rows = []
    for gid, d in t.groupby("game_id"):
        dec = np.concatenate([d["entry_dec_ns"].to_numpy("int64"), d["exit_dec_ns"].to_numpy("int64")])
        kt = pd.read_parquet(kdir / kfmt.format(gid))
        pt = pd.read_parquet(pdir / pfmt.format(gid))
        rows.append({"game_id": gid, **game_check(dec, kt, pt)})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--training", action="store_true")
    ap.add_argument("--trades")
    ap.add_argument("--kalshi-dir")
    ap.add_argument("--pm-dir")
    a = ap.parse_args()
    if a.training:
        r = run(pd.read_parquet("out/strategy_b/trades.parquet"), Path("data/ticks"), Path("data/ticks"),
                "{}_kalshi.parquet", "{}_polymarket.parquet")
        n_games = len(pd.read_csv("out/strategy_b/b_games_espn.csv")) - 14
    else:
        r = run(pd.read_parquet(a.trades), Path(a.kalshi_dir), Path(a.pm_dir), "{}.parquet", "{}.parquet")
        n_games = None
    e = r[r["evaluable"].astype(bool)] if len(r) else r
    print(f"B games{f' in sample {n_games}' if n_games else ''}; with B decisions (selected setting) {len(r)}; "
          f"evaluable {len(e)}")
    if len(e):
        print(f"FLAGGED: {int(e['flagged'].sum())} {sorted(e.loc[e['flagged'], 'game_id'])}")
        print(f"median over games of median |K - PM| at decision times: {e['median_abs_diff'].median():.4f}; "
              f"games with median |K - PM| > 0.10: {int((e['median_abs_diff'] > 0.10).sum())}")


if __name__ == "__main__":
    main()
