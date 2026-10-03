"""Signal rule: trade the follower venue B after a jump on the leader venue A (venue-neutral).

PROVISIONAL (pre-spec) defaults from docs/BUILD_PLAN.md T6: entry_gap=2c, exit when the gap
is under 1c or after timeout_s=60 s. Order size per signal: 10 contracts (costs.ORDER_SIZE,
frozen in docs/stats_plan.md). Alden to confirm.

Inputs are per-second grid series (align.py). A decision taken from grid label g only uses
values at labels <= g and is stamped at g + 1 s, the first instant those values are all known.
Fills (backtest.py) then happen at that stamp + latency.
"""
from __future__ import annotations

import pandas as pd

PROVISIONAL = dict(entry_gap_cents=2.0, exit_gap_cents=1.0, timeout_s=60, qty=10)
EPS = 1e-9


def decision_time_ns(g: int) -> int:
    """A decision made from label g is knowable at g + 1 s (label g covers [g, g + 1))."""
    return (int(g) + 1) * 1_000_000_000


def signals(pa: pd.Series, pb: pd.Series, jumps: pd.DataFrame, entry_gap_cents: float = 2.0,
            exit_gap_cents: float = 1.0, timeout_s: int = 60, qty: int = 1) -> pd.DataFrame:
    """One position at a time. Entry on a detected A jump if A - B (in the jump direction) >= entry_gap."""
    rows = []
    busy_until = None
    gaps = (pa - pb)
    for j in jumps.sort_values("jump_g").itertuples():
        g = j.jump_g
        if busy_until is not None and g <= busy_until:
            continue
        if g not in gaps.index:
            continue
        d = j.direction
        if gaps.loc[g] * d < entry_gap_cents / 100.0 - EPS:
            continue
        # Exit: first later label h where the gap has closed below exit_gap, or the timeout.
        later = gaps.loc[g + 1: g + timeout_s] * d
        closed = later[later < exit_gap_cents / 100.0 - EPS]
        if len(closed):
            h, reason = int(closed.index[0]), "gap_closed"
        else:
            h, reason = int(min(g + timeout_s, gaps.index.max())), "timeout"
        rows.append({"entry_g": int(g), "exit_g": h, "direction": int(d), "qty": qty, "exit_reason": reason,
                     "entry_decision_ns": decision_time_ns(g), "exit_decision_ns": decision_time_ns(h),
                     "gap_at_entry_cents": round(gaps.loc[g] * d * 100, 2)})
        busy_until = h
    return pd.DataFrame(rows, columns=["entry_g", "exit_g", "direction", "qty", "exit_reason",
                                       "entry_decision_ns", "exit_decision_ns", "gap_at_entry_cents"])
