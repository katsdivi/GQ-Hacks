# Post-hoc T&S laggard test (EXPLORATORY, selected after seeing the holdout)

Written 2026-10-04 03:32 ET, before any test code exists and before any test code touches real data.
Branch t17-extras. Code under test is identical to the run's commit 872ff43 (laggard.py, strategy.py, leadlag.py,
xcorr_lead.py, holdout_mid.py, costs.py). This test was chosen after the holdout results were seen. It is not
confirmatory and does not change any pre-registered result.

## RULE

Rule:
- Universe: the 39 Polymarket US laggard games covered by 20261003-time-and-sales.csv (venue time before 17:00 ET Oct 3), lead-test windows with the kickoff cut.
- Polymarket US price at time t = last T&S trade price with venue "Transaction Time" <= t. No polled quotes are used anywhere.
- Signal: unchanged pre-registered laggard rule (Kalshi mid jump >= 4 c within 10 s; Polymarket US price, defined above, lags Kalshi's new mid by >= 3 c in the same direction at decision time; 60 s timeout; trading end per v2 A5).
- Entry: at decision + L (venue time), fill at the price of the first T&S trade with venue time >= decision + L, plus 1 c if buying, minus 1 c if selling, capped to [0.01, 0.99]. Skip if no trade within 60 s.
- Exit: on timeout or when the gap closes (pre-registered exit), fill at the first T&S trade at or after the exit time, minus 1 c if selling, plus 1 c if buying.
- Fees: Polymarket US taker 0.0695 x C x P(1-P), banker's rounding to the cent, entry and exit. 10 contracts.
- Latencies L: 1, 2, 5 s. Primary: L = 1 s. No other variants.
- Report: trades, mean net c/contract with game-bootstrap 95% CI (same seed as the run), share of games positive, per-game Sharpe (mean/sd of per-game P&L, not annualized), excluding top 5 games, skips by reason.
- Variant count: this adds 3 variants to the DSR total.

## Implementation notes (not part of the rule; fixed before running)

Paths: "staleline" = /Users/divyamkataria/GQ HACKS/staleline (read-only). T&S file =
/private/tmp/claude-501/-Users-divyamkataria-GQ-HACKS/4b6ada3b-5914-4e79-b685-97dc6f2dd657/scratchpad/pmus_tns/20261003-time-and-sales.csv
(280,153,445 bytes; columns Transaction Time, Symbol, Last Price, Last Quantity; Symbol = Polymarket US slug).
Coverage end C = 2026-10-03 17:00:00.000000000 ET (21:00:00 UTC); the file's prints run from
2026-10-02 17:00:00.09 ET to 2026-10-03 16:59:59.998 ET.

(a) Universe. Games: rows of staleline/results/holdout/lead_Polymarket US_per_game.csv with qualifying == True
and window_start_ns < C. Metadata check (no test code; per-game CSV, map and a slug count only): this gives
57 games, all on machine vultr, all with a Polymarket US slug present in the T&S file. The "39" in the rule is
the prior diagnostic's count of games WITH run fills before 17:00 ET at 1 s (604 fills, 39 games; the other 18
of the 57 had no run fill before 17:00 ET); it is an outcome, not a selection rule. This test uses all 57
games. The number of games with T&S trades is reported and is expected to differ from 39 because the signal
set changes when the follower price changes. Decisions: within each game only round trips whose entry decision
time is < C and whose entry fill trade and exit fill trade both have venue time < C are in the test. A round
trip outside that (decision at or after C, or a needed fill trade not found before C) is "outside coverage":
counted and reported separately, NOT a skip. A no-trade search whose 60 s window ends at or after C without a
trade before C is also "outside coverage".

(b) Kalshi side. Same recorded books, same machine (column machine; vultr for all 57), same calls as
scripts/final_test_run.py laggard() and scripts/holdout_diag.py part_g: holdout_mid.Machine("vultr",
staleline/data/vultr, staleline/data/vultr/GAPS_vultr.md, staleline/data/vultr/heartbeats) (and the "mac"
Machine with root staleline, staleline/data/mac/GAPS_mac.md, staleline/data/mac/heartbeats, defined but
unused); maps staleline/data/live/holdout_maps (holdout_mid.load_maps); candidates
staleline/data/live/holdout_candidates.csv; instrument from holdout_mid.instruments (Kalshi home market);
Kalshi rows from final_test_run.rows_with_size(m, "kalshi", ticker, lo - 3600 s, hi + 120 s), lo =
window_start_ns, hi = laggard.trading_end_ns(kickoff, pin_start_g) (NaN pin -> None). Kalshi mid grid via
the unchanged laggard.signals -> laggard._grid -> xcorr_lead.mid_snapshots / mid_grid. Clock basis: Kalshi ts
is vultr receipt time; T&S Transaction Time is the venue clock. No clock correction is applied.

(c) T&S into the unchanged signal code. A synthetic follower tick table is built per game: for every T&S print
of the slug (ALL prints in the file, see (h)), two rows with ts = the print's venue time (UTC ns), venue
"polymarket_us", market_id = slug, kind "bid" and "ask", price = home-oriented print price (see (d)). So
bid = ask = last print and the Amendment 2 mid equals the last trade price. laggard.signals(kt, synthetic,
"polymarket_us", lo, hi, exclude=[(excl_lo_g, excl_hi_g)], outages=outs) is called unchanged with SETTING
unchanged. Prints at the same ns: file order is kept (stable sort by ts); the grid takes the last print of a
second (mid_grid groupby last; pivot aggfunc "last" for same-ns rows). Grid label g = last print with venue
time < (g + 1) s, i.e. before the decision instant (g + 1) s; a print at exactly (g + 1) s belongs to label
g + 1. Breaks, kept exactly as the run's code: the kickoff cut (excl_lo_g, excl_hi_g from the per-game CSV)
and outages = GAPS rows of the frozen GAPS file of that machine with venue in {"kalshi", "all"} overlapping
[lo, hi) (holdout_mid.Machine.gaps, which also adds the Kalshi REST-connected spans from the heartbeats). The
run also passed "polymarket_us" GAPS rows; those are outages of our poller, not of the venue's trades, so they
do not apply to T&S and are not passed (GAPS_vultr.md has no polymarket_us rows anyway: 42 kalshi_ws,
82 polymarket, 2 all). Exception to "last trade <= t", inherited unchanged from laggard._grid: inside a break
the follower price is undefined, and after a break it stays undefined until the first T&S print after the
break ends (no carry across a break). laggard._grid also carries the last print forward to the window end;
any decision this produces at or after C is outside coverage by (a).
Fills: T&S fills are taken even if the fill time falls inside a break or at or after the trading end hi (the
run's quote_at "break" and "after window end" skips are book-quote rules and are not applied); the only skip
reasons are "no entry trade within 60 s" and "no exit trade within 60 s".

(d) Price orientation. T&S Last Price is the price of the slug's LONG instrument. long_is_away is read per slug
from staleline/data/live/holdout_maps/polymarket_us_map.json (the map holdout_mid.instruments uses); the
metadata check gives long_is_away = True for all 57 slugs. Home price = 1 - Last Price if long_is_away, else
Last Price, rounded to 4 decimals (prints are on a 0.001 grid; some are sub-cent and are used as is).
Direction +1 = buy home at home price, -1 = sell home. If any slug has long_is_away missing, the script stops.

(e) Venue time parsing. Transaction Time strings are ISO 8601 with 3 to 9 fractional digits and offset
-04:00 (all 208,124 universe prints carry -04:00). Parsed with integer arithmetic only: seconds part to UTC
seconds, fractional digits right-padded to 9 to ns, offset subtracted. No float and no pandas parsing of the
fraction. Any other offset or format stops the script.

(f) Timing. Decision time = (g + 1) s (strategy.decision_time_ns, entry_decision_ns from strategy.signals).
Entry time = decision + L. Exit time = the pre-registered exit decision time (exit_decision_ns from
strategy.signals: gap closed, timeout, or window end). Exit time does not add L (the rule says fill at the
first trade at or after the exit time). Entry fill = first print (file order at equal ns) with venue time in
[t_entry, t_entry + 60 s] (inclusive); exit fill = first print with venue time in [t_exit, t_exit + 60 s]
(inclusive). No print in the interval -> skip with reason "no entry trade within 60 s" / "no exit trade within
60 s" (a skipped exit skips the whole round trip), unless the interval reaches C, see (a). The +/- 1 c is applied
to the home-oriented print price before the [0.01, 0.99] cap, on both legs: buy = min(p + 0.01, 0.99),
sell = max(p - 0.01, 0.01). Fees: costs.fee(fill, 10, side, "polymarket_us", ts = fill print venue time ns),
on the capped fill price. P&L dollars = direction x (exit fill - entry fill) x 10 - fee_entry - fee_exit
(as laggard.fill_trades); net c/contract = P&L x 100 / 10. Signals do not depend on L; one signal set per game,
the three latencies only change fills. Kalshi mid at decision and T&S price at decision in trades.csv are gk[g]
and go[g] from the same laggard._grid calls as the signal (go[g] = last print before (g + 1) s); the entry and
exit print venue times and prices are also listed.

(g) Statistics, per L, over filled round trips in the test. Mean net c/contract = mean over trades. CI =
laggard.game_bootstrap_ci(per-game sum of net c/contract, per-game trade count) over games with >= 1 trade
(2,000 draws, seed 20261003), as laggard.latency_curve. Per-game P&L in dollars (sum of round trip P&L). Share
of games positive = share of games with trades whose per-game P&L > 0. Per-game Sharpe = mean / sd (ddof 1) of
per-game P&L over games with trades, not annualized. Excluding top 5 = drop the 5 games with the largest
per-game P&L (pandas nlargest(5)), mean net c/contract of the remaining trades; as holdout_diag.part_x.
Skips by reason and outside-coverage counts are reported per L. Sample: 5 filled L = 1 s trades by
DataFrame.sample(5, random_state=20261003). Comparison: the run's laggard_trades.csv rows with venue
polymarket_us, latency_s 1.0, filled, exit_fill_ns < C on the same 57 games (604 fills, 39 games).

(h) Data source. The T&S file above, read once; all prints of each universe slug in the file are used (not only
in-window prints), so the last print <= t is correct at window start. Exact duplicate rows (5,479 among
universe prints) and same-ns prints (87,290 share a time and slug with another print) are kept: they are
separate fills. No raw T&S prints are written to the repo; only our simulated round trips.
