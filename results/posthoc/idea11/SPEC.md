# Post-hoc Idea 11: (a) Kalshi vs polymarket.com lag diagnostics at fine resolution; (b) cross-venue arbitrage measurement

Label: post-hoc, exploratory (formed after the holdout was seen). Committed before any real-data code runs.

Data: Vultr Oct 3 books only. Windows ONLY from data/live/holdout_windows.csv (feadc99): qualifying = True, no
exclusion flags, polymarket.com rows.

## Spec (verbatim)

General:
- Book levels with 0 < size < 0.01 contracts are treated as floating-point residue and removed on both venues before anything else (Kalshi minimum granularity is 0.01). Report how many levels were removed per venue.
- Mid = (best bid + best ask)/2, defined only when both sides exist; never filled across an empty side.
- Kickoff cut [kickoff - 2 min, kickoff + 20 min] excluded on both venues.

(a) Lag diagnostics (descriptive, not variants):
- a1. Receipt-time test: build mids on the Vultr RECEIPT clock on a 10 ms grid; per-game cross-correlation of mid changes, lags -1.0 to +1.0 s; per-game lag = argmax. Same for unrelated-game placebo pairs (Design 1, same machine). Report median lag, distribution of per-game lags (histogram, 10 ms bins), share > 0, Mann-Whitney real vs placebo.
- a2. Venue-time test: identical but on venue timestamps.
- a3. Offset signature: report the standard deviation and IQR of per-game lags in a1 and a2. State in the results the pre-fixed reading rule: if a2 per-game lags have IQR <= 10 ms and a1 per-game lags do not show the same positive median, the venue-time result is read as a timestamp offset; if a1 median lag >= +30 ms with share > 0 >= 0.6, it is read as a receipt-side lead of that size; otherwise inconclusive.
- a4. Receipt minus venue delay per venue (median, p10, p90), as the clock-offset bound.

(b) Cross-venue arbitrage measurement (labeled "market-efficiency measurement; polymarket.com is not available to US persons; not a strategy available to the authors"):
- An opportunity exists at receipt time t if, for some team X: Kalshi best ask for YES X + polymarket.com best ask for the token of the OTHER team + Kalshi direct taker fee per contract (0.07 x P(1-P), rounded up to the cent for a 10-contract order, divided by 10) + polymarket.com taker fee per contract (0.05 x P(1-P)) < 1.00. Both books must be live at t.
- Report: number of opportunities, median and p90 duration, share lasting >= 0.25, 0.5, 1.0, 2.0 s, median executable size = min of displayed sizes on both legs.
- Executability at L in {0.25, 0.5, 1.0} s (3 variants): Kalshi leg fills against the Kalshi book received at or after t + L; polymarket.com leg fills against the polymarket.com book at or after t + L + that market's taker delay (1 s, from data/live/holdout_seconds_delay.csv). Size = min(10, displayed size on each leg at its fill time), SAME size on both legs. Executed only if the sum still clears at both fill times; else "missed". Hold both to settlement.
- Settlement check: for every game with an executed opportunity, confirm both venues settled the game the same way; any disagreement listed with game id.
- P&L per L: total and per contract, game-bootstrap 95% CI (2,000 reps, seed 20261004), excluding top 5 games.

## Implementation notes (fixed before any real-data run)

1. Windows file: `git show feadc99:data/live/holdout_windows.csv`, sha256
   d66c96bca8b1a91c44e30d907bd6b863244a97f9a871abb6a18d6ec74268441d (identical on posthoc-latency). Rows: venue =
   "polymarket" (polymarket.com), qualifying = True, excluded_outage, excluded_no_rows, excluded_no_instrument and
   not_qualifying_mid_changes all False, machine = vultr. Window = [window_start_ns, window_end_ns). Kickoff =
   kickoff_utc of data/live/holdout_candidates.csv (same as Idea 2 on posthoc-latency).
2. Book files: data/vultr/data/live/{kalshi,polymarket}/2026100*/*.parquet (the Vultr recordings, as Idea 2).
   Receipt clock = `recv_ns` (Vultr receive time, ns); venue clock = `src_ts_ns` (venue timestamp). Book rows
   with null `src_ts_ns` are dropped from the venue-time test only, and counted.
3. The recorded books are top of book only (one `bid` row and one `ask` row per snapshot), stored as P(home)
   (away-team instruments flipped at ingest, bid/ask swapped). Residue rule on top of book: a best level with
   0 < size < 0.01 is removed, so that side is EMPTY at that snapshot (the next level is not recorded); the mid
   is then undefined and that leg is not live. Counts of removed levels reported per venue.
4. Instruments: Kalshi home market (`<event>-<home code>`) and away market (`<event>-<away code>`);
   polymarket.com home token (`collector_home_token` in data/live/holdout_maps/polymarket_com_map.json; the two
   tokens of a polymarket.com market share one book, so the other team's ask = 1 - home token bid). The lag test
   uses the Kalshi home market and the polymarket.com home token (holdout_mid.instruments), both P(home).
5. Lag grid (a1, a2): bin = clock // 10 ms; value = mid of the last snapshot in or before the bin (ties by
   receipt order), forward filled; a one-sided snapshot makes the mid undefined until the next two-sided one.
   Changes via xcorr_lead.mid_changes with the kickoff cut as the excluded interval (bins inside dropped, no
   change spans the cut). Pearson correlation of changes, pairwise over bins where both are defined, for lags
   -100 to +100 bins; lag = first maximal lag scanning from -1.0 s upward. Positive lag = Kalshi first
   (Kalshi change at t correlates with polymarket.com change at t + lag), the repo convention. Placebo, Design 1
   (holdout_mid.run_test, same machine): Kalshi of game A vs polymarket.com of the next qualifying game B by
   kickoff with kickoff within 30 min of A, in A's window and A's kickoff cut. Mann-Whitney two-sided
   (scipy.stats.mannwhitneyu), real vs placebo per-game lags. A "receipt-side lead" in a3 means Kalshi first.
6. a4: per book snapshot inside the windows (kickoff cut excluded), recv_ns - src_ts_ns, per venue, in ms.
7. Arbitrage state, in P(home) terms. X = home: Kalshi YES home ask = Kalshi home market ask; polymarket.com
   away-token ask = 1 - polymarket.com bid. X = away: Kalshi YES away ask = 1 - (stored P(home) bid of the Kalshi
   away market); polymarket.com home-token ask = polymarket.com ask. Displayed sizes = the size of that stored
   row. Fees per contract as in the spec, with P = that leg's own price (Kalshi: strategy_a.fee_kalshi_direct at
   qty 10, divided by 10; polymarket.com: 0.05 x P x (1 - P), unrounded).
8. "Live at t": for each of the two legs, the latest snapshot of that instrument received at or before t is
   inside the game window, outside the kickoff cut, and has the needed side (after the residue rule). State is
   evaluated at every receipt event of the three instruments.
9. One opportunity = a maximal run of receipt events for the same X where the condition holds; t = its first
   receipt time; duration = receipt time of the first event where it no longer holds (or the cut / window end)
   minus t. Every opportunity is tested for execution at each L (one attempt per opportunity per L).
10. Execution: Kalshi fill snapshot = first snapshot of the X market with recv_ns >= t + L; polymarket.com fill
    snapshot = first snapshot of the home token with recv_ns >= t + L + seconds_delay (seconds_delay from
    data/live/holdout_seconds_delay.csv by condition id; 1 s if absent, counted). Each leg must have its side at
    its fill snapshot. q = min(10, size_K, size_PM), same q on both legs. Executed iff
    priceK + pricePM + feeK(q)/q + feePM(q)/q < 1.00, fees for the actual order q (Kalshi rounded up to the cent
    per order); else "missed". P&L = q x (payoutK + payoutPM) - q x (priceK + pricePM) - feeK(q) - feePM(q).
11. Settlement: Kalshi from data/holdout_raw/settlements.csv (result of the X market); polymarket.com from the
    Gamma API (`gamma-api.polymarket.com/markets?condition_ids=<condition>`, outcomePrices, cached under
    data/pm_resolution/, gitignored) for the other team's token. Payouts computed from each venue's own result;
    "same way" = both venues name the same winner (or both 50/50). Disagreements listed.
12. P&L CI: game bootstrap of per-game P&L sums (2,000 reps, seed 20261004), reported as total and per
    contract; "excluding top 5" drops the 5 games with the largest P&L sum. Fee line: Kalshi direct only (per
    spec).
13. Outputs under results/posthoc_idea11/. No experiments/variants.csv rows yet (held for one later commit;
    3 variants, L in {0.25, 0.5, 1.0}).
