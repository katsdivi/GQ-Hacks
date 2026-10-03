"""Align venues on one clock: a common 1-second grid (HYPOTHESIS_v2.md, "One clock").

Grid convention (used by leadlag.py, strategy.py and backtest.py):
  * Every timestamp is floored to a whole second. Grid label g covers [g, g + 1) seconds.
  * The value at label g is the last observation with timestamp < g + 1 s, carried forward.
  * Because a label-g value can include an observation from late in that second, anything
    computed from label g is only known at time g + 1. Decisions taken on label g are
    stamped at g + 1 s (see strategy.decision_time_ns).

Kalshi timestamps (microseconds) are floored the same way as polymarket.com block times
(already whole seconds), so neither venue gets a rounding head start.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

NS = 1_000_000_000


def venue_events(ticks: pd.DataFrame, venue: str, shift_s: float = 0.0) -> pd.DataFrame:
    """Time-ordered (ts, price) observations for one venue: mid when a book exists, else last trade.

    shift_s > 0 moves every timestamp of this venue EARLIER by shift_s seconds (the v2 block-time
    correction when trading on polymarket.com). It never moves anything later.
    """
    v = ticks[ticks["venue"] == venue].sort_values(["ts", "kind"], kind="stable")
    shift = int(round(shift_s * NS))
    book = v[v["kind"].isin(["bid", "ask"])]
    if len(book) and set(book["kind"].unique()) == {"bid", "ask"}:
        # Mid of the latest bid and latest ask seen so far (forward fill only = backward-looking).
        bid = book["price"].where(book["kind"] == "bid").ffill()
        ask = book["price"].where(book["kind"] == "ask").ffill()
        ev = pd.DataFrame({"ts": book["ts"].to_numpy() - shift, "price": ((bid + ask) / 2).to_numpy()})
    else:
        tr = v[v["kind"] == "trade"]
        ev = pd.DataFrame({"ts": tr["ts"].to_numpy() - shift, "price": tr["price"].to_numpy()})
    ev = ev.dropna(subset=["price"])
    return ev.sort_values("ts", kind="stable").reset_index(drop=True)


def trade_median_events(ticks: pd.DataFrame, venue: str, window_s: float = 3.0) -> pd.DataFrame:
    """PROVISIONAL (pre-spec) price series: at each trade, the median of this venue's trade prices
    in the trailing window (t - window_s, t], past and current trades only. Damps bid/ask bounce
    on trades-only history. Never shifted: decisions and gap checks use raw timestamps
    (HYPOTHESIS_v2.md Amendment 1).
    """
    tr = ticks[(ticks["venue"] == venue) & (ticks["kind"] == "trade")].sort_values("ts", kind="stable")
    if tr.empty:
        return pd.DataFrame(columns=["ts", "price"])
    s = pd.Series(tr["price"].to_numpy(), index=pd.to_datetime(tr["ts"].to_numpy(), utc=True))
    med = s.rolling(pd.Timedelta(seconds=window_s), closed="right").median()   # (t - w, t]
    return pd.DataFrame({"ts": tr["ts"].to_numpy(), "price": med.to_numpy()})


def to_grid(ev: pd.DataFrame) -> pd.Series:
    """Events -> per-second series indexed by integer second label g (last value in [g, g+1), ffilled)."""
    if ev.empty:
        return pd.Series(dtype="float64")
    g = ev["ts"].to_numpy() // NS                      # floor to whole seconds
    last = pd.Series(ev["price"].to_numpy(), index=g).groupby(level=0).last()
    full = np.arange(last.index.min(), last.index.max() + 1, dtype="int64")
    return last.reindex(full).ffill()


def common_grid(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Restrict two grid series to the seconds where both venues have started; carry forward."""
    lo, hi = max(a.index.min(), b.index.min()), min(a.index.max(), b.index.max())
    idx = np.arange(lo, hi + 1, dtype="int64")
    return a.reindex(idx).ffill(), b.reindex(idx).ffill()


def asof_join(left: pd.DataFrame, right: pd.DataFrame, on: str = "ts", **kw) -> pd.DataFrame:
    """The only join allowed between venues: each left row gets the last right row at or before it."""
    return pd.merge_asof(left.sort_values(on), right.sort_values(on), on=on, direction="backward", **kw)
