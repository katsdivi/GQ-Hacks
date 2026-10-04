# IDEA 3, Kalshi reversal after large taker trades. POST-HOC, EXPLORATORY (formed after seeing the holdout)

Everything here was formed after the holdout results were seen. It is exploratory and confirms nothing.
It does not touch the pre-registered holdout run (RUN_COMMIT 872ff43) or its outputs.

## RULE

- Signal: a Kalshi trade print of size >= 95th percentile of that market's trade sizes in the window, moving the mid >= 2 c. Fade it: at receipt t + L (L in {0.25, 0.5, 1.0} s) take the opposite side at the quote, exit after 10 s at the quote. Kalshi direct fees both legs. Report as idea 2 (per L: trades, mean net c/contract with game-bootstrap CI, share of games positive, per-trade Sharpe (not annualized), excluding top 5 games).
- Variant count: 3 (one per L) added to the DSR total.

## Implementation notes (not part of the rule; fixed before running)

Data and games
- Vultr recordings only: staleline/data/vultr/data/live/kalshi/*/*.parquet. No Polymarket US data, no
  polymarket.com data.
- Games: read ONLY from data/live/holdout_windows.csv (commit feadc99): rows with qualifying == True and
  excluded_outage, excluded_no_rows, excluded_no_instrument all False. A row whose machine is not vultr is
  skipped and counted. Dedupe: a game_id appearing under both venues is kept once, using the polymarket row
  (same as idea 1); window = [window_start_ns, window_end_ns) of that row. Kickoff T = kickoff_utc from
  staleline/data/live/holdout_candidates.csv. A game whose kalshi_ticker is not in the Vultr
  kalshi_events.json is skipped and counted (as idea 1).
- Markets per game: both Kalshi team markets <ticker>-<HOME> and <ticker>-<AWAY> (kalshi_events.json gives
  [away, home, ...]). Each market is handled on its own (its own trade prints, own percentile, own book), and
  the position is taken in the market of the print. All prices are used in stored P(home) terms: the away
  market is already flipped at ingest (price 1 - p, bid/ask swapped with sizes, taker side buy/sell swapped),
  so "buy home" = pay the stored ask (stored ask size), "sell home" = hit the stored bid (stored bid size) in
  either market. This is exactly own_ask = 1 - stored bid etc. on the away market. Fees are symmetric in P,
  so computing them on the stored price equals computing them on the own-market price.
- Kickoff cut: venue times in [T - 2 min, T + 20 min] are excluded.

Trade prints and the percentile
- Trade rows: kind == trade. ts = Kalshi created_time (venue time); recv_ns = receipt time. Kalshi trade rows
  arrive via a REST poll triggered by the websocket trade message, so recv_ns is about 1 s after ts (measured
  on one file before this SPEC: median 1.08 s, 90th pct 1.7 s). src_ts_ns is null on trade rows.
- In-window prints of a market: trade rows with ts in [window_start_ns, window_end_ns) and ts outside the
  kickoff cut.
- The 95th percentile is computed over the market's in-window trade sizes (numpy percentile, linear
  interpolation), over the WHOLE game window. This uses future trade sizes, i.e. there is a lookahead in the
  threshold. This is a property of the given rule and is kept as stated; the rule is not changed. Nothing
  else that feeds a signal uses data received after the decision time. A market with fewer than 20 in-window
  prints gets no signals (counted).
- Trade row dedupe (rows can repeat across parquet files / REST re-polls): key (market_id, ts, price, size,
  side), keeping the earliest recv_ns. Book rows: key (market_id, recv_ns, kind), keep last.
- Candidate prints: in-window prints with size >= that percentile (1e-9 tolerance) and side in {buy, sell}
  (unknown side skipped, counted).

Mid and "moving the mid >= 2 c"
- Book snapshot = the bid and ask rows of one market sharing one recv_ns; its venue time = their src_ts_ns.
  Mid = (stored bid + stored ask) / 2 in P(home) terms, defined only when the snapshot has both sides. Book
  rows with null src_ts_ns are dropped (counted).
- Because the print's receipt time is a poll time about 1 to 2 s after the trade, receipt order between book
  and print is not meaningful, so before / after the print is decided on VENUE time. THIS DEVIATES from the
  brief's receipt-order wording ("first snapshot received after the print minus last received at or before");
  reason: measured trade recv_ns - ts median 1.08 s, 90th pct 1.7 s (one file), and median 2.02 s, 90th pct
  4.87 s, 99th pct 16.2 s (one market, KXNCAAFGAME-26OCT03ALAMSST-MSST, all of Oct 3 ET), so receipt order
  between prints and books does not reflect event order and the receipt-order version would compare two
  post-trade books.
- Millisecond tie rule. Book src_ts_ns is Kalshi ts_ms x 1e6 (millisecond resolution, with float64 rounding,
  e.g. ...689999872); trade ts is created_time with microseconds (99.9% have a nonzero sub-ms part). Measured
  before this SPEC on the same market (3,000 prints, every 10th): the nearest book snapshot to a print has
  offset src_ts_ns - ts with 25th / 50th / 75th pct -0.79 / -0.49 / -0.16 ms, i.e. the trade's own book
  delta carries the truncated millisecond and lands 0 to 1 ms BEFORE the print ts. So: print_ms =
  floor(ts / 1e6); book_ms = round(src_ts_ns / 1e6). mid_before = mid of the last snapshot of the print's
  market with book_ms < print_ms (strictly earlier millisecond); mid_after = mid of the first snapshot with
  book_ms >= print_ms (ordered by book_ms, ties by recv_ns). Both snapshots must have been RECEIVED at or
  before t = recv_ns of the print, else no signal (counted as "post-print book not yet received"); this keeps
  the signal causal. Both mids must be defined.
- Print direction d = +1 if side == buy (aggressor bought home exposure), -1 if sell. Signal if
  d x (mid_after - mid_before) >= 0.02 (1e-9 tolerance).
- Decision time t = recv_ns of the print (receipt time).

Execution
- Fade = trade opposite to the print's aggressor direction in home terms: d = +1 -> sell home (hit the stored
  bid), d = -1 -> buy home (pay the stored ask).
- Fill: the first snapshot of the print's market with recv_ns >= t + L (no quote received before t + L is
  used). Price = its stored ask to buy, stored bid to sell. If that snapshot lacks the needed side: no trade
  (counted "no quote"). Quantity = min(10, displayed size of that side in that snapshot).
- Exit: the first snapshot of the same market with recv_ns >= fill recv_ns + 10 s that has the needed side;
  crossing the spread: a short buys back at the stored ask, a long sells at the stored bid; same quantity. No
  such snapshot within the loaded data -> trade dropped and counted.
- Trades whose fill or exit snapshot RECEIPT time falls inside the kickoff cut, or whose
  exit receipt time is after window_end_ns + 60 s, are dropped and counted.
- One position at a time per game and per L (across both markets of the game): candidate prints are processed
  in order of t; a print with t < the exit receipt time of the open position is ignored.
- Gross c/contract: long (exit bid - entry ask) x 100; short (entry bid - exit ask) x 100.
- Fees: costs.fee(price, qty, side, "kalshi", route="direct") on each leg (0.07 x C x P x (1 - P) rounded up to
  the cent per order), converted to c/contract (x 100 / qty). Net = gross - entry fee - exit fee.

Reporting per L
- trades, games with trades, mean net c/contract, game-bootstrap 95% CI = laggard.game_bootstrap_ci on
  per-game sums and counts of net c/contract (2,000 draws, seed 20261003) over games with at least one trade,
  share of those games with positive per-game sum, per-trade Sharpe = mean / sd (ddof 1), not annualized; and
  the same mean and Sharpe after dropping the 5 games with the largest per-game sum of net c/contract. Also
  mean gross c/contract and skip counts. Also the distribution of recv_ns - ts for fired signals (traded
  prints) and the count of traded prints with recv_ns - ts > 5 s. Late prints are NOT capped (t = receipt
  time is the rule). The 20-print minimum per market is an implementation choice fixed here and will not be
  tuned. No interpretation.
- Variant count: 3 trading variants (L = 0.25, 0.5, 1.0) added to the DSR total.

## Read disclosure

Read results/holdout/lead_*_per_game.csv at (never) ET; columns used: none; not read.

## INVALID, LOOKAHEAD (note added 2026-10-04 03:49 ET)

On Divi's instruction (via the orchestrator, after the run), a 95th-percentile size threshold computed over the whole game window uses future trade sizes; that is lookahead and is not allowed. The idea 3 run (script d13e473, 03:48:12 to 03:48:40 ET, results commit a7b1dd8) used exactly that threshold, so ALL idea 3 outputs (idea3_results.csv, idea3_trades.csv, idea3_RESULTS.md) are INVALID, LOOKAHEAD. Per the instruction it is NOT rerun (no corrected threshold, no second run). It still counts as 3 variants (one per L) in the DSR total.

