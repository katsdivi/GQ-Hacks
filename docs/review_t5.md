# Review list for T5 to T7

Every line where time enters, file by file. One line each: `file:line`, what it does, why it cannot see the future.

Branch t5b-fixes, commit e00615a (after HYPOTHESIS_v2.md Amendment 1, bc9d583). The previous version of this list (v0-made-it, 850f081) described the old rule 2 shift, now removed.

Conventions:
- Grid (align.py:4-8): label g covers [g, g+1) s; a label-g value is only known at g+1 s; decisions from label g are stamped g+1 s; fills at stamp + latency.
- Latency axis everywhere: "0 s = decision within 1 s of the move" (grid stamping). The trailing 3 s median price adds its own detection delay on top: about 1 s for a clean step (two of the three trades in the window must be new before the median moves). On the fake game that uses up the full 2 s planted lag, so the fake-game edge is negative even at 0 s (tests/test_leadlag.py checks a 5 s lag still shows positive edge).
- Amendment 1: decisions, gap checks and lead/lag use raw timestamps for every venue. Only polymarket.com ENTRY FILLS in the lower bound use shifted quotes.

**Remaining deliberate exception, for sign-off:** in the lower bound, polymarket.com entry fills use quotes shifted earlier by D p90, so an entry fill at time t can use a trade matched up to (D p90 - D) s after t (typically under 1 s). This is a fill-price assumption chosen to be worse for us (it fills at a price that has moved further toward the leader); no decision or gap check ever sees it. The upper bound uses no shift.

## align.py

- align.py:27-28: venue_events sorts by (ts, kind) and computes a shift that is only ever subtracted (lines 34, 37); run.py no longer calls it with a shift (kept for the book case and tests).
- align.py:32-33: latest bid and ask so far by forward fill: each row sees only quotes at or before it.
- align.py:42-53: trade_median_events (new, PROVISIONAL price series): trades of one venue sorted by ts, no shift.
- align.py:52: rolling time window closed="right": the value at trade t is the median of trades in (t - 3 s, t], past and current only.
- align.py:60: floors ts to whole seconds (label g); values from [g, g+1) are treated as known at g+1 (strategy.decision_time_ns).
- align.py:61-63: last value within each second, then forward fill across empty seconds: past values carried forward, never a later one back.
- align.py:69-70: overlap of the two venues' seconds, forward filled; the end bound uses the data's last second (global range only; see strategy.py:44).
- align.py:75: merge_asof direction="backward", the only cross-venue join helper (fills use backtest.py:65).

## leadlag.py (measurement only; strategy uses only jump_g and direction)

- leadlag.py:33-34: jump test at label g uses the trailing window g-window_s..g only.
- leadlag.py:43: records jump_g (label where the move completed) and start_g (earlier extreme).
- leadlag.py:45: skips forward window_s labels after a jump (one play counts once).
- leadlag.py:64: follower baseline F0 at start_g, before the leader moved.
- leadlag.py:66: follower segment start_g .. jump_g + max_wait_s: looks FORWARD by design to measure the response time; strategy.py never reads response_s or covered.
- leadlag.py:70: response_s = first covering label minus jump_g (negative if the follower moved first).
- leadlag.py:78-79: whole-series cross-correlation of 1 s returns at lags -15..+15 (measurement only).
- leadlag.py:100: contract jump_ts = (jump_g + 1) s, the time the jump was knowable.

## strategy.py (unchanged)

- strategy.py:20: decision_time_ns(g) = (g + 1) s.
- strategy.py:29-36: entry test at jump label g uses gaps.loc[g] = A[g] - B[g], both labels <= g, both unshifted.
- strategy.py:39-40: exit = first later label h in g+1 .. g+timeout_s with gap at h below exit_gap; uses values at h only; stamped h + 1 (line 46).
- strategy.py:44: timeout exit at g + timeout_s, capped at the last label of the data.
- strategy.py:46: entry and exit stamped g + 1 and h + 1 s.
- strategy.py:48: no new entry until after the exit label h.

## backtest.py

- backtest.py:37-38: follower rows sorted; shift only ever subtracted (earlier).
- backtest.py:42-43: as-of bid and ask by forward fill (book case, fake game only).
- backtest.py:47: trades-only quotes: each trade's own ts, price +/- half-spread.
- backtest.py:54: simulate takes separate entry and exit quote tables (Amendment 1).
- backtest.py:61-62: entry quotes qe and exit quotes qx, each sorted by ts.
- backtest.py:65: as-of lookup: last quote with ts <= t (searchsorted right minus 1), never a later quote in that table.
- backtest.py:70: fill times = decision stamp + latency, entry and exit.
- backtest.py:71: entry priced from qe at the entry fill time, exit from qx at the exit fill time.

## run.py

- run.py:46: LATENCY_NOTE "0 s = decision within 1 s of the move", printed with every run, on the chart and in variants.csv notes.
- run.py:93-95: both grids from the trailing median of raw (unshifted) trades; decisions and lead/lag never shifted.
- run.py:98: raw quotes for the follower (no shift).
- run.py:100-101: polymarket.com traded: lower bound = entry on quotes shifted earlier by D p90, exit on raw quotes; upper bound = raw for both.
- run.py:103: Kalshi traded: raw for both (unchanged).
- run.py:106: one simulation per bound, same signals.
- run.py:153: input ticks sorted by (ts, venue, kind), stable: determinism only.

## ingest/download_all.py (run.py fetches missing ticks with this)

- ingest/download_all.py:357: fetch_game refuses sealed test games (kickoff >= 2026-08-01).
- ingest/download_all.py:359: fetch window kickoff - 2 h to kickoff + 5 h (data selection only; nothing in the window is used before its own timestamp).
- ingest/download_all.py:377-381: Kalshi and polymarket.com trades in that window, flipped to P(home wins), timestamps as published (Kalshi created_time, polymarket.com block time).

## Not time-related but worth checking

- costs.py: 2c per contract per fill on both fills (4c round trip), labelled PLACEHOLDER FEE; half-spread 0.5c when no book.
- backtest.py:29-32: test games refused without --final-test; sample exempt.
- run.py variants rows: one per (direction, bound); git sha marked -dirty if .py files are uncommitted.
