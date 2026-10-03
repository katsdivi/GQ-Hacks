"""Made It: one command per game. Lead/lag both directions, paper strategy both directions, net P&L.

  python run.py --game sample
  python run.py --game nfl_20251116_was_mia [--latency 1.0] [--final-test]

For each ordered venue pair (A leads, B follows) it prints the lead/lag summary, the number of
round trips on B and net P&L after costs, saves out/leadlag/<game>.parquet,
out/signals/<game>.parquet and out/<game>_run.png, and (real games only) appends one row per
direction to experiments/variants.csv.

polymarket.com block-time correction (HYPOTHESIS_v2.md): when B = polymarket (trading on it),
every polymarket.com timestamp is shifted EARLIER by D p90 from experiments/d_estimate.json.
When polymarket.com is only the signal (A), its timestamps are left as block times.
Deterministic: no randomness, inputs sorted by (ts, kind) with a stable sort.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pandas as pd

import align
import backtest
import costs
import leadlag
import strategy

ROOT = Path(__file__).resolve().parent
TICKS = ROOT / "data" / "ticks"
OUT = ROOT / "out"
VARIANTS = ROOT / "experiments" / "variants.csv"
D_FILE = ROOT / "experiments" / "d_estimate.json"


def load_d() -> dict:
    d = json.loads(D_FILE.read_text()) if D_FILE.exists() else {}
    if not d:
        print("D estimate: MISSING (experiments/d_estimate.json); polymarket.com shift = 0, results inconclusive")
        return {"D_median_s": 0.0, "D_p90_s": 0.0, "n_trades": 0, "meets_v2_minimum": False}
    flag = "" if d.get("meets_v2_minimum") else f"  FLAG: only {d['n_trades']} trades, v2 needs >= 200"
    print(f"D estimate: median {d['D_median_s']:+.3f} s, p90 {d['D_p90_s']:+.3f} s from {d['n_trades']} "
          f"calibration trades, measured {d['measured_at_utc'][:19]}Z{flag}")
    return d


def kickoff(game_id: str) -> str | None:
    g = pd.read_csv(ROOT / "data" / "games.csv", dtype=str)
    r = g[g["game_id"] == game_id]
    return r["kickoff_utc"].iloc[0] if len(r) else None


def git_sha() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "*.py"], cwd=ROOT, capture_output=True,
                               text=True, check=True).stdout.strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def run_direction(ticks: pd.DataFrame, a: str, b: str, d: dict, latency_s: float, p: dict) -> dict:
    shift_b = d["D_p90_s"] if b == "polymarket" else 0.0   # v2 rule 2: trading on polymarket.com
    shift_a = 0.0                                          # signal venue: unshifted (conservative)
    pa = align.to_grid(align.venue_events(ticks, a, shift_a))
    pb = align.to_grid(align.venue_events(ticks, b, shift_b))
    pa, pb = align.common_grid(pa, pb)
    resp, summ = leadlag.leadlag(pa, pb, p["jump_cents"], p["window_s"], p["cover"], p["max_wait_s"], p["max_lag_s"])
    sig = strategy.signals(pa, pb, resp, p["entry_gap_cents"], p["exit_gap_cents"], p["timeout_s"], p["qty"])
    quotes, fill_model = backtest.follower_quotes(ticks, b, shift_b)
    trades = backtest.simulate(sig, quotes, b, latency_s)
    net = float(trades["pnl_cents"].sum()) if len(trades) else 0.0
    return {"leader": a, "follower": b, "shift_b_s": shift_b, "summary": summ, "jumps": resp, "trades": trades,
            "fill_model": fill_model, "net_cents": net, "pa": pa, "pb": pb,
            "edge_mean": float(trades["pnl_cents"].mean()) if len(trades) else float("nan")}


def chart(game_id: str, res: list[dict], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    r0 = res[0]
    t = pd.to_datetime(r0["pa"].index * 1_000_000_000, utc=True)
    ax[0].step(t, r0["pa"].to_numpy(), where="post", lw=0.8, label=r0["leader"])
    ax[0].step(t, r0["pb"].to_numpy(), where="post", lw=0.8, label=r0["follower"])
    for r, m in zip(res, ("^", "v")):
        if len(r["trades"]):
            te = pd.to_datetime(r["trades"]["entry_fill_ns"], utc=True)
            ax[0].scatter(te, r["trades"]["entry_px"], marker=m, s=18, zorder=3,
                          label=f"entries on {r['follower']} ({r['leader']} leads)")
            ax[1].step(pd.to_datetime(r["trades"]["exit_fill_ns"], utc=True), r["trades"]["pnl_cents"].cumsum(),
                       where="post", label=f"{r['leader']} leads, trade {r['follower']}")
    ax[0].set_ylabel("P(home wins)")
    ax[0].set_title(f"{game_id}: 1 s grid (polymarket.com shifted only when traded)")
    ax[0].legend(loc="best", fontsize=8)
    ax[1].axhline(0, color="grey", lw=0.6)
    ax[1].set_ylabel("cumulative net P&L (cents)")
    ax[1].set_title(f"Net of costs, {costs.FEE_LABEL}")
    ax[1].legend(loc="best", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--latency", type=float, default=1.0, help="reaction delay in seconds (PROVISIONAL 1.0)")
    ap.add_argument("--final-test", action="store_true")
    a = ap.parse_args()

    k = kickoff(a.game)
    if k is None:
        raise SystemExit(f"{a.game} not in data/games.csv")
    backtest.check_allowed(a.game, k, a.final_test)
    ticks = pd.read_parquet(TICKS / f"{a.game}.parquet").sort_values(["ts", "venue", "kind"], kind="stable")
    venues = sorted(set(ticks["venue"]) & {"cme", "kalshi", "polymarket"})
    if len(venues) != 2:
        raise SystemExit(f"need exactly two venues, found {venues}")

    p = {**leadlag.PROVISIONAL, **strategy.PROVISIONAL}
    print(f"game {a.game}, kickoff {k}, venues {venues[0]} vs {venues[1]}, latency {a.latency:.2f} s")
    print("params PROVISIONAL (pre-spec): " + ", ".join(f"{kk}={v}" for kk, v in p.items()))
    print(f"costs: {costs.FEE_LABEL}; half-spread {costs.HALF_SPREAD * 100:.1f}c when no book (PROVISIONAL)")
    d = load_d() if "polymarket" in venues else {"D_p90_s": 0.0}

    res = [run_direction(ticks, x, y, d, a.latency, p) for x, y in ((venues[0], venues[1]), (venues[1], venues[0]))]
    for r in res:
        s = r["summary"]
        print(f"\n{r['leader']} leads -> {r['follower']} follows"
              + (f"   [{r['follower']} timestamps shifted {r['shift_b_s']:.3f} s earlier]" if r["shift_b_s"] else ""))
        print(f"  jumps on {r['leader']}: {s['n_jumps']}, covered by {r['follower']}: {s['n_covered']}, "
              f"median response {s['median_response_s']:+.1f} s, xcorr lag {s['xcorr_lag_s']:+d} s")
        print(f"  trades on {r['follower']}: {len(r['trades'])} (fill model {r['fill_model']}), "
              f"net P&L {r['net_cents']:+.1f}c, mean " + (f"{r['edge_mean']:+.2f}c per trade" if len(r["trades"]) else "n/a (no trades)"))

    OUT.joinpath("leadlag").mkdir(parents=True, exist_ok=True)
    OUT.joinpath("signals").mkdir(parents=True, exist_ok=True)
    pd.concat([leadlag.to_contract(r["jumps"], r["leader"], r["follower"]) for r in res], ignore_index=True) \
        .to_parquet(OUT / "leadlag" / f"{a.game}.parquet", index=False)
    pd.concat([backtest.to_contract(r["trades"], r["follower"]).assign(leader=r["leader"]) for r in res],
              ignore_index=True).to_parquet(OUT / "signals" / f"{a.game}.parquet", index=False)
    chart(a.game, res, OUT / f"{a.game}_run.png")
    print(f"\nsaved out/{a.game}_run.png, out/leadlag/{a.game}.parquet, out/signals/{a.game}.parquet")

    if a.game != "sample":   # rule 3: every variant run on training data is logged
        rows = [{"ts_utc": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"), "git_sha": git_sha(),
                 "game_set": a.game, "jump_cents": p["jump_cents"], "window_s": p["window_s"],
                 "entry_gap": p["entry_gap_cents"], "timeout_s": p["timeout_s"], "latency_s": a.latency,
                 "n_games": 1, "n_trades": len(r["trades"]),
                 "edge_cents_mean": round(r["edge_mean"], 4) if r["edge_mean"] == r["edge_mean"] else "",
                 "notes": f"{r['leader']} leads {r['follower']}; PROVISIONAL; PLACEHOLDER FEE; "
                          f"pm_shift={r['shift_b_s']}"} for r in res]
        pd.DataFrame(rows).to_csv(VARIANTS, mode="a", header=False, index=False)
        print(f"appended {len(rows)} rows to experiments/variants.csv")


if __name__ == "__main__":
    main()
