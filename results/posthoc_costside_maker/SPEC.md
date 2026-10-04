# Post-hoc maker / spread-capture search (costside-maker)

Label: post-hoc, exploratory; training only (kickoff before 2026-08-01); every trial counted; holdout not touched.
Written 2026-10-04 05:5x ET, committed before any real-data run. Fixed list: **36 trials** (32 grid + 4 walk-forward selectors).

## Data
- `data/raw/kalshi_only/<game_id>.parquet` (1,267 games, `data/raw/kalshi_only_games.csv`), settlement via
  `strategy_a.load_games` (home 1/0, tie 0.5, NaN void: skipped). Own-market YES price via `strategy_a.own_market_trades`.
  Trades only, no order book. Never read data/holdout_raw, data/live, data/vultr, results/holdout.

## Fees (cost lines, not trials)
- Taker: `strategy_a.fee_kalshi_direct` = 0.07*C*P*(1-P) rounded up to the cent per order (source: strategy_a.py).
- Maker: not confirmed first-party in the repo (strategy_a_maker.py docstring: fee schedule PDF HTTP 429;
  docs/webull_risk_controls.md line 49: not confirmed). Two lines: **maker0** = 0 and **maker175** =
  0.0175*C*P*(1-P) rounded up per order (secondary sources, per strategy_a_maker.py). maker175 is the primary
  (ranking) line. Exits are always taker (taker fee, per team per exit order, aggregate qty).

## Simulation rules (shared)
- Quote cycle: requote times t_k = window_start + j*W while t_k + W <= window_end. At t_k all open orders are
  cancelled and new ones posted. Reference price R = last own-market trade with ts <= t_k, must be within 10 min
  of t_k else no quote. Limit L = R - h cents, rounded to the market tick; skip if L < 0.01 or L > 0.98.
- Order size 5 contracts (or less to respect the per-team inventory cap; no order if cap reached).
- Fill (strict trade-through, queue-agnostic, as strategy_a_maker.maker_fill): the order fills at L (full order
  size) if some own-market trade with ts in (t_k + 1 s, t_k + W] prints at price <= L - tick (strictly below L).
  One fill per order. Fill price L (no price improvement credited).
- No lookahead: decision at t_k uses rows ts <= t_k only; fills use rows strictly after t_k + 1 s.
- Taker exit (M1/M2 variants "exit"): sell all inventory of the team at the first own-market trade with
  ts >= exit_time + 1 s within 120 s, price = trade - 1 cent (floor 0.01), taker fee; if no such trade, hold to
  settlement (counted).
- Settlement: team YES pays 1 if it wins, 0.5 on tie; void games skipped.
- Windows (ET-independent, ESPN kickoff K): pregame [K-60 min, K-5 min]; ingame [K+20 min, K+3 h];
  late ingame [K+90 min, K+3 h]. Pregame "exit" occurs at K-5 min; ingame "exit" at K+3 h.
- Unit: games. Per-game P&L = sum over all fills of both teams, net of fees.

## Trials
**M1 pregame two-sided quoting (8):** both teams' YES, W = 5 min, h in {1,2} x cap in {10,30} contracts per team x
end {settle, exit at K-5 taker}.
**M2 ingame two-sided quoting (12):** same, window ingame, h in {1,2,3} x cap {10,30} x end {settle, exit at K+3h taker}.
**M3 maker entry on favourites (4):** quote a team only when R >= thr, h = 1, cap 10, W = 5 min, hold to
settlement. window in {pregame, late ingame} x thr in {0.85, 0.90}.
**M4 box via maker legs (8):** at each t_k post buys on BOTH teams at R_i - h; legs not filled stay (the first leg
is not cancelled until cycle end). Window in {pregame, ingame} x h in {1,2} x W in {5 min, 15 min}; cap 10 per
team, settle. Primary P&L includes orphan (single-leg) fills held to settlement. Diagnostics: count of cycles where
both legs fill within W (pairs), mean pair cost (sum of fill prices), paired-only net P&L (box locks 1.00 payout
including tie), orphan P&L.
**WF selectors (4):** WF-M1, WF-M2, WF-M3, WF-M4: in test week w, trade the grid config (of that mechanism's
grid above) with the best past-weeks (< w) net c/contract on maker175, requiring >= 30 past filled contracts and
the best > 0, else no trade that week. These re-use the grid's per-week results.

Total 8 + 12 + 4 + 8 + 4 = 36.

## Evaluation
- ET weeks (Monday start) of kickoff; the data span 25 game weeks (2025-07-28 .. 2026-01-12). The first 6 are
  history, the next 19 are test weeks. All 32 grid trials and the selectors are reported on the 19 test weeks
  (no parameter is fitted, each grid point is its own trial). All-weeks numbers appear as diagnostics, unranked.
- Metrics per trial: games with a fill, fills, contracts, fill rate (fills / orders posted), adverse selection
  (mean outcome of filled contracts minus mean fill price), ROC = net P&L / sum(entry cost + entry fee) as a ratio
  of sums, game-bootstrap 95% CI (2,000 reps, numpy default_rng(20261004), resampling games with replacement),
  net c/contract on each fee line, Sharpe = mean/std of daily (ET game-day) P&L * sqrt(365), max drawdown of the
  cumulative daily P&L (dollars), and ROC excluding the 5 best games.
- Ranking: by maker175 ROC lower CI bound, then ROC.
- Outputs: results/posthoc_costside_maker/{RESULTS.md,trials_log.csv,daily_pnl.csv}; per-trade files gitignored.
