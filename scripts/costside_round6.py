"""Post-hoc cost-side search, Round 6 (SPEC.md Round 6: Kalshi microstructure BIG, IMB, GAP; 16 trials).

post-hoc, exploratory; training only. Usage (cwd = repo root, PYTHONPATH=.:scripts):
  python scripts/costside_round6.py
"""
from __future__ import annotations

import pickle
import sys

import numpy as np
import pandas as pd

import costside_common as C
import costside_round1 as R1


def registry() -> list[dict]:
    r = []
    for d in ("follow", "fade"):
        for em in ("taker", "maker"):
            r.append({"trial": f"R6.BIG.{d}.{em}", "method": "large single print (>p99 and >=1000)",
                      "params": f"dir={d} exec={em}", "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"})
    for w in (10, 60, 120):
        for em in ("taker", "maker"):
            r.append({"trial": f"R6.IMB.follow.w{w}.{em}", "method": "aggressor imbalance |I|>=0.8, vol>=500",
                      "params": f"follow w={w}s exec={em}", "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"})
    for em in ("taker", "maker"):
        r.append({"trial": f"R6.IMB.fade.w60.{em}", "method": "aggressor imbalance |I|>=0.8, vol>=500",
                  "params": f"fade w=60s exec={em}", "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"})
    for gsec in (120, 300):
        for em in ("taker", "maker"):
            r.append({"trial": f"R6.GAP.g{gsec}.{em}", "method": "first trade after no-trade gap, move >= 0.03, follow",
                      "params": f"g={gsec}s exec={em}", "cost_line": "taker" if em == "taker" else "maker175 (alt maker0)"})
    assert len(r) == 16
    return [{**x, "round": 6} for x in r]


def micro(gid: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    t = pd.read_parquet(C.DATA / "raw" / "kalshi_only" / f"{gid}.parquet", columns=["ts", "kind", "price", "size", "side"])
    t = t[t.kind == "trade"].sort_values("ts", kind="stable")
    sgn = np.where(t.side.to_numpy() == "buy", 1, np.where(t.side.to_numpy() == "sell", -1, 0))
    return t.ts.to_numpy(np.int64), t.price.to_numpy(float), t["size"].to_numpy(float), sgn


def signals(g, ts, px, sz, sg):
    ko = g["kickoff_ns"]
    lo, hi = ko + 20 * 60 * C.NS, ko + 4 * 3600 * C.NS
    w = np.flatnonzero((ts >= lo) & (ts <= hi))
    out = {}
    if len(w) == 0:
        return out
    # BIG: threshold from earlier in-window prints only
    big = []
    for k, i in enumerate(w):
        if k >= 200:
            prior = sz[w[:k]]
            if sz[i] >= 1000 and sz[i] > np.percentile(prior, 99) and sg[i] != 0:
                big.append((int(ts[i]), int(sg[i])))
                break
    for d in ("follow", "fade"):
        out[f"BIG.{d}"] = [(t, s if d == "follow" else -s) for t, s in big]
    # IMB: trailing window [t - w, t]
    cs_signed = np.concatenate([[0.0], np.cumsum(sz * sg)])
    cs_tot = np.concatenate([[0.0], np.cumsum(sz)])
    for wsec in (10, 60, 120):
        j0 = np.searchsorted(ts, ts[w] - wsec * C.NS, side="left")
        net = cs_signed[w + 1] - cs_signed[j0]
        tot = cs_tot[w + 1] - cs_tot[j0]
        I = np.where(tot > 0, net / np.where(tot > 0, tot, 1), 0)
        ok = np.flatnonzero((np.abs(I) >= 0.8) & (tot >= 500))
        sig = [(int(ts[w[k]]), int(np.sign(I[k]))) for k in ok[:1]]
        out[f"IMB.follow.w{wsec}"] = sig
        if wsec == 60:
            out["IMB.fade.w60"] = [(t, -s) for t, s in sig]
    # GAP
    for gsec in (120, 300):
        sig = []
        for i in w:
            if i == 0:
                continue
            if ts[i] - ts[i - 1] >= gsec * C.NS and abs(px[i] - px[i - 1]) >= 0.03 - 1e-9:
                sig.append((int(ts[i]), 1 if px[i] > px[i - 1] else -1))
                break
        out[f"GAP.g{gsec}"] = sig
    return out


def main() -> None:
    games = C.load_games()
    wk, hist = C.week_index(games)
    pd.DataFrame(registry()).to_csv(C.CACHE / "registry_round6.csv", index=False)
    rows = []
    for g in games:
        if wk[g["game_id"]] < hist:
            continue
        ts, px, sz, sg = micro(g["game_id"])
        team_of = lambda dirn, g=g: g["home"] if dirn > 0 else g["away"]
        for name, sig in signals(g, ts, px, sz, sg).items():
            for em in ("taker", "maker"):
                rows += R1.run_sequential(g, sig, team_of, f"R6.{name}.{em}", em, None, {"week": wk[g["game_id"]]})
    pd.DataFrame(rows).to_parquet(C.CACHE / "trades_round6.parquet")
    print("rows", len(rows))


if __name__ == "__main__":
    sys.exit(main())
