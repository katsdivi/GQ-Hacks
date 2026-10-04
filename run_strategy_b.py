"""Strategy B on TRAINING games only (HYPOTHESIS_v3.md Strategy B + Amendment 1). Holdout never loaded.

  python run_strategy_b.py --check   orientation check only: Kalshi vs polymarket.com P(home), both 3 s medians,
                                     at ESPN kickoff - 5 min where both are valid (trade in the last 60 s).
                                     PASS = median |diff| <= 3 cents and < 2% of games with |diff| > 10 cents.
  python run_strategy_b.py           the 8 settings and their unrelated-game placebo; summary, selection (v3
                                     rule), costs x2 for the selected setting; appends experiments/variants.csv.
Games: the 977 T8 games (data/raw/t8_game_plan.csv) with ESPN kickoffs (out/strategy_b/b_games_espn.csv),
minus games whose T8 download window does not cover [ESPN - 30 min, ESPN + 4.5 h] (v3 Amendment 1 section 3:
the 14 listed games; asserted). At most 2 worker processes (the Mac is the backup recorder).
"""
from __future__ import annotations

import argparse
import subprocess
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

import strategy_b as B

TICKS = Path("data/ticks")
OUT = Path("out/strategy_b")
VARIANTS = Path("experiments/variants.csv")
SEED, N_BOOT = 20261003, 2000
EXCLUDED_A1 = {"cfb_20251129_ore_wash", "cfb_20251129_cin_tcu", "cfb_20251129_hou_bay", "cfb_20251129_colo_ksu",
               "nfl_20251208_phi_lac", "nfl_20251225_det_min", "nfl_20251225_den_kc", "cfb_20250913_usc_pur",
               "cfb_20251129_ucla_usc", "cfb_20250913_fau_fiu", "cfb_20251018_txam_ark", "cfb_20250920_tem_gt",
               "cfb_20251018_utsa_unt", "cfb_20250913_ull_mizz"}
NS = B.NS


def games() -> pd.DataFrame:
    g = pd.read_csv(OUT / "b_games_espn.csv")
    t8 = pd.to_datetime(g["t8_kickoff"], utc=True)
    es = pd.to_datetime(g["espn_kickoff"], utc=True)
    g["covered"] = (t8 - pd.Timedelta(hours=2) <= es - pd.Timedelta(minutes=30)) & \
                   (t8 + pd.Timedelta(hours=5) >= es + pd.Timedelta(hours=4.5))
    assert set(g.loc[~g["covered"], "game_id"]) == EXCLUDED_A1, "coverage exclusions differ from Amendment 1 list"
    assert (es < B.SEAL).all(), "training only"
    return g


def load(gid: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_parquet(TICKS / f"{gid}_kalshi.parquet"), pd.read_parquet(TICKS / f"{gid}_polymarket.parquet")


def check_one(row: tuple[str, str]) -> dict:
    gid, ko = row
    kt, pt = load(gid)
    t_g = pd.Timestamp(ko).value // NS - 5 * 60
    g = B.build_grid(kt, pt, t_g * NS, (t_g + 1) * NS)
    return {"game_id": gid, "valid": bool(g.valid[0]), "diff": float(g.d[0])}


def run_one(args) -> tuple[pd.DataFrame, dict]:
    a, b, ko, kw = args
    kt, _ = load(a)
    _, pt = load(b)
    t, info = B.evaluate_game(a, ko, kt, pt, **kw)
    return t.assign(game_b=b), info


def boot_ci(per_game_pnl: pd.Series, per_game_n: pd.Series) -> tuple[float, float]:
    """Game-level bootstrap of mean net edge per trade = sum P&L / sum trades over resampled games."""
    rng = np.random.default_rng(SEED)
    p, n = per_game_pnl.to_numpy(float), per_game_n.to_numpy(float)
    if n.sum() < 2:
        return float("nan"), float("nan")
    idx = rng.integers(0, len(p), size=(N_BOOT, len(p)))
    m = p[idx].sum(axis=1) / np.maximum(n[idx].sum(axis=1), 1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def summarize(t: pd.DataFrame, n_games: int) -> pd.DataFrame:
    rows = []
    for (k, m, T), d in t.groupby(["k", "m", "T"]):
        f = d[d["filled"].astype(bool)]
        row = {"k": k, "m": m, "T": T, "games": n_games, "signals": len(d), "n_trades": len(f),
               "skip_no_entry_fill": int((d["skip"] == "no entry fill").sum()),
               "skip_no_exit_fill": int((d["skip"] == "no exit fill").sum()),
               "exit_converged": int((f["exit_reason"] == "converged").sum()),
               "exit_timeout": int((f["exit_reason"] == "timeout").sum()),
               "exit_window_end": int((f["exit_reason"] == "window end").sum())}
        for line in ("webull", "direct"):
            row[f"edge_{line}_cents"] = f[f"edge_{line}_cents"].mean() if len(f) else float("nan")
            pg = f.groupby("game_id")
            lo, hi = boot_ci(pg[f"edge_{line}_cents"].sum(), pg.size())
            row.update({f"edge_{line}_ci_lo": lo, f"edge_{line}_ci_hi": hi, f"pnl_{line}_total": f[f"pnl_{line}"].sum()})
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-variants-log", action="store_true",
                    help="reproduction of an already logged run: do not append duplicate variants.csv rows")
    a = ap.parse_args()
    g = games()
    use = g[g["covered"]].copy()
    if a.check:
        with Pool(2) as pool:
            c = pd.DataFrame(pool.map(check_one, list(zip(use["game_id"], use["espn_kickoff"]))))
        c.to_csv(OUT / "orientation_check.csv", index=False)
        v = c[c["valid"]]
        x = v["diff"].abs()
        ok = x.median() <= 0.03 and (x > 0.10).mean() < 0.02
        print(f"games {len(c)}, both valid at kickoff - 5 min {len(v)}; |K - PM| median {x.median():.4f}, "
              f"p95 {x.quantile(0.95):.4f}, > 0.10: {int((x > 0.10).sum())} ({100 * (x > 0.10).mean():.2f}%); "
              f"signed median {v['diff'].median():+.4f} -> {'PASS' if ok else 'FAIL'}")
        return
    jobs = [(r.game_id, r.game_id, r.espn_kickoff, {}) for r in use.itertuples()]
    pairs = B.placebo_pairs(use[["game_id", "espn_kickoff"]])
    ko = dict(zip(use["game_id"], use["espn_kickoff"]))
    pjobs = [(x, y, ko[x], {}) for x, y in pairs]
    with Pool(2) as pool:
        res = pool.map(run_one, jobs, chunksize=8)
        pres = pool.map(run_one, pjobs, chunksize=8)
    t = pd.concat([r[0] for r in res], ignore_index=True)
    pt = pd.concat([r[0] for r in pres], ignore_index=True)
    vs = pd.DataFrame([r[1] for r in res])
    t.to_parquet(OUT / "trades.parquet")
    pt.to_parquet(OUT / "placebo_trades.parquet")
    summ = summarize(t, len(use))
    psumm = summarize(pt, len(pairs))
    sel = B.select_setting(summ)
    x2 = pd.DataFrame()
    if sel is not None:
        k, m, T = sel
        jobs2 = [(r.game_id, r.game_id, r.espn_kickoff, {"settings": [sel], "half_spread": 2 * B.HALF_SPREAD,
                                                          "fee_mult": 2.0}) for r in use.itertuples()]
        with Pool(2) as pool:
            r2 = pool.map(run_one, jobs2, chunksize=8)
        t2 = pd.concat([r[0] for r in r2], ignore_index=True)
        t2.to_parquet(OUT / "trades_costs_x2.parquet")
        x2 = summarize(t2, len(use))
    summ.to_csv(OUT / "summary.csv", index=False)
    psumm.to_csv(OUT / "placebo_summary.csv", index=False)
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    var = []
    for label, s, n in (("real", summ, len(use)), ("placebo (unrelated game)", psumm, len(pairs))):
        for r in s.itertuples():
            var.append({"ts_utc": now, "git_sha": sha, "game_set": f"strategy_b training ({n} {'games' if label == 'real' else 'pairs'})",
                        "jump_cents": "", "window_s": r.m, "entry_gap": round(r.k * 100), "timeout_s": r.T,
                        "latency_s": B.LATENCY_S, "n_games": n, "n_trades": r.n_trades,
                        "edge_cents_mean": r.edge_webull_cents,
                        "notes": f"Strategy B v3+A1; {label}; k={r.k} m={r.m} T={r.T}; edge = net cents per contract "
                                 f"(Webull); direct {r.edge_direct_cents:.4f}; selected {sel}"})
    if not a.no_variants_log:
        pd.DataFrame(var).to_csv(VARIANTS, mode="a", header=False, index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(f"games {len(use)} (excluded {len(g) - len(use)}), placebo pairs {len(pairs)}, valid share median "
          f"{vs['valid_share'].median():.3f}; selected {sel}; variants rows {len(var)}")
    print(summ.round(4).to_string(index=False))
    print("placebo:")
    print(psumm.round(4).to_string(index=False))
    print("costs x2 (selected):")
    print(x2.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
