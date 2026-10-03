"""Cross-correlation lead test (HYPOTHESIS_v2.md Amendment 2 draft, Parts A and B).

Per game: both venues' trailing 3 s median trade prices on the common 1 s grid (align.py), then the
lag (s) maximising corr(Kalshi return at g, other-venue return at g + lag), max lag 15 s
(leadlag.xcorr_lag). Positive = Kalshi first. Corrected lag = lag - D (median match-to-block delay
for polymarket.com, 0 for Polymarket US).

Decision (drafted rule): on the qualifying games (>= 50 trades on each venue in kickoff - 2 h to
+ 5 h), with the unrelated-games placebo built the same way as the null:
  Kalshi leads iff median corrected lag >= 1 s AND two-sided Mann-Whitney real vs placebo p < 0.05
  AND >= 60% of qualifying games have corrected lag > 0; symmetric for the other venue;
  fewer than 30 qualifying games -> "inconclusive".

No prices are printed; this module returns lags and decisions only.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import align
import leadlag

PRICE_WINDOW_S = 3.0
MAX_LAG_S = 15
MIN_TRADES = 50
MIN_GAMES = 30
MIN_LEAD_S = 1.0
MIN_SHARE = 0.60


def game_lag(ticks_x: pd.DataFrame, venue_x: str, ticks_y: pd.DataFrame, venue_y: str,
             max_lag_s: int = MAX_LAG_S) -> float:
    """xcorr lag of venue_x (Kalshi) vs venue_y; positive = x first. NaN if the grids do not overlap."""
    gx = align.to_grid(align.trade_median_events(ticks_x, venue_x, PRICE_WINDOW_S))
    gy = align.to_grid(align.trade_median_events(ticks_y, venue_y, PRICE_WINDOW_S))
    if gx.empty or gy.empty:
        return float("nan")
    gx, gy = align.common_grid(gx, gy)
    if len(gx) < 2 * max_lag_s + 2:
        return float("nan")
    lag, corr = leadlag.xcorr_lag(gx, gy, max_lag_s)
    return float(lag) if np.isfinite(corr[lag]) else float("nan")


NS = 1_000_000_000
_EMPTY = -1.0   # sentinel for "last snapshot had an empty side" so a grid carry never fills across it


def mid_snapshots(ticks: pd.DataFrame, venue: str) -> pd.Series:
    """Mid per recorded top-of-book snapshot (HYPOTHESIS_v2.md Amendment 2): index ts (ns), value
    (bid + ask) / 2, NaN when either side is empty. The collector writes the bid row and the ask row of a
    snapshot with the same receipt ts and writes no row for an empty side, so a snapshot ts with only one
    kind means the other side was empty. One market per venue (the runner picks it)."""
    b = ticks[(ticks["venue"] == venue) & ticks["kind"].isin(["bid", "ask"])]
    if b.empty:
        return pd.Series(dtype="float64")
    assert b["market_id"].nunique() == 1, f"{venue}: one market per venue, got {b['market_id'].nunique()}"
    w = b.pivot_table(index="ts", columns="kind", values="price", aggfunc="last").sort_index()
    for k in ("bid", "ask"):
        if k not in w:
            w[k] = np.nan
    return (w["bid"] + w["ask"]) / 2


def mid_grid(snap: pd.Series) -> pd.Series:
    """1 s grid label g -> mid of the last snapshot at or before the end of second g (backward only).
    A second with no snapshot carries the previous snapshot's state; if that state had an empty side the
    mid stays undefined (NaN) until a two-sided snapshot arrives."""
    if snap.empty:
        return pd.Series(dtype="float64")
    g = snap.index.to_numpy() // NS
    last = pd.Series(snap.fillna(_EMPTY).to_numpy(), index=g).groupby(level=0).last()
    full = np.arange(last.index.min(), last.index.max() + 1, dtype="int64")
    return last.reindex(full).ffill().replace(_EMPTY, np.nan)


def mid_changes(grid: pd.Series) -> pd.Series:
    """Per grid second: defined mid minus the previous DEFINED mid; NaN where the mid is undefined or no
    earlier defined mid exists. Duplicate rows cannot create a change (the mid does not move)."""
    prev = grid.ffill().shift(1)
    return (grid - prev).where(grid.notna())


def n_mid_changes(grid: pd.Series) -> int:
    """Amendment 2 qualification count: grid seconds whose defined mid differs from the previous defined mid."""
    c = mid_changes(grid)
    return int((c.notna() & (c.abs() > 1e-12)).sum())


def game_lag_mid(ticks_x: pd.DataFrame, venue_x: str, ticks_y: pd.DataFrame, venue_y: str,
                 max_lag_s: int = MAX_LAG_S) -> float:
    """Book-midpoint version (Amendment 2 confirmatory test): xcorr of 1 s mid changes, mids defined only
    when both sides exist, never filled across an empty side. Seconds without a defined change on either
    venue drop out of the correlation (pairwise). Positive = x (Kalshi) first."""
    gx, gy = mid_grid(mid_snapshots(ticks_x, venue_x)), mid_grid(mid_snapshots(ticks_y, venue_y))
    if gx.empty or gy.empty:
        return float("nan")
    lo, hi = max(gx.index.min(), gy.index.min()), min(gx.index.max(), gy.index.max())
    if hi - lo + 1 < 2 * max_lag_s + 2:
        return float("nan")
    idx = np.arange(lo, hi + 1, dtype="int64")
    rx, ry = mid_changes(gx).reindex(idx), mid_changes(gy).reindex(idx)
    corr = {lag: float(rx.corr(ry.shift(-lag))) for lag in range(-max_lag_s, max_lag_s + 1)}
    corr = {k: (v if v == v else -np.inf) for k, v in corr.items()}
    lag = max(corr, key=corr.get)
    return float(lag) if np.isfinite(corr[lag]) else float("nan")


def mann_whitney_p(a, b) -> float:
    """Two-sided Mann-Whitney U test (scipy.stats.mannwhitneyu, default method). NaNs dropped."""
    from scipy.stats import mannwhitneyu
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) == 0 or len(b) == 0:
        return float("nan")
    if np.unique(np.concatenate([a, b])).size == 1:
        return 1.0
    return float(mannwhitneyu(a, b, alternative="two-sided").pvalue)


def mann_whitney_p_custom(a, b) -> float:
    """Cross-check only (tests): the earlier hand-written version. Normal approximation, tie and continuity
    correction."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return float("nan")
    allv = np.concatenate([a, b])
    ranks = pd.Series(allv).rank(method="average").to_numpy()
    u1 = ranks[:n1].sum() - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    _, counts = np.unique(allv, return_counts=True)
    n = n1 + n2
    tie = (counts ** 3 - counts).sum() / (n * (n - 1)) if n > 1 else 0.0
    sigma = math.sqrt(n1 * n2 / 12 * ((n + 1) - tie))
    if sigma == 0:
        return 1.0
    z = (abs(u1 - mu) - 0.5) / sigma
    return float(math.erfc(max(z, 0.0) / math.sqrt(2)))


def decide(real_lags, placebo_lags, d_s: float = 0.0, x: str = "kalshi", y: str = "other",
           min_lead_s: float = MIN_LEAD_S, alpha: float = 0.05) -> dict:
    r = np.asarray(real_lags, float) - d_s
    pl = np.asarray(placebo_lags, float) - d_s
    r, pl = r[~np.isnan(r)], pl[~np.isnan(pl)]
    out = {"n_qualifying": int(len(r)), "n_placebo": int(len(pl))}
    if len(r) < MIN_GAMES:
        out["result"] = f"inconclusive ({len(r)} qualifying games < {MIN_GAMES})"
        return out
    med, p = float(np.median(r)), mann_whitney_p(r, pl)
    share_pos, share_neg = float((r > 0).mean()), float((r < 0).mean())
    out.update({"median_corrected_lag_s": med, "mann_whitney_p": p, "share_positive": share_pos,
                "share_negative": share_neg, "placebo_median_s": float(np.median(pl)) if len(pl) else float("nan")})
    out["alpha"] = alpha
    if med >= min_lead_s and p < alpha and share_pos >= MIN_SHARE:
        out["result"] = f"{x} leads"
    elif med <= -min_lead_s and p < alpha and share_neg >= MIN_SHARE:
        out["result"] = f"{y} leads"
    else:
        out["result"] = "neither venue leads consistently"
    return out


def decide_holm(inputs: dict, alpha: float = 0.05) -> dict:
    """Holm across the venue tests (Amendment 3 draft): inputs = {test: (real_lags, placebo_lags, y, min_lead_s)}.
    Step-down: the smaller Mann-Whitney p is judged at alpha / 2; only if that test's p passes is the larger p
    judged at alpha. A test whose p fails its Holm level cannot be called a lead (other criteria unchanged)."""
    p = {t: mann_whitney_p(np.asarray(r, float), np.asarray(pl, float)) for t, (r, pl, _y, _m) in inputs.items()}
    order = sorted(p, key=lambda t: (np.inf if p[t] != p[t] else p[t]))
    levels, still = {}, True
    for i, t in enumerate(order):
        lv = alpha / (len(order) - i)
        levels[t] = lv if still else 0.0             # 0.0: Holm stopped, nothing below can pass
        still = still and (p[t] == p[t]) and p[t] < lv
    out = {}
    for t, (r, pl, y, m) in inputs.items():
        out[t] = {**decide(r, pl, 0.0, "kalshi", y, min_lead_s=m, alpha=levels[t]), "holm_level": levels[t]}
    return out
