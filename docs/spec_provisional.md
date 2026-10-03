# Frozen provisional spec (pre Alden's math_spec.md)

Frozen 2026-10-03 against code at branch t9-costs (19a1001) and experiments/d_estimate.json (603 trades). Every number here is PROVISIONAL until Alden's `docs/math_spec.md` lands; if it differs, that file wins and this one is superseded with a dated note, never edited in place. Applies to the who-leads test and the tuning pipeline in `docs/stats_plan.md`.

## Clock

| Item | Value | Where |
|---|---|---|
| Grid | 1 s; every timestamp floored to whole seconds; label g covers [g, g+1) | align.py |
| When a label is known | g + 1 s; decisions from label g are stamped g + 1 s | strategy.decision_time_ns |
| Kalshi timestamps | trade created_time (microseconds), floored like everything else | ingest/kalshi.py |
| polymarket.com timestamps | on-chain block time, whole seconds (verified 20/20) | ingest/download_all.py |
| Decisions, gaps, lead/lag | raw timestamps, never shifted (v2 Amendment 1) | run.py |
| Latency axis label | "0 s = decision within 1 s of the move" | run.LATENCY_NOTE |

## Price series

Trailing 3-second median of trade prices per venue: at each trade t, the median of that venue's trades in (t - 3 s, t], past data only; then the last value in each grid second, carried forward.

Why 3 s: chosen after seeing the jump counts on nfl_20251116_was_mia under the earlier last-trade series (Kalshi 286 -> 180 jumps, polymarket.com 152 -> 114), to cut last-trade bid/ask bounce. It was not chosen by looking at P&L. The fake game finds 15/15 planted jumps with it.

Consequence: the median moves only once two of the three trades in its window are new, which adds about 1 s of detection delay for a clean step. Smoothing (about 1 s) plus grid stamping (up to 1 s) plus reaction latency means lags under about 3 s total cannot be traded even if they are measurable. On the fake game (planted lag 2 s) the edge is negative at every latency for this reason; with a 5 s planted lag it is positive at 0 s (tests/test_leadlag.py).

## Lead/lag (leadlag.py)

| Parameter | Value |
|---|---|
| Jump | move of at least 3 cents within a trailing 10 s window (`jump_cents=3`, `window_s=10`) |
| One play counts once | skip 10 s after a jump |
| Covered | follower moves at least 0.8 of the jump, same direction (`cover=0.8`), from its level at the leader's jump start |
| Search window | leader's jump start to jump + 60 s (`max_wait_s=60`); never-covered jumps kept with covered=False |
| Response time | first covering second minus the leader's jump second (negative = follower moved first) |
| Cross-correlation | 1 s returns, lags -15..+15 s (`max_lag_s=15`), secondary statistic |

## Strategy (strategy.py)

| Parameter | Value |
|---|---|
| Entry | on a detected leader jump at label g, if (leader - follower) in the jump direction >= 2 cents (`entry_gap_cents=2`) |
| Exit | first later label where that gap < 1 cent (`exit_gap_cents=1`), or 60 s (`timeout_s=60`) |
| Positions | one at a time per direction per game |
| Order size | 10 contracts per signal (`qty=10`, costs.ORDER_SIZE) |
| Default latency | 1.0 s; latency curve at 0, 0.25, 0.5, 1, 2, 5, 10 s |

## Fills and costs (backtest.py, costs.py, docs/research/fees.md)

| Item | Value |
|---|---|
| Fill time | decision stamp + latency |
| Fill price | as-of last trade at or before fill time, +0.5 cent for a buy, -0.5 cent for a sell (`HALF_SPREAD`, trades-only history); as-of bid/ask when a book exists |
| polymarket.com traded | lower bound: entry quotes shifted earlier by D p90 = 2.879 s, exit unshifted; upper bound: no shift. Both reported. |
| Kalshi traded | unshifted |
| Kalshi fee, primary | Webull $0.02 per contract per fill |
| Kalshi fee, comparison line | 0.07 x C x P x (1 - P), rounded up to the cent per order |
| polymarket.com fee | 0.05 x C x P x (1 - P), rounded up per order; fee venue to confirm (polymarket.com vs Polymarket US) |
| Fee dates | current schedules (Kalshi 2026-07-07, Polymarket 2026-07-10) applied to all games: "costs as if traded today" |

## D (match-to-block delay)

median +2.119 s, p90 +2.879 s from 603 non-sports polymarket.com trades, 2026-10-03 04:11 to 04:21 UTC (experiments/d_estimate.json). Frozen for the training analysis; a later re-measurement is reported next to it, not substituted.

## Needs Alden's confirmation

Every value above, in particular: the 3 s median, jump 3c / 10 s, cover 0.8, entry 2c / exit 1c / timeout 60 s, half-spread 0.5c, latency grid.
