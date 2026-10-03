"""Fake game generator for StaleLine.

Writes data/ticks/sample.parquet in the shared format, plus the planted
answer key at data/ticks/sample_truth.csv so leadlag.py can be checked.

The fake game:
  * 3.5 hours at one tick per second.
  * CME price takes small random steps plus 15 sudden jumps of 3 to 10 cents.
  * Kalshi copies CME's price from LAG_S seconds earlier, plus a little noise,
    rounded to whole cents.
  * Bid and ask rows 1 cent either side of each venue's price.
  * Every price stays in [0.01, 0.99] and means P(home team wins).

Usage:
  python make_sample.py            # write sample.parquet + truth
  python make_sample.py --plot     # also save out/sample.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
TICKS_DIR = ROOT / "data" / "ticks"
OUT_DIR = ROOT / "out"

GAME_ID = "sample"
KICKOFF_UTC = pd.Timestamp("2026-09-27 17:00:00", tz="UTC")
DURATION_S = int(3.5 * 3600)        # 12,600 one-second ticks
LAG_S = 2                           # the planted answer
N_JUMPS = 15
JUMP_MIN, JUMP_MAX = 0.03, 0.10     # dollars
STEP_SD = 0.0015                    # small random step per second
KALSHI_NOISE_SD = 0.002
MIN_JUMP_GAP_S = 300                # jumps at least 5 min apart
P_LO, P_HI = 0.01, 0.99

CME_MARKET = "FG-SAMPLE"
KALSHI_MARKET = "KXNFLGAME-SAMPLE-HOME"


def pick_jump_times(rng: np.random.Generator) -> np.ndarray:
    """N_JUMPS distinct seconds, spaced >= MIN_JUMP_GAP_S, away from the edges."""
    while True:
        t = np.sort(rng.integers(600, DURATION_S - 600, size=N_JUMPS))
        if np.all(np.diff(t) >= MIN_JUMP_GAP_S):
            return t


def simulate_cme(rng: np.random.Generator, jump_times: np.ndarray) -> tuple[np.ndarray, pd.DataFrame]:
    p = np.empty(DURATION_S)
    p[0] = 0.55
    jump_set = {int(t): i for i, t in enumerate(jump_times)}
    truth = []
    for t in range(1, DURATION_S):
        step = rng.normal(0.0, STEP_SD)
        if t in jump_set:
            size = rng.uniform(JUMP_MIN, JUMP_MAX)
            # Jump toward whichever side has room, random otherwise.
            room_up, room_dn = P_HI - p[t - 1], p[t - 1] - P_LO
            if room_up < size + 0.02:
                sign = -1
            elif room_dn < size + 0.02:
                sign = 1
            else:
                sign = rng.choice([-1, 1])
            step = sign * size
            truth.append({"jump_idx": jump_set[t], "t_s": t, "jump_cents": round(size * 100, 2),
                          "direction": int(sign)})
        p[t] = np.clip(p[t - 1] + step, P_LO, P_HI)
    return p, pd.DataFrame(truth)


def simulate_kalshi(rng: np.random.Generator, cme: np.ndarray) -> np.ndarray:
    lagged = np.concatenate([np.full(LAG_S, cme[0]), cme[:-LAG_S]])
    k = lagged + rng.normal(0.0, KALSHI_NOISE_SD, size=len(cme))
    return np.clip(np.round(k, 2), P_LO, P_HI)


def to_rows(ts_ns: np.ndarray, price: np.ndarray, venue: str, market_id: str,
            rng: np.random.Generator, size_hi: int, round_cents: bool) -> pd.DataFrame:
    n = len(price)
    prev = np.concatenate([[price[0]], price[:-1]])
    side = np.where(price > prev, "buy", np.where(price < prev, "sell", "unknown"))
    trade = pd.DataFrame({"ts": ts_ns, "venue": venue, "market_id": market_id, "kind": "trade",
                          "price": np.round(price, 4), "size": rng.integers(1, size_hi + 1, n),
                          "side": side})
    base = np.round(price, 2) if round_cents else price
    bid = trade.assign(kind="bid", price=np.round(np.clip(base - 0.01, P_LO, P_HI), 4),
                       size=rng.integers(1, size_hi * 4 + 1, n), side="buy")
    ask = trade.assign(kind="ask", price=np.round(np.clip(base + 0.01, P_LO, P_HI), 4),
                       size=rng.integers(1, size_hi * 4 + 1, n), side="sell")
    return pd.concat([trade, bid, ask], ignore_index=True)


def build(seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    jump_times = pick_jump_times(rng)
    cme, truth = simulate_cme(rng, jump_times)
    kalshi = simulate_kalshi(rng, cme)

    t0 = KICKOFF_UTC.value  # ns
    ts_ns = t0 + np.arange(DURATION_S, dtype=np.int64) * 1_000_000_000

    df = pd.concat([
        to_rows(ts_ns, cme, "cme", CME_MARKET, rng, size_hi=50, round_cents=False),
        to_rows(ts_ns, kalshi, "kalshi", KALSHI_MARKET, rng, size_hi=500, round_cents=True),
    ], ignore_index=True)
    df = df.sort_values(["ts", "venue", "kind"], kind="stable").reset_index(drop=True)
    df = df.astype({"ts": "int64", "venue": "string", "market_id": "string", "kind": "string",
                    "price": "float64", "size": "int64", "side": "string"})

    truth["jump_ts"] = t0 + truth["t_s"].astype("int64") * 1_000_000_000
    truth["planted_lag_s"] = LAG_S
    truth = truth[["jump_idx", "jump_ts", "t_s", "jump_cents", "direction", "planted_lag_s"]]
    return df, truth


def validate(df: pd.DataFrame, truth: pd.DataFrame) -> None:
    assert list(df.columns) == ["ts", "venue", "market_id", "kind", "price", "size", "side"]
    assert df["price"].between(P_LO, P_HI).all(), "price out of [0.01, 0.99]"
    assert set(df["venue"].unique()) == {"cme", "kalshi"}
    assert set(df["kind"].unique()) == {"trade", "bid", "ask"}
    assert len(truth) == N_JUMPS
    # Lag sanity: Kalshi trade price best matches CME shifted by LAG_S.
    tr = df[df["kind"] == "trade"].pivot(index="ts", columns="venue", values="price")
    errs = {k: float((tr["kalshi"] - tr["cme"].shift(k)).abs().mean()) for k in range(0, 6)}
    best = min(errs, key=errs.get)
    assert best == LAG_S, f"best-fit lag {best}s, expected {LAG_S}s: {errs}"


def plot(df: pd.DataFrame, truth: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tr = df[df["kind"] == "trade"].copy()
    tr["t"] = pd.to_datetime(tr["ts"], utc=True)
    fig, axes = plt.subplots(2, 1, figsize=(12, 7))
    for venue, color in [("cme", "tab:blue"), ("kalshi", "tab:orange")]:
        s = tr[tr["venue"] == venue]
        axes[0].plot(s["t"], s["price"], lw=0.8, color=color, label=venue)
    axes[0].set_title("Fake game: P(home wins) by venue")
    axes[0].legend()
    # Zoom on the first planted jump.
    j = pd.to_datetime(truth["jump_ts"].iloc[0], utc=True)
    win = tr[(tr["t"] >= j - pd.Timedelta(seconds=10)) & (tr["t"] <= j + pd.Timedelta(seconds=10))]
    for venue, color in [("cme", "tab:blue"), ("kalshi", "tab:orange")]:
        s = win[win["venue"] == venue]
        axes[1].step(s["t"], s["price"], where="post", color=color, label=venue)
    axes[1].axvline(j, color="grey", ls="--", lw=0.8)
    axes[1].set_title(f"Zoom on jump 0 ({truth['jump_cents'].iloc[0]:.1f}c): Kalshi trails by {LAG_S}s")
    axes[1].legend()
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--plot", action="store_true")
    args = ap.parse_args()

    df, truth = build(args.seed)
    validate(df, truth)

    TICKS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(TICKS_DIR / f"{GAME_ID}.parquet", index=False)
    truth.to_csv(TICKS_DIR / f"{GAME_ID}_truth.csv", index=False)
    print(f"wrote {len(df):,} rows to data/ticks/{GAME_ID}.parquet "
          f"({N_JUMPS} planted jumps, Kalshi lag {LAG_S}s, seed {args.seed})")
    if args.plot:
        plot(df, truth, OUT_DIR / "sample.png")
        print("saved out/sample.png")


if __name__ == "__main__":
    main()
