"""Lead/lag measurement between a leader venue A and a follower venue B (venue-neutral).

PROVISIONAL (pre-spec): docs/math_spec.md does not exist yet. Defaults from docs/BUILD_PLAN.md
T5: jump_cents=3, window_s=10, cover=0.8, max_wait_s=60, grid_s=1 (v2 fixes a 1 s grid),
max_lag_s=15. Alden to confirm every number.

All inputs are per-second grid series from align.to_grid (label g = value known at g + 1).
Run it both ways (A=cme/kalshi/polymarket as leader, B the other) and compare.

This module MEASURES lags. response_times looks forward in the follower's series on purpose
(that is what a response time is); nothing here is used to make trading decisions.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

PROVISIONAL = dict(jump_cents=3.0, window_s=10, cover=0.8, max_wait_s=60, max_lag_s=15)
EPS = 1e-9


def detect_jumps(p: pd.Series, jump_cents: float = 3.0, window_s: int = 10) -> pd.DataFrame:
    """Every move of at least jump_cents within a trailing window_s seconds on series p.

    At label g, compares p[g] with the min and max of p over the trailing labels g-window_s..g
    (only past and current values). After a jump, skips window_s labels so one play counts once.
    """
    x = p.to_numpy()
    idx = p.index.to_numpy()
    J = jump_cents / 100.0
    out, g, n = [], 0, len(x)
    while g < n:
        lo = max(0, g - window_s)
        w = x[lo:g + 1]
        if np.isnan(x[g]) or np.all(np.isnan(w)):
            g += 1
            continue
        i_min, i_max = lo + int(np.nanargmin(w)), lo + int(np.nanargmax(w))
        up, dn = x[g] - x[i_min], x[i_max] - x[g]
        if up >= J - EPS or dn >= J - EPS:
            d = 1 if up >= dn else -1
            start = i_min if d == 1 else i_max
            out.append({"jump_g": int(idx[g]), "start_g": int(idx[start]), "direction": d,
                        "jump_cents": round(abs(x[g] - x[start]) * 100, 2), "level_before": x[start]})
            g += window_s + 1
        else:
            g += 1
    return pd.DataFrame(out, columns=["jump_g", "start_g", "direction", "jump_cents", "level_before"])


def response_times(jumps: pd.DataFrame, follower: pd.Series, cover: float = 0.8, max_wait_s: int = 60) -> pd.DataFrame:
    """Seconds from the leader's jump label until the follower has moved cover x the jump, same direction.

    Follower baseline F0 = follower at the leader's jump START label (before the leader moved).
    Search runs from the start label to jump label + max_wait_s, so a follower that moved first
    gets a negative response. Never-covered jumps are KEPT with covered=False, response_s NaN.
    """
    f = follower
    rows = []
    for j in jumps.itertuples():
        if j.start_g not in f.index:
            rows.append({"response_s": np.nan, "covered": False})
            continue
        f0 = f.loc[j.start_g]
        target = cover * j.jump_cents / 100.0
        seg = f.loc[j.start_g: j.jump_g + max_wait_s]
        moved = (seg - f0) * j.direction >= target - EPS
        if moved.any():
            g_hit = int(moved.idxmax())
            rows.append({"response_s": float(g_hit - j.jump_g), "covered": True})
        else:
            rows.append({"response_s": np.nan, "covered": False})
    return pd.concat([jumps.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def xcorr_lag(a: pd.Series, b: pd.Series, max_lag_s: int = 15) -> tuple[int, dict]:
    """Lag (s) maximising corr(return of A at g, return of B at g + lag). Positive = B follows A."""
    ra, rb = a.diff(), b.diff()
    corr = {lag: float(ra.corr(rb.shift(-lag))) for lag in range(-max_lag_s, max_lag_s + 1)}
    corr = {k: (v if v == v else -np.inf) for k, v in corr.items()}
    return max(corr, key=corr.get), corr


def leadlag(pa: pd.Series, pb: pd.Series, jump_cents=3.0, window_s=10, cover=0.8, max_wait_s=60,
            max_lag_s=15) -> tuple[pd.DataFrame, dict]:
    """A leads, B follows. Returns (per-jump table, summary)."""
    jumps = detect_jumps(pa, jump_cents, window_s)
    resp = response_times(jumps, pb, cover, max_wait_s)
    lag, _ = xcorr_lag(pa, pb, max_lag_s)
    cov = resp[resp["covered"]]
    summary = {"n_jumps": int(len(resp)), "n_covered": int(len(cov)),
               "median_response_s": float(cov["response_s"].median()) if len(cov) else float("nan"),
               "xcorr_lag_s": int(lag)}
    return resp, summary


def to_contract(resp: pd.DataFrame, leader: str, follower: str) -> pd.DataFrame:
    """out/leadlag/<game_id>.parquet columns. jump_ts = when the jump was knowable: (jump_g + 1) s."""
    return pd.DataFrame({
        "jump_ts": ((resp["jump_g"] + 1) * 1_000_000_000).astype("int64"),
        "jump_cents": resp["jump_cents"], "direction": resp["direction"],
        "response_s": resp["response_s"], "covered": resp["covered"],
        "leader": leader, "follower": follower,
    })
