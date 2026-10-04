# IDEA 2, polymarket.com sub-second lead. POST-HOC, EXPLORATORY (formed after seeing the holdout)

Everything here was formed after the holdout results were seen. It is exploratory and confirms nothing.
It does not touch the pre-registered holdout run (RUN_COMMIT 872ff43) or its outputs.

## RULE

- Use VENUE timestamps on both feeds (not receipt time). 100 ms grid, mid only when both sides exist. Per game: cross-correlation of mid changes, lags -3.0 to +3.0 s. Report the lag distribution and the placebo (same-machine unrelated games), like the lead test.
- Trade rule (fixed now, run once): when polymarket.com mid moves >= 3 c within 500 ms (venue time) and Kalshi mid has moved < 1 c in the same direction, buy (or sell) Kalshi at the quote in the first Kalshi snapshot received at or after (polymarket.com venue time + receipt delay of that message + L), L in {0.25, 0.5, 1.0} s. Exit after 30 s at the Kalshi quote then (cross the spread). Kalshi direct fees both legs, also Webull. 10 contracts, size capped at displayed size.
- Report per L: trades, mean net c/contract with game-bootstrap CI, share of games positive, per-trade Sharpe (not annualized), excluding top 5 games.
- Variant count: 3 trading variants (one per L) added to the DSR total; the lag test and its placebo are not trading variants.

## Implementation notes (not part of the rule; fixed before running)

Data and games
- Vultr recordings only: staleline/data/vultr/data/live/{kalshi,polymarket}/*/*.parquet. No Polymarket US data.
- Games (amended 03:41 ET, before any real-data run, on Divi's instruction via the orchestrator): windows are
  read ONLY from data/live/holdout_windows.csv (commit feadc99): rows with venue == polymarket, qualifying ==
  True and excluded_outage, excluded_no_rows, excluded_no_instrument all False; machine as named in the row; a
  row whose machine is not vultr is skipped and counted (currently 0; 88 usable rows, all vultr). Window per
  game = [window_start_ns, window_end_ns) from that file, applied to VENUE time (src_ts_ns). Kickoff T =
  kickoff_utc from data/live/holdout_candidates.csv. No re-qualification. Placebo order: games sorted by
  kickoff with a stable sort (ties keep the windows-file row order); this may differ from run_test's tie order.
- Instruments: holdout_mid.instruments(cand_row, maps) with data/live/holdout_candidates.csv and
  data/live/holdout_maps. Kalshi market = <ticker>-<HOME>, polymarket.com market = collector home token, so both
  prices are P(home).
- Kickoff cut: T = kickoff_utc of the game; venue times in [T - 2 min, T + 20 min] are excluded. (This is the
  fixed cut the brief asks for; it is not the run's book-wipe exclusion columns excl_lo_g / excl_hi_g.)
- Timestamps: src_ts_ns is the venue time (Kalshi message time; polymarket.com message "timestamp", ms
  resolution, stored as ns). recv_ns is the receipt time. Only book rows (kind bid / ask) are used; trade rows
  are ignored. A snapshot = the bid and ask rows sharing one receipt ts; its venue time is their src_ts_ns.
  Book rows with null src_ts_ns are dropped (counted and reported).

Venue-time grid
- Bin b = floor(src_ts_ns / 100 ms). Mid on the grid at bin b = mid of the last snapshot (by venue time, ties
  broken by receipt order) with venue time inside bin b, else carried from the previous bin. The mid is defined
  only when that snapshot has both sides; a one-sided snapshot makes the mid undefined until the next two-sided
  snapshot (same sentinel logic as xcorr_lead.mid_grid). Bins inside the kickoff cut are dropped and a change
  never spans the cut (xcorr_lead.mid_changes with the cut as exclude interval, in 100 ms bin units).

Lag test (description only, not a trading variant)
- Per game: exactly xcorr_lead.game_lag_mid but on the 100 ms venue-time grid: common range of the two grids
  intersected with the window, mid changes per bin, pairwise Pearson corr of Kalshi changes vs polymarket.com
  changes shifted by -lag, lags -30..+30 bins. Lag = the key with the maximal corr; tie-break = first maximal key
  in order from -30 upward (Python max over the dict in insertion order, as in game_lag_mid). Positive lag =
  Kalshi first. NaN if the range is shorter than 2 x 30 + 2 bins or every corr is NaN. Reported in seconds
  (bins / 10).
- Placebo: exactly holdout_mid.run_test pairing: games sorted by kickoff; game A pairs with the next qualifying
  game B on the same machine with kickoff within PLACEBO_KICKOFF_S = 1800 s of A; Kalshi of A vs polymarket.com
  of B over A's window and A's kickoff cut.
- Statistics as xcorr_lead.decide for description: median lag, share positive, share negative, placebo median,
  Mann-Whitney p (xcorr_lead.mann_whitney_p) real vs placebo. The decide "result" label is printed but is not
  a test of anything here.

Signal
- Evaluated at each polymarket.com snapshot with venue time s inside the window and outside the cut, and with
  s - 500 ms also outside the cut.
- dP = polymarket.com mid as of venue time s minus mid as of venue time s - 500 ms (as of = last snapshot with
  venue time <= that time; mid must be defined at both points). Signal if |dP| >= 0.03 (with 1e-9 tolerance).
- dK = Kalshi mid as of s minus Kalshi mid as of s - 500 ms, same as-of rule on Kalshi venue time; both must be
  defined. Kalshi "moved < 1 c in the same direction": dK x sign(dP) < 0.01.
- Causality: inputs use only snapshots with venue time <= the as-of time AND receipt time <= the receipt time
  of the triggering polymarket.com message (so nothing received later feeds the decision).
- Direction: dP > 0 -> buy Kalshi home; dP < 0 -> sell Kalshi home.

Execution
- Order time (receipt clock) = s + (recv_ns - src_ts_ns of the triggering message) + L = recv_ns of that
  message + L.
- Fill: the first Kalshi snapshot with recv_ns >= order time. Buy at its best ask, sell at its best bid. If that
  snapshot lacks the needed side, no trade (counted as "no quote"). Quantity = min(10, displayed size of that
  side in that snapshot).
- Exit: first Kalshi snapshot with recv_ns >= fill recv_ns + 30 s that has the needed side (a long sells at
  the bid, a short buys at the ask; crossing the spread), same quantity. No exit snapshot -> trade dropped and
  counted.
- Trades whose fill or exit receipt time falls inside the kickoff cut, or whose exit is after window_end_ns +
  60 s, are dropped and counted.
- One position at a time per game and per L: signals whose triggering message was received before the
  current position's exit receipt time are ignored.
- Gross c/contract: long (exit bid - entry ask) x 100; short (entry bid - exit ask) x 100.
- Fees: costs.fee(price, qty, side, "kalshi", route="direct") on each leg (0.07 x C x P x (1 - P) rounded up to
  the cent per order), converted to c/contract (x 100 / qty). Webull line: costs.fee(..., route="webull"),
  $0.02 per contract per leg (4 c/contract round trip). Kalshi direct is the primary line.

Reporting per L and fee line
- trades, games with trades, mean net c/contract, game-bootstrap 95% CI = laggard.game_bootstrap_ci on per-game
  sums and counts of net c/contract (2,000 draws, seed 20261003), share of games with positive per-game sum,
  per-trade Sharpe = mean / sd (ddof 1), not annualized; and the same mean and Sharpe after dropping the 5 games
  with the largest per-game sum of net c/contract.
- Variant count: 3 trading variants (L = 0.25, 0.5, 1.0) added to the DSR total.

## Disclosure: earlier read of the per-game results file

Read staleline/results/holdout/lead_polymarket.com_per_game.csv at about 03:31 to 03:32 ET (before the SPEC
commit 4ec43cc). Loaded the whole CSV with pandas. Printed: the header (all column names), value counts of
machine and of machine among qualifying rows, and for 5 rows the columns game_id, kickoff_utc, machine,
excl_lo_g, excl_hi_g, excl_source (excl columns shown partly). In a second step (src_ts_ns coverage check) the
whole CSV was loaded again and qualifying, game_id, window_start_ns, window_end_ns were used for 2 games; nothing
else was printed. Columns lag_s, n_changes_kalshi, n_changes_other, pin_start_g, reason, kalshi_rows, other_rows,
excluded_s were loaded in memory but never printed or looked at. The lag values were not seen in this session
(the holdout lead result itself was known to the project before this idea was formed). The script no longer
reads that file.

## Timestamp resolution, measured before the real-data run

Measured by the orchestrator at 03:37 ET on Vultr Oct 3 ET books (src_ts_ns, all markets pooled):
- Kalshi: 21,975,575 rows with venue ts; smallest nonzero gap between consecutive distinct venue timestamps
  1.000 ms; median gap 3.0 ms; share with nonzero sub-second part 0.9985; share ending in .000 (whole second)
  0.0015.
- polymarket.com: 8,677,780 rows with venue ts; smallest nonzero gap 1.000 ms; median gap 10.0 ms; share with
  nonzero sub-second part 0.9971; share ending in .000 0.0029.
- About 75% of values have nonzero sub-millisecond digits, consistent with float64 rounding when millisecond
  times are converted to ns (spacing about 256 ns at 1.76e18), so the effective resolution is taken as 1 ms.
  A venue time exactly on a 100 ms boundary can therefore land one bin early; negligible.
- Gate rule: if either venue is coarser than 100 ms, or more than 50% of its timestamps are whole seconds, the
  lag test is reported "not testable at 100 ms" and the trade rule is not run. Gate result: passes on both
  venues; the lag test and the trade rule run.
- Own check (2 games, before the SPEC commit): src_ts_ns is present on every Kalshi and polymarket.com book row
  (Kalshi nulls are trade rows only). Receipt delay recv_ns - src_ts_ns: Kalshi median about 29 ms (99th pct
  about 0.11 s); polymarket.com median about 52 ms, 99th pct 6 to 16 s.
