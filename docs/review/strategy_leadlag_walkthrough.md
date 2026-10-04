# strategy.py and leadlag.py walkthrough: only the functions the run imports (Rule-7 review packet)

The run (scripts/final_test_run.py) reaches these files only through laggard.py: strategy.decision_time_ns, strategy.signals, leadlag.detect_jumps. Nothing else in either file feeds a reported number (leadlag.xcorr_lag feeds only the exploratory trade-based lag; tests/test_legacy_not_imported.py checks the run never imports legacy.backtest).

File: strategy.py at e2c38e8 (branch t15-final), 52 lines. Only the two functions the run imports (through laggard.py): decision_time_ns and signals.

Tags at line end: **[TIME]** touches decision time, fill time, windows, outages or timestamps. **[MONEY]** touches price, fee, spread, threshold or P&L. Tests per block: every test that calls a function defined in the block.

## Lines 20 to 23

decision_time_ns: a decision taken from grid label g (which covers [g, g + 1)) is stamped (g + 1) s, the first instant every value at labels <= g is known.

```python
 20  def decision_time_ns(g: int) -> int:                                                         [TIME]
 21      """A decision made from label g is knowable at g + 1 s (label g covers [g, g + 1))."""   [TIME]
 22      return (int(g) + 1) * 1_000_000_000                                                      [TIME]
 23
```

Tests: `test_leadlag.py::test_decisions_are_stamped_after_their_grid_label (via signals)`

## Lines 25 to 52

signals: one position at a time. For each detected leader jump (in label order), skip it while a position is open; enter if the gap A - B in the jump direction at the jump label is >= the entry gap; exit at the first later label whose gap is below the exit gap, else at jump + timeout (or the last label); decisions stamped by decision_time_ns.

```python
 25  def signals(pa: pd.Series, pb: pd.Series, jumps: pd.DataFrame, entry_gap_cents: float = 2.0,
 26              exit_gap_cents: float = 1.0, timeout_s: int = 60, qty: int = 1) -> pd.DataFrame:
 27      """One position at a time. Entry on a detected A jump if A - B (in the jump direction) >= entry_gap."""
 28      rows = []
 29      busy_until = None
 30      gaps = (pa - pb)                                                                                           [MONEY]
 31      for j in jumps.sort_values("jump_g").itertuples():
 32          g = j.jump_g                                                                                           [TIME]
 33          if busy_until is not None and g <= busy_until:                                                         [TIME]
 34              continue
 35          if g not in gaps.index:                                                                                [TIME]
 36              continue
 37          d = j.direction
 38          if gaps.loc[g] * d < entry_gap_cents / 100.0 - EPS:                                                    [MONEY]
 39              continue
 40          # Exit: first later label h where the gap has closed below exit_gap, or the timeout.
 41          later = gaps.loc[g + 1: g + timeout_s] * d                                                             [TIME] [MONEY]
 42          closed = later[later < exit_gap_cents / 100.0 - EPS]                                                   [MONEY]
 43          if len(closed):
 44              h, reason = int(closed.index[0]), "gap_closed"                                                     [TIME]
 45          else:
 46              h, reason = int(min(g + timeout_s, gaps.index.max())), "timeout"                                   [TIME]
 47          rows.append({"entry_g": int(g), "exit_g": h, "direction": int(d), "qty": qty, "exit_reason": reason,
 48                       "entry_decision_ns": decision_time_ns(g), "exit_decision_ns": decision_time_ns(h),        [TIME]
 49                       "gap_at_entry_cents": round(gaps.loc[g] * d * 100, 2)})                                   [MONEY]
 50          busy_until = h                                                                                         [TIME]
 51      return pd.DataFrame(rows, columns=["entry_g", "exit_g", "direction", "qty", "exit_reason",
 52                                         "entry_decision_ns", "exit_decision_ns", "gap_at_entry_cents"])
```

Tests: `test_leadlag.py::test_decisions_are_stamped_after_their_grid_label`

File: leadlag.py at 4ee5ff2 (branch t15-final), 105 lines. Only detect_jumps, which the run imports through laggard.py. xcorr_lag is NOT used by the run: the confirmatory lag is xcorr_lead.game_lag_mid; xcorr_lag feeds only the exploratory trade-based game_lag.

Tags at line end: **[TIME]** touches decision time, fill time, windows, outages or timestamps. **[MONEY]** touches price, fee, spread, threshold or P&L. Tests per block: every test that calls a function defined in the block.

## Lines 22 to 49

detect_jumps: at each label g, compare p[g] with the min and max over the trailing labels g - window_s..g (past and current only); a move of at least jump_cents up (from the min) or down (from the max) is a jump in that direction, recorded with its start label; then skip window_s labels so one play counts once. NaN labels are skipped.

```python
 22  def detect_jumps(p: pd.Series, jump_cents: float = 3.0, window_s: int = 10) -> pd.DataFrame:             [TIME] [MONEY]
 23      """Every move of at least jump_cents within a trailing window_s seconds on series p.                 [TIME] [MONEY]
 24
 25      At label g, compares p[g] with the min and max of p over the trailing labels g-window_s..g           [TIME]
 26      (only past and current values). After a jump, skips window_s labels so one play counts once.         [TIME] [MONEY]
 27      """
 28      x = p.to_numpy()                                                                                     [MONEY]
 29      idx = p.index.to_numpy()                                                                             [TIME]
 30      J = jump_cents / 100.0                                                                               [TIME]
 31      out, g, n = [], 0, len(x)                                                                            [TIME]
 32      while g < n:                                                                                         [TIME]
 33          lo = max(0, g - window_s)                                                                        [TIME]
 34          w = x[lo:g + 1]
 35          if np.isnan(x[g]) or np.all(np.isnan(w)):
 36              g += 1                                                                                       [TIME] [MONEY]
 37              continue                                                                                     [MONEY]
 38          i_min, i_max = lo + int(np.nanargmin(w)), lo + int(np.nanargmax(w))                              [MONEY]
 39          up, dn = x[g] - x[i_min], x[i_max] - x[g]                                                        [MONEY]
 40          if up >= J - EPS or dn >= J - EPS:
 41              d = 1 if up >= dn else -1
 42              start = i_min if d == 1 else i_max                                                           [TIME]
 43              out.append({"jump_g": int(idx[g]), "start_g": int(idx[start]), "direction": d,               [TIME] [MONEY]
 44                          "jump_cents": round(abs(x[g] - x[start]) * 100, 2), "level_before": x[start]})
 45              g += window_s + 1                                                                            [TIME]
 46          else:                                                                                            [TIME]
 47              g += 1
 48      return pd.DataFrame(out, columns=["jump_g", "start_g", "direction", "jump_cents", "level_before"])
 49
```

Tests: `test_leadlag.py::test_decisions_are_stamped_after_their_grid_label (via leadlag)`, `test_leadlag.py::test_no_jumps_gives_empty_table_not_crash (via leadlag)`


## Where a lookahead could hide, and why each is safe

1. **The jump (leadlag.py lines 33 to 42).** `w = x[lo:g + 1]` with `lo = g - window_s`: only labels up to and including g. The jump's direction and start come from that trailing window. Tests: `test_laggard.py::test_no_lookahead_future_rows_do_not_change_past_decisions`, `test_laggard.py::test_signal_and_exact_pnl_at_1s_market_delay`.

2. **The entry (strategy.py lines 35 to 39, 48).** The entry gap is read at the jump label g (`gaps.loc[g]`), from mids known by the end of second g, and the decision is stamped (g + 1) s. Test: `test_laggard.py::test_signal_and_exact_pnl_at_1s_market_delay` (decision 101 s for a jump at label 100).

3. **The exit (strategy.py lines 41 to 46).** The forward scan `gaps.loc[g + 1: g + timeout_s]` picks the exit label h from the gap AT h, and the exit is stamped (h + 1) s, so the exit uses no data after its own decision. A NaN gap (break, empty side) never triggers a close, so the trade times out; its fill is then subject to laggard.quote_at's break and trading-end skips. Tests: `test_laggard.py::test_latency_curve_starts_at_market_delay_and_edge_dies_after_follower_moves`, `test_laggard.py::test_fill_scheduled_across_outage_is_skipped`.

## Points for your line-by-line review (choices to confirm)

- strategy.py lines 3 to 5 and 16: the PROVISIONAL defaults (entry gap 2 cents) are not used by the run; laggard.py passes the Amendment 2 setting (4 cent jump, 10 s, 3 cent entry, 1 cent exit, 60 s, 10 contracts).
- strategy.py line 33: a jump during an open position is dropped, not queued.
- strategy.py line 46: if the window ends before the timeout, the exit is at the last label ("timeout" reason); laggard.quote_at then skips the fill if it lands at or after the trading end (v2 Amendment 5).
- leadlag.py line 45: after a jump the scan skips window_s + 1 labels, so two jumps closer than 11 s count once.
