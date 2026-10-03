"""Synthetic activity-bias test for the xcorr lead statistic (Amendment 2 draft, item 4).

Does a busy venue look like it leads a thin venue just because it trades more often? Each simulated
game has a hidden P(home) path (1 s steps plus 15 jumps of 3 to 10 cents, 7 h). Each venue trades as
a Poisson process at its own rate; a trade's price is the hidden path at (trade time - venue lag)
plus 0.5 cent bid/ask bounce, rounded to the cent. The full pipeline (trailing 3 s median, 1 s grid,
xcorr max lag 15 s) gives one lag per game; positive = Kalshi first.

Rate pairs (trades per minute): Kalshi-like 390 vs polymarket.com-like 5, and vs Polymarket-US-like 1.
Cases:
  no_link   independent paths (what the unrelated-games placebo measures)
  zero_lag  the same path, both venues on time (a real link with no lead)
  lead_5s   the same path, the thin venue 5 s behind
For each case: per-game lag distribution, and the drafted decision rule (xcorr_lead.decide) on
STUDIES studies of GAMES games each, against a no-link placebo of the same size.

Run the report:  python tests/test_activity_bias.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import xcorr_lead  # noqa: E402

DURATION_S = 7 * 3600
SEED = 20261003


def hidden_path(rng: np.random.Generator) -> np.ndarray:
    steps = rng.normal(0, 0.0015, DURATION_S)
    jumps = rng.choice(np.arange(600, DURATION_S - 600), 15, replace=False)
    steps[jumps] += rng.choice([-1, 1], 15) * rng.uniform(0.03, 0.10, 15)
    p = np.clip(0.5 + np.cumsum(steps), 0.02, 0.98)
    return p


def trades(rng: np.random.Generator, path: np.ndarray, rate_per_min: float, lag_s: float, venue: str) -> pd.DataFrame:
    n = rng.poisson(rate_per_min / 60 * DURATION_S)
    t = np.sort(rng.uniform(0, DURATION_S, n))
    src = np.clip(np.floor(t - lag_s).astype(int), 0, DURATION_S - 1)
    px = np.round(path[src] + rng.choice([-0.005, 0.005], n), 2).clip(0.01, 0.99)
    return pd.DataFrame({"ts": (t * 1e9).astype("int64"), "venue": venue, "market_id": venue, "kind": "trade",
                         "price": px, "size": 1.0, "side": "unknown"})


def game(rng, k_rate, o_rate, case: str) -> float:
    pk = hidden_path(rng)
    po = hidden_path(rng) if case == "no_link" else pk
    lag_o = 5.0 if case == "lead_5s" else 0.0
    tk = trades(rng, pk, k_rate, 0.0, "kalshi")
    to = trades(rng, po, o_rate, lag_o, "other")
    return xcorr_lead.game_lag(tk, "kalshi", to, "other")


def study(seed: int, k_rate: float, o_rate: float, games: int, studies: int) -> dict:
    rng = np.random.default_rng(seed)
    out = {}
    lags = {c: [[game(rng, k_rate, o_rate, c) for _ in range(games)] for _ in range(studies)]
            for c in ("no_link", "zero_lag", "lead_5s")}
    placebo = [[game(rng, k_rate, o_rate, "no_link") for _ in range(games)] for _ in range(studies)]
    for c, runs in lags.items():
        flat = np.array([x for r in runs for x in r], float)
        flat = flat[~np.isnan(flat)]
        verdicts = [xcorr_lead.decide(r, pl, 0.0)["result"] for r, pl in zip(runs, placebo)]
        out[c] = {"median_lag": float(np.median(flat)) if len(flat) else float("nan"),
                  "share_pos": float((flat > 0).mean()) if len(flat) else float("nan"),
                  "share_ge1": float((flat >= 1).mean()) if len(flat) else float("nan"),
                  "share_lag5": float((np.abs(flat - 5) <= 1).mean()) if len(flat) else float("nan"),
                  "kalshi_leads_rate": float(np.mean([v == "kalshi leads" for v in verdicts])),
                  "verdicts": pd.Series(verdicts).value_counts().to_dict()}
    return out


# ---- tests (small, fast) ----

def test_pipeline_recovers_lead_with_two_busy_venues():
    rng = np.random.default_rng(1)
    lags = [game(rng, 390, 390, "lead_5s") for _ in range(5)]
    assert np.median(lags) == 5


def test_no_link_equal_rates_is_not_a_lead():
    r = study(2, 60, 60, games=30, studies=2)
    assert r["no_link"]["kalshi_leads_rate"] == 0.0


def test_mann_whitney_sanity():
    assert xcorr_lead.mann_whitney_p([5] * 40, [0] * 40) < 1e-6
    assert xcorr_lead.mann_whitney_p([1, 2, 3, 4], [1, 2, 3, 4]) > 0.5


if __name__ == "__main__":
    GAMES, STUDIES = 40, 10
    rows = []
    for label, o_rate in (("polymarket.com-like 5/min", 5), ("Polymarket-US-like 1/min", 1)):
        res = study(SEED, 390, o_rate, GAMES, STUDIES)
        for case, r in res.items():
            rows.append({"pair": f"Kalshi 390/min vs {label}", "case": case, "games": GAMES * STUDIES,
                         "median_lag_s": r["median_lag"], "share_lag_pos": round(r["share_pos"], 3),
                         "share_lag_ge_1s": round(r["share_ge1"], 3), "share_lag_5s_pm1": round(r["share_lag5"], 3),
                         "rule_says_kalshi_leads": f"{r['kalshi_leads_rate']:.0%} of {STUDIES} studies",
                         "verdicts": r["verdicts"]})
    df = pd.DataFrame(rows)
    with pd.option_context("display.width", 250, "display.max_colwidth", 80):
        print(df.to_string(index=False))
    df.to_csv(Path(__file__).resolve().parents[1] / "out" / "activity_bias_report.csv", index=False)


def thinned_self(tk: pd.DataFrame, to: pd.DataFrame) -> pd.DataFrame:
    """Activity-matched placebo: the thin venue's trade TIMES, with Kalshi's own as-of trade price (backward)."""
    k = tk.sort_values("ts")[["ts", "price"]]
    o = to.sort_values("ts")[["ts"]]
    m = pd.merge_asof(o, k, on="ts", direction="backward").dropna()
    return m.assign(venue="other", market_id="other", kind="trade", size=1.0, side="unknown")


def game_with_matched_null(rng, k_rate, o_rate, case: str) -> tuple[float, float]:
    pk = hidden_path(rng)
    po = hidden_path(rng) if case == "no_link" else pk
    tk = trades(rng, pk, k_rate, 0.0, "kalshi")
    to = trades(rng, po, o_rate, 5.0 if case == "lead_5s" else 0.0, "other")
    return (xcorr_lead.game_lag(tk, "kalshi", to, "other"),
            xcorr_lead.game_lag(tk, "kalshi", thinned_self(tk, to), "other"))
