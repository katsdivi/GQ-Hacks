"""Made It: one command per game. Lead/lag both directions, paper strategy both directions, net P&L.

  python run.py --game sample
  python run.py --game nfl_20251116_was_mia [--latency 1.0] [--final-test]

If data/ticks/<game>.parquet is missing, it is fetched from the public Kalshi and polymarket.com
APIs using the game's row in data/games.csv (no keys, no vendor data in git). The fake game is
regenerated with make_sample.py.

For each ordered venue pair (A leads, B follows) it prints the lead/lag summary, round trips on
B and net P&L after costs; saves out/leadlag/<game>.parquet, out/signals/<game>.parquet and
out/<game>_run.png; and for real games appends one row per (direction, bound) to
experiments/variants.csv.

Clock (HYPOTHESIS_v2.md Amendment 1): decisions, gap checks and lead/lag use raw timestamps,
never shifted. When polymarket.com is the traded venue, two fills are reported:
  lower bound: entry fills on quotes shifted EARLIER by D p90, exit fills unshifted (both worse for us)
  upper bound: no shift
Kalshi-traded directions are unshifted (one row).

Latency: 0 s = decision within 1 s of the move (grid stamping: label g is decided at g + 1 s).
The trailing 3 s median price adds its own detection delay on top (about 1 s for a clean step).
Deterministic: no randomness, inputs sorted by (ts, venue, kind) with a stable sort.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
LATENCY_NOTE = "0 s = decision within 1 s of the move"
PRICE_WINDOW_S = 3.0   # PROVISIONAL: trailing median window for the price series


def load_d() -> dict:
    d = json.loads(D_FILE.read_text()) if D_FILE.exists() else {}
    if not d:
        print("D estimate: MISSING (experiments/d_estimate.json); lower bound = upper bound, results inconclusive")
        return {"D_median_s": 0.0, "D_p90_s": 0.0, "n_trades": 0, "meets_v2_minimum": False}
    flag = "" if d.get("meets_v2_minimum") else f"  FLAG: only {d['n_trades']} trades, v2 needs >= 200"
    print(f"D estimate: median {d['D_median_s']:+.3f} s, p90 {d['D_p90_s']:+.3f} s from {d['n_trades']} "
          f"calibration trades, measured {d['measured_at_utc'][:19]}Z{flag}")
    return d


def game_row(game_id: str) -> dict | None:
    g = pd.read_csv(ROOT / "data" / "games.csv", dtype=str)
    r = g[g["game_id"] == game_id]
    return r.iloc[0].to_dict() if len(r) else None


def ensure_ticks(game_id: str, row: dict) -> Path:
    path = TICKS / f"{game_id}.parquet"
    if path.exists():
        return path
    if game_id == "sample":
        subprocess.run([sys.executable, "make_sample.py"], cwd=ROOT, check=True)
        return path
    from ingest.download_all import fetch_game
    fetch_game(game_id, row["league"], row["home"], row["away"], row["kickoff_utc"], row["kalshi_ticker"],
               row["polymarket_token"])
    return path


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
    # Decisions, gaps and lead/lag: raw timestamps for both venues (Amendment 1).
    pa = align.to_grid(align.trade_median_events(ticks, a, PRICE_WINDOW_S))
    pb = align.to_grid(align.trade_median_events(ticks, b, PRICE_WINDOW_S))
    pa, pb = align.common_grid(pa, pb)
    resp, summ = leadlag.leadlag(pa, pb, p["jump_cents"], p["window_s"], p["cover"], p["max_wait_s"], p["max_lag_s"])
    sig = strategy.signals(pa, pb, resp, p["entry_gap_cents"], p["exit_gap_cents"], p["timeout_s"], p["qty"])
    raw_q, fill_model = backtest.follower_quotes(ticks, b, 0.0)
    if b == "polymarket":
        shifted_q, _ = backtest.follower_quotes(ticks, b, d["D_p90_s"])
        bounds = {"lower bound": (shifted_q, raw_q), "upper bound": (raw_q, raw_q)}
    else:
        bounds = {f"{b} traded (unshifted)": (raw_q, raw_q)}
    fills = {}
    for name, (qe, qx) in bounds.items():
        t = backtest.simulate(sig, qe, qx, b, latency_s)
        fills[name] = {"trades": t, "net_cents": float(t["pnl_cents"].sum()) if len(t) else 0.0,
                       "edge_mean": float(t["pnl_cents"].mean()) if len(t) else float("nan")}
    return {"leader": a, "follower": b, "summary": summ, "jumps": resp, "signals": sig, "fills": fills,
            "fill_model": fill_model, "pa": pa, "pb": pb}


def chart(game_id: str, res: list[dict], latency_s: float, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(13, 7), sharex=True)
    r0 = res[0]
    t = pd.to_datetime(r0["pa"].index * 1_000_000_000, utc=True)
    ax[0].step(t, r0["pa"].to_numpy(), where="post", lw=0.8, label=r0["leader"])
    ax[0].step(t, r0["pb"].to_numpy(), where="post", lw=0.8, label=r0["follower"])
    for r in res:
        for name, f in r["fills"].items():
            tr = f["trades"]
            if len(tr):
                ax[1].step(pd.to_datetime(tr["exit_fill_ns"], utc=True), tr["pnl_cents"].cumsum(), where="post",
                           label=f"{r['leader']} leads, trade {r['follower']}: {name}")
    ax[0].set_ylabel(f"P(home wins), trailing {PRICE_WINDOW_S:g} s median")
    ax[0].set_title(f"{game_id}: 1 s grid, raw timestamps")
    ax[0].legend(loc="best", fontsize=8)
    ax[1].axhline(0, color="grey", lw=0.6)
    ax[1].set_ylabel("cumulative net P&L (cents)")
    ax[1].set_title(f"Net of costs, {costs.FEE_LABEL}; latency {latency_s:g} s ({LATENCY_NOTE})")
    ax[1].legend(loc="best", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--game", required=True)
    ap.add_argument("--latency", type=float, default=1.0,
                    help=f"reaction delay in seconds, PROVISIONAL 1.0 ({LATENCY_NOTE})")
    ap.add_argument("--final-test", action="store_true")
    a = ap.parse_args()

    row = game_row(a.game)
    if row is None:
        raise SystemExit(f"{a.game} not in data/games.csv")
    backtest.check_allowed(a.game, row["kickoff_utc"], a.final_test)
    ticks = pd.read_parquet(ensure_ticks(a.game, row)).sort_values(["ts", "venue", "kind"], kind="stable")
    venues = sorted(set(ticks["venue"]) & {"cme", "kalshi", "polymarket"})
    if len(venues) != 2:
        raise SystemExit(f"need exactly two venues, found {venues}")

    p = {**leadlag.PROVISIONAL, **strategy.PROVISIONAL}
    print(f"game {a.game}, kickoff {row['kickoff_utc']}, venues {venues[0]} vs {venues[1]}, "
          f"latency {a.latency:g} s ({LATENCY_NOTE})")
    print(f"params PROVISIONAL (pre-spec): price = trailing {PRICE_WINDOW_S:g} s median of trades, "
          + ", ".join(f"{kk}={v}" for kk, v in p.items()))
    print(f"costs: {costs.FEE_LABEL}; half-spread {costs.HALF_SPREAD * 100:.1f}c when no book (PROVISIONAL)")
    d = load_d() if "polymarket" in venues else {"D_p90_s": 0.0}

    res = [run_direction(ticks, x, y, d, a.latency, p) for x, y in ((venues[0], venues[1]), (venues[1], venues[0]))]
    for r in res:
        s = r["summary"]
        print(f"\n{r['leader']} leads -> {r['follower']} follows")
        print(f"  jumps on {r['leader']}: {s['n_jumps']}, covered by {r['follower']}: {s['n_covered']}, "
              f"median response {s['median_response_s']:+.1f} s, xcorr lag {s['xcorr_lag_s']:+d} s")
        print(f"  signals: {len(r['signals'])}; fill model {r['fill_model']}")
        for name, f in r["fills"].items():
            mean = f"{f['edge_mean']:+.2f}c per trade" if len(f["trades"]) else "n/a (no trades)"
            print(f"  {name:26s} trades on {r['follower']}: {len(f['trades'])}, net P&L {f['net_cents']:+.1f}c, mean {mean}")

    OUT.joinpath("leadlag").mkdir(parents=True, exist_ok=True)
    OUT.joinpath("signals").mkdir(parents=True, exist_ok=True)
    pd.concat([leadlag.to_contract(r["jumps"], r["leader"], r["follower"]) for r in res], ignore_index=True) \
        .to_parquet(OUT / "leadlag" / f"{a.game}.parquet", index=False)
    pd.concat([backtest.to_contract(f["trades"], r["follower"]).assign(leader=r["leader"], bound=name)
               for r in res for name, f in r["fills"].items()], ignore_index=True) \
        .to_parquet(OUT / "signals" / f"{a.game}.parquet", index=False)
    chart(a.game, res, a.latency, OUT / f"{a.game}_run.png")
    print(f"\nsaved out/{a.game}_run.png, out/leadlag/{a.game}.parquet, out/signals/{a.game}.parquet")

    if a.game != "sample":   # rule 3: every variant run on training data is logged
        now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        rows = [{"ts_utc": now, "git_sha": git_sha(), "game_set": a.game, "jump_cents": p["jump_cents"],
                 "window_s": p["window_s"], "entry_gap": p["entry_gap_cents"], "timeout_s": p["timeout_s"],
                 "latency_s": a.latency, "n_games": 1, "n_trades": len(f["trades"]),
                 "edge_cents_mean": round(f["edge_mean"], 4) if len(f["trades"]) else "",
                 "notes": f"{r['leader']} leads {r['follower']}; {name}; price=trailing {PRICE_WINDOW_S:g}s median; "
                          f"latency {LATENCY_NOTE}; PROVISIONAL; fees as if traded today (Webull route)"}
                for r in res for name, f in r["fills"].items()]
        pd.DataFrame(rows).to_csv(VARIANTS, mode="a", header=False, index=False)
        print(f"appended {len(rows)} rows to experiments/variants.csv")


if __name__ == "__main__":
    main()
