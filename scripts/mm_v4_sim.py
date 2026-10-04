"""SYNTHETIC SIMULATION, calibrated to one day of observed data; not market evidence; not a test of HYPOTHESIS_v4.

Spec: results/posthoc_mm_v4_extra/synthetic/SIM_SPEC.md (4c7da20, committed before any simulation).
Feeds synthetic books and trades to the committed maker (scripts/posthoc_mm_v4.py, 1d3d68a) through a thin adapter.

Usage (cwd = repo root, PYTHONPATH=.:scripts): python scripts/mm_v4_sim.py
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

import posthoc_mm_v4 as M

NS = M.NS
OUT = Path("results/posthoc_mm_v4_extra/synthetic")
LABEL = "SYNTHETIC SIMULATION, calibrated to one day of observed data; not market evidence; not a test of HYPOTHESIS_v4"
BOOT_SEED, NBOOT = 20261011, 2000
PRE_S, POST_S = 90 * 60, int(4.5 * 3600)
KO = 10**18                                          # synthetic kickoff, ns (arbitrary epoch)


@dataclass(frozen=True)
class Params:
    spread_vals: tuple
    spread_probs: tuple
    upd_per_min: float
    trades_per_min: float
    size_q: tuple                                      # (p, value) pairs
    through: float
    vol: tuple                                         # pre, h1, h2 (c per 10 s)
    jumps_per_h: float
    jump_q: tuple                                      # (p, value) pairs above 10 c
    informed: float
    d_inf: float = 0.01
    spread_shift: int = 0
    spread_fixed: int | None = None


def load_params() -> Params:
    c = json.loads((OUT / "calibration.json").read_text())
    sq = tuple(sorted((float(k), v) for k, v in c["trade_size_quantiles"].items()))
    jq = tuple(sorted((float(k), v) for k, v in c["jump_size_c_quantiles"].items()))
    return Params(tuple(c["spread_c_values"]), tuple(c["spread_c_probs"]), c["quote_updates_per_min_median"],
                  c["trades_per_min_mean"], sq, c["through_share"],
                  (c["vol10s_c"]["pre"], c["vol10s_c"]["h1"], c["vol10s_c"]["h2"]), c["jumps_per_hour_mean"], jq,
                  c["informed_share"])


def inv_cdf(rng, q: tuple, n: int, lo_p: float = 0.0, lo_v: float | None = None, cap: float | None = None):
    ps = np.array([p for p, _ in q])
    vs = np.array([v for _, v in q])
    if lo_v is not None:
        ps, vs = np.insert(ps, 0, lo_p), np.insert(vs, 0, lo_v)
    u = rng.uniform(ps[0], ps[-1], n)
    x = np.interp(u, ps, vs)
    return np.minimum(x, cap) if cap else x


def game(p: Params, rng: np.random.Generator) -> dict:
    """One synthetic game. Returns book arrays, trades, lo/hi/ko and settlement payout (home YES)."""
    T = PRE_S + POST_S
    lo, hi = KO - PRE_S * NS, KO + POST_S * NS
    sec = np.arange(T)
    t_ns = lo + sec * NS
    cut_end = PRE_S + 20 * 60
    half = cut_end + (T - cut_end) / 2
    phase_sd = np.where(sec < PRE_S, p.vol[0], np.where(sec < half, p.vol[1], p.vol[2])) / 100 / np.sqrt(10)
    steps = rng.normal(0, 1, T) * phase_sd
    jmask = (sec >= PRE_S) & (rng.uniform(size=T) < p.jumps_per_h / 3600)
    nj = int(jmask.sum())
    if nj:
        steps[jmask] += rng.choice([-1, 1], nj) * inv_cdf(rng, p.jump_q, nj, 0.0, 10.0, 30.0) / 100
    # trades (seconds) and informed impacts added to the path before cumsum (impact right after the trade)
    tsec = np.flatnonzero(rng.uniform(size=T) < p.trades_per_min / 60)
    ntr = len(tsec)
    tdir = rng.choice([-1, 1], ntr)
    inf = rng.uniform(size=ntr) < p.informed
    tsize = inv_cdf(rng, p.size_q, ntr)
    thr = rng.uniform(size=ntr) < p.through
    imp = np.zeros(T)
    nxt = np.minimum(tsec + 1, T - 1)
    np.add.at(imp, nxt[inf], tdir[inf] * p.d_inf)
    mid = np.clip(rng.uniform(0.2, 0.8) + np.cumsum(steps + imp), 0.02, 0.98)
    # book: Poisson updates plus forced update when mid leaves [bid, ask]
    upd = rng.uniform(size=T) < p.upd_per_min / 60
    bid = np.empty(T)
    ask = np.empty(T)
    vals = np.array(p.spread_vals)
    sp_draw = rng.choice(vals, T, p=np.array(p.spread_probs) / np.sum(p.spread_probs))
    b = a = None
    bts, bb, ba = [], [], []
    for s in range(T):
        m = mid[s]
        if b is None or upd[s] or m < b or m > a:
            if b is None or upd[s]:          # Poisson update: redraw the spread; forced re-centre keeps it
                sp = (p.spread_fixed if p.spread_fixed else int(sp_draw[s]) + p.spread_shift) / 100
            b = np.floor((m - sp / 2) * 100 + 1e-9) / 100
            b = min(max(b, 0.01), 0.98)
            a = min(round(b + sp, 2), 0.99)
            bts.append(s)
            bb.append(b)
            ba.append(a)
        bid[s], ask[s] = b, a
    nb = len(bts)
    bsz = inv_cdf(rng, p.size_q, nb) * 10
    asz = inv_cdf(rng, p.size_q, nb) * 10
    book = M.Book(lo + np.array(bts, np.int64) * NS, np.array(bb), np.array(ba), bsz, asz)
    tpx = np.where(tdir > 0, ask[tsec] + np.where(thr, 0.01, 0.0), bid[tsec] - np.where(thr, 0.01, 0.0))
    tts = lo + tsec.astype(np.int64) * NS + NS // 2      # trade half a second into its second, after that second's book
    payout = float(rng.uniform() < mid[-1])
    return {"book": book, "tts": tts, "tpx": np.round(tpx, 2), "tsz": tsize, "lo": lo, "hi": hi, "ko": KO,
            "payout": payout, "mid": mid, "tdir": tdir, "inf": inf, "thr": thr, "tsec": tsec}


def run_maker(g: dict, min_spread: float) -> pd.DataFrame:
    """Thin adapter: synthetic game -> committed maker simulate() and score()."""
    fl = M.simulate(g["book"], g["tts"], g["tpx"], g["tsz"], g["lo"], g["hi"], g["ko"], None, None, "F1",
                    min_spread=min_spread)
    return M.score(fl, g["book"], g["payout"], M.PM_FEE)


def boot_pc(pnl: np.ndarray, q: np.ndarray) -> tuple[float, float, float]:
    """Game bootstrap of total P&L / total contracts (cents per contract)."""
    m = q > 0
    if q.sum() == 0:
        return np.nan, np.nan, np.nan
    est = pnl.sum() / q.sum() * 100
    rng = np.random.default_rng(BOOT_SEED)
    idx = rng.integers(0, len(pnl), (NBOOT, len(pnl)))
    num, den = pnl[idx].sum(1), q[idx].sum(1)
    bs = np.where(den > 0, num / np.maximum(den, 1e-12) * 100, np.nan)
    return float(est), float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))


def scenarios(base: Params) -> list[tuple[str, Params, int, int]]:
    return [("base", base, 500, 20261011),
            ("informed_0.5x", replace(base, informed=base.informed * 0.5), 200, 20261012),
            ("informed_2x", replace(base, informed=min(1.0, base.informed * 2)), 200, 20261013),
            ("jumps_0.5x", replace(base, jumps_per_h=base.jumps_per_h * 0.5), 200, 20261014),
            ("jumps_2x", replace(base, jumps_per_h=base.jumps_per_h * 2), 200, 20261015),
            ("spread_narrow_1c", replace(base, spread_fixed=1), 200, 20261016),
            ("spread_wide_plus2c", replace(base, spread_shift=2), 200, 20261017)]


def main() -> None:
    base = load_params()
    out = []
    for name, p, n, seed in scenarios(base):
        rng = np.random.default_rng(seed)
        per = {"A": [], "B": []}
        for i in range(n):
            g = game(p, rng)
            for arm, ms in (("A", 0.0), ("B", 0.03)):
                sc = run_maker(g, ms)
                per[arm].append((float(sc["pnl60"].fillna(0).sum()) if len(sc) else 0.0,
                                 float(sc["pnlset"].sum()) if len(sc) else 0.0,
                                 float(sc["qty"].sum()) if len(sc) else 0.0, len(sc)))
        for arm in ("A", "B"):
            x = np.array(per[arm])
            e60, l60, h60 = boot_pc(x[:, 0], x[:, 2])
            es, ls, hs = boot_pc(x[:, 1], x[:, 2])
            traded = x[:, 2] > 0
            out.append({"label": LABEL, "scenario": name, "arm": arm, "games": n, "fills": int(x[:, 3].sum()),
                        "contracts": float(x[:, 2].sum()), "pnl60_c_pc": e60, "pnl60_lo": l60, "pnl60_hi": h60,
                        "pnlset_c_pc": es, "pnlset_lo": ls, "pnlset_hi": hs,
                        "share_games_pos60_traded": float((x[traded, 0] > 0).mean()) if traded.any() else np.nan})
        print(name, [f"{r['arm']} {r['pnl60_c_pc']:.2f} [{r['pnl60_lo']:.2f},{r['pnl60_hi']:.2f}]" for r in out[-2:]],
              flush=True)
    R = pd.DataFrame(out)
    R.to_csv(OUT / "results.csv", index=False)
    cols = [c for c in R.columns if c != "label"]
    f = lambda v: f"{v:.3g}" if isinstance(v, float) else str(v)
    lines = [f"# Synthetic simulation results ({LABEL})", "",
             "Spec 4c7da20. One run. P&L in cents per contract (total P&L / total contracts); CI = game bootstrap, 2,000 "
             "reps, seed 20261011. Observed day for comparison (N maker, 88 real games, 863eb69): +1.09 c [0.17, 2.12] "
             "at +60 s.", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(f(v) for v in r) + " |" for r in R[cols].itertuples(index=False)]
    (OUT / "RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
