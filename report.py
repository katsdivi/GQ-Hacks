"""Latency curve (T11, first version): net edge per trade vs assumed reaction latency.

  python report.py --games sample
  python report.py --games sample --fake-lag 5
  python report.py --games g1,g2,g3 [--latencies 0,0.5,1] [--final-test]

For each game, each ordered venue pair (A leads, B trades), each fill bound and each latency,
it runs exactly the run.py pipeline (run.run_direction with that latency) and collects per-trade
net P&L in cents. Signals do not depend on latency (only backtest.simulate does), so the same
signals are reused at every latency; this is checked at run time.

Outputs:
  out/latency_curve_<set>_<UTC stamp>.csv (latest also copied to out/latency_curve.csv)  contract columns first (latency_s, n_trades, edge_cents_mean, edge_ci_low,
                         edge_ci_high, pnl_total), then direction, bound, n_games, ci_method.
                         One row per (direction, bound, latency).
  out/latency_curve_<set>_<UTC stamp>.png  one line per (direction, bound) with its CI band.

Confidence intervals: block bootstrap by game (resample whole games with replacement, 2000 draws,
seed 20261003, percentiles 2.5 and 97.5 of the pooled mean edge per trade). With one game a game
bootstrap is impossible, so trades are resampled instead and ci_method says so.

--fake-lag N builds the fake game in memory with make_sample.LAG_S = N (nothing is written under
data/), labelled sample_lagN; --games is ignored in that mode. It exists to show the curve when
the planted lag exceeds the detection delay (trailing 3 s median plus 1 s grid stamping use up a
2 s lag before any latency, see tests/test_leadlag.py).

Test set: games with kickoff on/after 2026-08-01 are refused unless --final-test (backtest.check_allowed),
checked before any tick file is read. Real game sets append one row per (direction, bound, latency)
to experiments/variants.csv; the fake game is never logged.

PROVISIONAL (pre-spec): all lead/lag, strategy and cost parameters are the run.py defaults.
Deterministic: no randomness except the seeded bootstrap; CSV values are rounded to 4 dp.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

import backtest
import costs
import leadlag
import make_sample
import run
import strategy

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
DEFAULT_LATENCIES = (0.0, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
N_BOOT = 2000
SEED = 20261003
CONTRACT = ["latency_s", "n_trades", "edge_cents_mean", "edge_ci_low", "edge_ci_high", "pnl_total"]
EXTRA = ["direction", "bound", "n_games", "ci_method"]
CI_GAME = "game bootstrap (2000 draws, seed 20261003, 2.5/97.5 pct)"
CI_TRADE = "trade bootstrap (single game; game-block bootstrap needs >= 2 games)"
CI_NONE = "none (no trades)"
VENUES = {"cme", "kalshi", "polymarket"}


def is_synthetic(game_id: str) -> bool:
    return game_id == "sample" or game_id.startswith("sample_lag")


def build_fake_game(lag_s: int, seed: int = 42) -> pd.DataFrame:
    """The fake game with a different planted lag, in memory only. LAG_S is always restored."""
    old = make_sample.LAG_S
    make_sample.LAG_S = int(lag_s)
    try:
        df, truth = make_sample.build(seed)
        if lag_s <= 5:   # validate's best-fit lag scan only covers 0..5 s
            make_sample.validate(df, truth)
    finally:
        make_sample.LAG_S = old
    return df


def load_games(game_ids: list[str], fake_lag: int | None = None, final_test: bool = False,
               game_row=run.game_row) -> dict[str, pd.DataFrame]:
    """game_id -> ticks sorted as run.py sorts them. Sealed games are refused before any file read."""
    if fake_lag is not None:
        row = game_row("sample")
        backtest.check_allowed("sample", row["kickoff_utc"], final_test)   # derived from the fake game
        ticks = build_fake_game(fake_lag)
        return {f"sample_lag{int(fake_lag)}": ticks.sort_values(["ts", "venue", "kind"], kind="stable")}
    if any(is_synthetic(g) for g in game_ids) and not all(is_synthetic(g) for g in game_ids):
        raise SystemExit("do not mix the fake game with real games (real sets are logged to variants.csv)")
    rows = {}
    for g in game_ids:
        row = game_row(g)
        if row is None:
            raise SystemExit(f"{g} not in data/games.csv")
        backtest.check_allowed(g, row["kickoff_utc"], final_test)
        rows[g] = row
    games = {}
    for g, row in rows.items():
        # Same as run.py: regenerates the fake game, or fetches a missing real game from the public
        # Kalshi and polymarket.com APIs (sealed games were already refused above).
        path = run.ensure_ticks(g, row)
        games[g] = pd.read_parquet(path).sort_values(["ts", "venue", "kind"], kind="stable")
    return games


def collect(games: dict[str, pd.DataFrame], latencies) -> dict:
    """{(direction, bound, latency): {game_id: per-trade net P&L in cents}} via run.run_direction."""
    p = {**leadlag.PROVISIONAL, **strategy.PROVISIONAL}
    cells: dict = {}
    d_cache = None
    for gid, ticks in games.items():
        venues = sorted(set(ticks["venue"]) & VENUES)
        if len(venues) != 2:
            raise SystemExit(f"{gid}: need exactly two venues, found {venues}")
        if "polymarket" in venues:
            d_cache = d_cache if d_cache is not None else run.load_d()
            d = d_cache
        else:
            d = {"D_p90_s": 0.0}
        for a, b in ((venues[0], venues[1]), (venues[1], venues[0])):
            sig0 = None
            for lat in latencies:
                r = run.run_direction(ticks, a, b, d, float(lat), p)
                if sig0 is None:
                    sig0 = r["signals"]
                else:   # signals must not depend on latency; fills alone move
                    pd.testing.assert_frame_equal(sig0, r["signals"])
                for bound, f in r["fills"].items():
                    t = f["trades"]
                    pnl = t["pnl_cents"].to_numpy(dtype="float64") if len(t) else np.array([], dtype="float64")
                    cells.setdefault((f"{a}->{b}", bound, float(lat)), {})[gid] = pnl
    return cells


def bootstrap_ci(per_game: dict[str, np.ndarray]) -> tuple[float, float, str]:
    """Percentile CI of the pooled mean edge per trade. Fresh seeded RNG per cell."""
    arrs = [per_game[g] for g in sorted(per_game)]
    pooled = np.concatenate(arrs) if arrs else np.array([])
    if pooled.size == 0:
        return float("nan"), float("nan"), CI_NONE
    rng = np.random.default_rng(SEED)
    if len(arrs) >= 2:
        sums = np.array([a.sum() for a in arrs])
        cnts = np.array([a.size for a in arrs], dtype="float64")
        idx = rng.integers(0, len(arrs), size=(N_BOOT, len(arrs)))
        n = cnts[idx].sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            means = np.where(n > 0, sums[idx].sum(axis=1) / n, np.nan)
        method = CI_GAME
    else:
        idx = rng.integers(0, pooled.size, size=(N_BOOT, pooled.size))
        means = pooled[idx].mean(axis=1)
        method = CI_TRADE
    lo, hi = np.nanpercentile(means, [2.5, 97.5])
    return float(lo), float(hi), method


def curve(games: dict[str, pd.DataFrame], latencies=DEFAULT_LATENCIES) -> pd.DataFrame:
    rows = []
    for (direction, bound, lat), per_game in sorted(collect(games, latencies).items()):
        pooled = np.concatenate([per_game[g] for g in sorted(per_game)])
        lo, hi, method = bootstrap_ci(per_game)
        rows.append({"latency_s": lat, "n_trades": int(pooled.size),
                     "edge_cents_mean": float(pooled.mean()) if pooled.size else float("nan"),
                     "edge_ci_low": lo, "edge_ci_high": hi, "pnl_total": float(pooled.sum()),
                     "direction": direction, "bound": bound, "n_games": len(per_game), "ci_method": method})
    df = pd.DataFrame(rows, columns=CONTRACT + EXTRA)
    for c in ("edge_cents_mean", "edge_ci_low", "edge_ci_high", "pnl_total"):
        df[c] = df[c].round(4)
    return df.sort_values(["direction", "bound", "latency_s"], kind="stable").reset_index(drop=True)


def chart(df: pd.DataFrame, game_set: str, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]   # fixed order
    fig, ax = plt.subplots(figsize=(10, 5.5))
    ax.axhline(0, color="#888888", lw=1)
    for i, ((direction, bound), g) in enumerate(df.groupby(["direction", "bound"], sort=True)):
        g = g.dropna(subset=["edge_cents_mean"])
        if g.empty:
            continue
        c = palette[i % len(palette)]
        ax.fill_between(g["latency_s"], g["edge_ci_low"], g["edge_ci_high"], color=c, alpha=0.15, lw=0)
        ax.plot(g["latency_s"], g["edge_cents_mean"], color=c, lw=2, marker="o", ms=5,
                label=f"{direction}, {bound} (n games {int(g['n_games'].iloc[0])})")
    ax.set_xlabel(f"assumed reaction latency (s); {run.LATENCY_NOTE}")
    ax.set_ylabel("net edge per trade (cents)")
    ax.set_title(f"Latency curve, games: {game_set}\n{costs.FEE_LABEL}; PROVISIONAL (pre-spec)", fontsize=10)
    ax.grid(True, color="#e5e5e5", lw=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="best", fontsize=8, frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def print_table(df: pd.DataFrame) -> None:
    def f(x, fmt):
        return format("n/a", ">" + fmt.lstrip("+").split(".")[0]) if pd.isna(x) else format(x, fmt)
    print(f"{'direction':16s} {'bound':26s} {'lat_s':>5s} {'n':>4s} {'edge_c':>8s} {'ci_low':>8s} "
          f"{'ci_high':>8s} {'pnl_c':>9s}")
    for r in df.itertuples():
        print(f"{r.direction:16s} {r.bound:26s} {r.latency_s:5g} {r.n_trades:4d} {f(r.edge_cents_mean, '+8.2f')} "
              f"{f(r.edge_ci_low, '+8.2f')} {f(r.edge_ci_high, '+8.2f')} {f(r.pnl_total, '+9.1f')}")
    for m in sorted(df["ci_method"].unique()):
        print(f"ci_method: {m}")


def liquidity_kalshi(meta_csv: Path = Path("data/raw/kalshi_market_meta.csv"),
                     games_csv: Path = Path("data/raw/kalshi_only_games.csv")) -> pd.DataFrame:
    """Liquidity section, Kalshi, training markets only: lifetime traded volume per market (contracts), median
    and IQR, by league and overall. Open interest is NOT reported: Kalshi's metadata shows it after settlement
    (0 on every training market), so it says nothing about pre-game depth."""
    m = pd.read_csv(meta_csv)
    g = pd.read_csv(games_csv)[["game_id", "league", "kickoff_utc_espn"]]
    assert (pd.to_datetime(g["kickoff_utc_espn"], utc=True) < pd.Timestamp("2026-08-01", tz="UTC")).all(), "training markets only"
    m = m.merge(g, on="game_id", how="inner")
    m["volume"] = pd.to_numeric(m["volume_fp"], errors="coerce")
    rows = []
    for lg, d in [("all", m)] + list(m.groupby("league")):
        v = d["volume"].dropna()
        rows.append({"venue": "kalshi", "league": lg, "n_markets": len(v), "volume_median": v.median(),
                     "volume_q25": v.quantile(0.25), "volume_q75": v.quantile(0.75)})
    return pd.DataFrame(rows)


def log_variants(df: pd.DataFrame, game_ids: list[str]) -> int:
    """Rule 3: one variants.csv row per (direction, bound, latency), same columns as run.py."""
    p = {**leadlag.PROVISIONAL, **strategy.PROVISIONAL}
    now = pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
    sha = run.git_sha()
    rows = [{"ts_utc": now, "git_sha": sha, "game_set": ",".join(game_ids), "jump_cents": p["jump_cents"],
             "window_s": p["window_s"], "entry_gap": p["entry_gap_cents"], "timeout_s": p["timeout_s"],
             "latency_s": r.latency_s, "n_games": r.n_games, "n_trades": r.n_trades,
             "edge_cents_mean": r.edge_cents_mean if r.n_trades else "",
             "notes": f"report.py latency curve; {r.direction.replace('->', ' leads ')}; {r.bound}; "
                      f"price=trailing {run.PRICE_WINDOW_S:g}s median; latency {run.LATENCY_NOTE}; "
                      f"CI {r.ci_method}; PROVISIONAL; PLACEHOLDER FEE"}
            for r in df.itertuples()]
    pd.DataFrame(rows).to_csv(run.VARIANTS, mode="a", header=False, index=False)
    return len(rows)


def main(argv: list[str] | None = None, out_dir: Path = OUT, stamp: str | None = None) -> pd.DataFrame:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", default="sample", help="comma list of game_ids from data/games.csv")
    ap.add_argument("--latencies", default=",".join(f"{x:g}" for x in DEFAULT_LATENCIES),
                    help=f"comma list of reaction delays in seconds ({run.LATENCY_NOTE})")
    ap.add_argument("--fake-lag", type=int, default=None,
                    help="build the fake game in memory with this planted lag (s); ignores --games")
    ap.add_argument("--final-test", action="store_true")
    a = ap.parse_args(argv)

    ids = [g.strip() for g in a.games.split(",") if g.strip()]
    lats = sorted({float(x) for x in a.latencies.split(",") if x.strip()})
    games = load_games(ids, a.fake_lag, a.final_test)
    game_set = ",".join(games)
    print(f"latency curve: games {game_set}; latencies {', '.join(f'{x:g}' for x in lats)} s ({run.LATENCY_NOTE})")
    print(f"params PROVISIONAL (pre-spec), as run.py; costs: {costs.FEE_LABEL}")

    df = curve(games, lats)
    out_dir.mkdir(parents=True, exist_ok=True)
    # One file pair per run, never overwritten: latency_curve_<game_or_set>_<UTC timestamp>.
    label = game_set if len(game_set) <= 60 else f"{len(games)}games"
    label = "".join(ch if ch.isalnum() or ch in "-_" else "+" for ch in label)
    stamp = stamp or pd.Timestamp.now(tz="UTC").strftime("%Y%m%dT%H%M%SZ")
    stem = f"latency_curve_{label}_{stamp}"
    df.to_csv(out_dir / f"{stem}.csv", index=False)
    chart(df, game_set, out_dir / f"{stem}.png")
    # CLAUDE.md contract path (what Olmer reads): a copy of the latest run.
    df.to_csv(out_dir / "latency_curve.csv", index=False)
    print()
    print_table(df)
    shown = out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir
    print(f"\nsaved {shown / (stem + '.csv')}, {shown / (stem + '.png')} (latest also copied to {shown / 'latency_curve.csv'})")
    if not any(is_synthetic(g) for g in games):
        print(f"appended {log_variants(df, list(games))} rows to experiments/variants.csv")
    return df


if __name__ == "__main__":
    main()
