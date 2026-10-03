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


def mann_whitney_p(a, b) -> float:
    """Two-sided Mann-Whitney U test, normal approximation with tie correction (no scipy)."""
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


def decide(real_lags, placebo_lags, d_s: float = 0.0, x: str = "kalshi", y: str = "other") -> dict:
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
    if med >= MIN_LEAD_S and p < 0.05 and share_pos >= MIN_SHARE:
        out["result"] = f"{x} leads"
    elif med <= -MIN_LEAD_S and p < 0.05 and share_neg >= MIN_SHARE:
        out["result"] = f"{y} leads"
    else:
        out["result"] = "neither venue leads consistently"
    return out
