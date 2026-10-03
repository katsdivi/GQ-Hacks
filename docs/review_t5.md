# Review list for T5 to T7 (branch t5-made-it, commit 621e625)

Every line where time enters, file by file. One line each: `file:line`, what it does, why it cannot see the future.
Convention (align.py:4-8): grid label g covers [g, g+1) s; a label-g value is only known at g+1 s; decisions from label g are stamped g+1 s; fills at stamp + latency.

**Flag for Divi and Alden (needs sign-off):** the v2 polymarket.com shift (rows marked FLAG). Shifting block times earlier by D p90 places a trade matched at true time m at m + D - D90, which is at or before m for about 90% of trades. When polymarket.com is the venue traded, its gap values and fill prices can therefore include trades matched up to (D90 - D) s after the decision. This is what v2 asks for and is conservative when the follower is catching up to the leader (we fill at the already-moved price), but it is a deliberate exception to "never peek" and is not conservative in every case (for example a polymarket.com move away from the leader). Options: keep (v2 as written), or also run with the shift = 0 and report both.

## align.py

- align.py:27: sorts one venue's rows by (ts, kind), stable: ordering only, no values move across time.
- align.py:28: shift in ns from shift_s; only ever subtracted (lines 34, 37), so timestamps move earlier, never later. FLAG when used for polymarket.com as the traded venue (see above).
- align.py:32: latest bid so far via forward fill: each row sees only bids at or before it.
- align.py:33: latest ask so far via forward fill: same.
- align.py:34: mid from the forward-filled bid and ask; timestamp = that row's own ts minus shift.
- align.py:37: trades-only path: each trade keeps its own ts minus shift.
- align.py:46: floors ts to whole seconds (label g); a value from [g, g+1) is labelled g and treated as known at g+1 (decision_time_ns), so the floor cannot give a head start.
- align.py:47: last value inside each second (groupby last within the same label only).
- align.py:49: forward fill across empty seconds: carries the past value forward, never a later one back.
- align.py:55-56: restricts both venues to the overlapping seconds and forward fills; the end bound uses the data's last second (global range only; see strategy.py:44).
- align.py:61: the only cross-venue join helper: merge_asof direction="backward" (not used by run.py yet; fills use backtest.py:62).

## leadlag.py (measurement only; nothing here feeds a trading decision except jump_g and direction)

- leadlag.py:33-34: jump test at label g uses the trailing window g-window_s..g only.
- leadlag.py:43: records jump_g = g (the label where the move completed) and start_g (earlier label of the extreme).
- leadlag.py:45: skips forward window_s labels after a jump (one play counts once); skipping ahead is not peeking.
- leadlag.py:64: follower baseline F0 at start_g (before the leader moved).
- leadlag.py:66: follower segment start_g .. jump_g + max_wait_s: looks FORWARD by design to measure the response time. Measurement only; strategy.py never reads response_s or covered.
- leadlag.py:70: response_s = first covering label minus jump_g (negative if the follower moved first).
- leadlag.py:78-79: cross-correlation of 1 s returns over the whole series at lags -15..+15: whole-sample statistic, measurement only.
- leadlag.py:100: contract jump_ts = (jump_g + 1) s, the time the jump was knowable.

## strategy.py

- strategy.py:20: decision_time_ns(g) = (g + 1) s: the first instant every label-g value is known.
- strategy.py:29: walks jumps in time order.
- strategy.py:30-36: entry test at jump label g uses gaps.loc[g] = A[g] - B[g], both labels <= g. Uses only jump_g and direction from leadlag (no forward-looking columns). FLAG if B = polymarket.com (shifted values).
- strategy.py:39-40: exit = first later label h in g+1 .. g+timeout_s where the gap at h is below exit_gap; the condition at h uses values at h only, and the exit is stamped h + 1 (line 46).
- strategy.py:44: timeout exit at g + timeout_s, capped at the last label of the data (uses the data end only to stop at the end of the file).
- strategy.py:46: entry and exit stamped at g + 1 and h + 1 s.
- strategy.py:48 (busy_until): no new entry until after the exit label h, so positions never overlap.

## backtest.py

- backtest.py:37-38: follower rows sorted by (ts, kind); same earlier-only shift as align.py. FLAG for polymarket.com as follower.
- backtest.py:42-43: as-of bid and ask by forward fill (book case, fake game only).
- backtest.py:47: trades-only quotes: each trade's own ts, price +/- half-spread.
- backtest.py:57: latency in ns.
- backtest.py:62: as-of lookup: last quote with ts <= t (searchsorted side="right" minus 1). Never a later quote.
- backtest.py:67: fill times = decision stamp + latency, for entry and exit.
- backtest.py:68: fill prices from the as-of quote at those fill times.
- backtest.py:88, 91: contract rows stamped at the fill times.

## run.py

- run.py:67: shift for B = D p90 only when B is polymarket.com (v2 rule 2). FLAG.
- run.py:68: signal venue A is never shifted: polymarket.com as signal keeps block time (arrives late, conservative).
- run.py:69-71: builds both grids and the overlap (align.py rules above).
- run.py:74-75: fills on B use the same shift as B's grid, so signals and fills share one clock.
- run.py:122: input ticks sorted by (ts, venue, kind), stable: determinism only.

## Not time-related but worth checking

- costs.py: 2c per contract per fill on both fills (4c round trip), labelled PLACEHOLDER FEE; half-spread 0.5c when no book.
- backtest.py:29-32: test games (kickoff >= 2026-08-01) refused without --final-test; sample exempt.
- run.py:152: variants.csv row per direction for real games; git sha marked -dirty if .py files are uncommitted. Two earlier rows (04:27:45Z, sha 8cf0670) were logged before the code was committed; kept per rule 3.
