# IDEA 1, Kalshi complement lag. POST-HOC, EXPLORATORY (formed after seeing the holdout)

Everything in this file and in every idea1 output is post-hoc and exploratory. The idea was formed after the
holdout results were seen. It is not part of the pre-registered plan and is not a confirmatory test.

## RULE

- At every Kalshi book update (receipt time t) for either team: buy-both-YES opportunity if best_ask_home + best_ask_away + fee(ask_home) + fee(ask_away) < 1.00; buy-both-NO opportunity if (1 - best_bid_home) + (1 - best_bid_away) + fees < 1.00. Fee = Kalshi direct taker 0.07 x C x P(1-P) rounded up to the cent per order (primary); also report Webull $0.02/contract/leg.
- Execution: latency L in {0.25, 0.5, 1.0} s. Each leg fills at its quote in the first snapshot received at or after t + L, size = min(10, displayed size at that quote) on both legs (equal size). Execute only if the sum still clears at t + L on both legs; otherwise record "missed". If one leg's size < the other's, the excess is unwound at the worse side's next quote and the loss counted.
- One position per game at a time; hold to settlement (no early exit).
- Report per L: opportunities seen, executed, missed, contracts, net P&L with game-bootstrap CI, per-trade mean and sd, per-trade Sharpe (mean/sd, not annualized), games with >= 1 executed trade, size distribution, opportunity duration distribution (how long the sum stayed below 1).
- Variant count: 3 (one per L) added to the DSR total.

## Implementation notes (not part of the rule; fixed before running)

Data and games
- Data: Vultr recordings only, `staleline/data/vultr/data/live/kalshi/*/*.parquet`, rows with kind in {bid, ask}.
  Trade rows are ignored. No Polymarket or Polymarket US data is used.
- Games: every row of `results/holdout/lead_polymarket.com_per_game.csv` with machine == vultr: 101 games
  (qualifying and non-qualifying for the lead test alike; every one has a window). The Polymarket US per-game
  file has 95 vultr games, all a subset of these 101, with the same window_start_ns but window_end_ns equal in
  only 45% of them, so the polymarket.com file's window [window_start_ns, window_end_ns) is used for all 101.
- Tickers: event ticker = `kalshi_ticker` in `data/live/holdout_candidates.csv`; team codes from
  `data/vultr/data/live/kalshi_events.json` as [away, home, sep] (the collector's own orientation source).
  Home market = `<event>-<home>`, away market = `<event>-<away>`. Cross-check done before writing this: for all
  101 games the events.json home code equals the game_id's last token (the `holdout_mid.instruments` home); 0
  mismatches.

Price orientation (verified)
- Stored prices are P(home wins). `collector/run.py` `top_rows` flips the away market: stored home-terms
  bid = 1 - own ask (stored size = own ask size), stored ask = 1 - own bid (stored size = own bid size). Data
  check (read-only, before writing this): on the IND at RUTG event both team markets are stored near
  0.05 / 0.06, i.e. both in RUTG (home) terms. On 4 games, time-aligned own_ask_home + own_ask_away has a
  median of 1.01 to 1.02 and the NO sum (1 - own_bid_home) + (1 - own_bid_away) a median of 1.01 to 1.03,
  consistent with the de-flip below. (The same check showed lower tails of the YES sum well below 1 on 2 of the
  4 games over the full recording, not restricted to windows; noted, not investigated.)
- Own quotes. Home market: own_bid = stored bid, own_ask = stored ask, sizes as stored. Away market:
  own_ask = 1 - stored bid with size = stored bid size; own_bid = 1 - stored ask with size = stored ask size.
- YES leg price = own_ask, size available = own ask size. NO leg price = 1 - own_bid (Kalshi NO ask),
  size available = own bid size.

Snapshots and book state
- A snapshot of a market = all bid/ask rows of that market with the same `recv_ns` (for book rows ts equals
  recv_ns in all but about 4 rows per game; recv_ns is used). The collector writes a snapshot only when the top
  of book changes, and drops a side that is empty; a snapshot without a side means that side is empty (NaN).
- Book state of a market at time t = its last snapshot with recv_ns <= t. Rows from 6 h before window_start
  are loaded to seed the state. No staleness limit.
- Signal (decision at t): uses only snapshots with recv_ns <= t. Evaluated at every distinct recv_ns of either
  team market with t in [window_start, window_end). Both markets must have a state with the needed sides.
- Kickoff cut: T = ESPN kickoff (`kickoff_utc`). An update with t in [T - 2 min, T + 20 min] counts as
  non-clearing: it ends a run and cannot start one.

Clearing test and fees
- Computed in exact decimals, strict inequality. Opportunity test (at t and the re-check at t + L) uses
  C = 10 per leg: YES: 10 x (pa_h + pa_a) + fee(pa_h, 10) + fee(pa_a, 10) < 10.00; NO: same with prices
  1 - own_bid_h and 1 - own_bid_a. fee = `costs.fee(p, C, side, "kalshi", route="direct")` (0.07 x C x P x
  (1 - P), rounded up to the cent per order) for the primary line, route="webull" ($0.02 x C) for the second.
- The whole simulation is run separately per fee schedule (opportunities, attempts and fills depend on the
  fee used in the test): 3 L x 2 schedules = 6 runs. Variant count stays 3.
- If both YES and NO clear at the same update, YES is taken (attempted) and both are counted as opportunities.
  YES and NO runs are tracked separately; an attempt happens at the first update of a run of either kind.
- P&L fees use the actually filled (possibly fractional) quantity per order.

Opportunity, attempt, execution
- Opportunity = a maximal run of consecutive signal updates (per game, per direction YES or NO) where the sum
  clears. Opportunities seen = number of runs. Duration = recv time of the first non-clearing update minus
  recv time of the first clearing update; a run still open at window_end is censored at window_end (flagged).
- An attempt is made at the first update of each run while no position is held in that game.
- Fill: for each leg, the first snapshot of that leg's market with recv_ns >= t + L (literal reading of the
  rule: because snapshots are change-only, this is the next book change at or after t + L, which can be well
  after t + L; no cap, but the fill snapshot must have recv_ns < window_end, else missed). The fill-delay
  distribution (fill recv minus (t + L)) is reported per L. At those two snapshots the clearing test (C = 10)
  is re-run on the fill quotes; if it fails or a needed side is empty: missed.
- Size: leg i fills q_i = min(10, displayed size at its fill quote). Paired size q = min(q_h, q_a). If
  q_h != q_a, the excess e = |q_h - q_a| on the larger leg is sold at that market's next quote: the first
  snapshot of that market with recv_ns strictly after that leg's fill snapshot having the needed side (YES
  excess sold at own_bid; NO excess sold at 1 - own_ask, the NO bid). If no such snapshot exists in the loaded
  data, the excess is held to settlement.
- "One position per game at a time" with hold to settlement means at most one executed position per game for
  the whole window. After a missed attempt, later runs may attempt again.

Payout and P&L
- Settlement from `data/holdout_raw/settlements.csv` (settlement_value_dollars per team market). Both-YES
  payout = q x (sv_home + sv_away); both-NO payout = q x (2 - sv_home - sv_away) (covers ties or scalar
  results). Per position net P&L = payout - q_h x price_h - q_a x price_a - entry fees(q_h) - entry fees(q_a)
  + (excess sale proceeds - excess sale fee). Excess held to settlement pays its own settlement value.
- A game with no finalized settlement rows for both markets (1 of the 101 has no rows): its executed positions
  are counted in executed / contracts but excluded from P&L and listed separately.

Statistics
- Per run (L, schedule): opportunities seen (YES, NO), attempts, executed, missed, contracts (sum of paired q),
  net P&L total, per-trade mean, sd, Sharpe = mean / sd (not annualized), games with >= 1 executed trade,
  paired-size distribution (min, quartiles, max), opportunity duration distribution (quartiles, p90, max),
  fill-delay distribution.
- Bootstrap: game-level resampling over all 101 games (games with no position contribute 0 P&L and no trades),
  2,000 draws, numpy default_rng(20261003), percentile 95% CI of total net P&L and of the per-trade mean.
- One run on real data. No code or parameter changes after seeing output.
