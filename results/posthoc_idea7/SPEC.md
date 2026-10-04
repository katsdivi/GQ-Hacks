# Post-hoc Idea 7: cross-venue consensus, hold to settlement

**Label: post-hoc, exploratory; selected on training only.**

Committed before any real-data code runs. Holdout only on the exact phrase "run idea7 holdout".

## Spec (verbatim)

- Universe: games in the Strategy B training set (Kalshi + polymarket.com trades, kickoff < 2026-08-01) and the v3 A4 holdout set with polymarket.com matched. Same exclusions as B, including the 14 ESPN kickoff-error games and the B orientation rule (0014b1e).
- Decision t = kickoff - 5 min. For each team: Kalshi price K = last Kalshi YES trade at or before t; polymarket.com price Q = last polymarket.com trade for that team at or before t (venue timestamp), oriented to the same team. Both must be within 10 min before t, else skip the game.
- Signal: gap g = Q - K for each team. Buy 10 Kalshi YES of the team with the larger g, only if g >= k. One trade per game.
- k in {0.02, 0.03, 0.05}: 3 variants.
- Fill = first Kalshi trade on that market at or after t + 1.0 s, plus 1 cent, capped at 0.99; skip if none within 5 min. Hold to settlement. Ties 0.5, voids excluded and counted.
- Fees: Kalshi direct 0.07 x C x P(1-P) rounded up per order (primary); Webull $0.02/contract (secondary); costs x2.
- Placebo: buy the team with the most NEGATIVE g, if g <= -k (Kalshi rich vs polymarket.com); should lose.
- Selection on training only: highest ROC (Kalshi direct) among k with >= 100 trades; tie -> larger k.
- Metrics, training and holdout separately: trades, ROC with game-bootstrap 95% CI (2,000 reps, seed 20261004), P&L per contract, mean g at entry, win rate vs mean fill, daily P&L on game days with Sharpe annualized x365 and daily Sharpe, max DD, skew, worst day, excluding top 5 games, correlation of daily P&L with Strategy A training daily P&L.
- Label: "post-hoc, exploratory; selected on training only".

## Implementation notes (fixed before any real-data run)

- Base commit 5ef528f (as instructed). Commit 0014b1e is NOT an ancestor of 5ef528f; the orientation rule is read from `git show 0014b1e:scripts/b_orientation_check.py` and docs/holdout_run_disclosure.md on main ("B orientation check").
- Training games: out/strategy_b/b_games_espn.csv (977 T8 games, ESPN kickoffs) minus the 14 games of run_strategy_b.EXCLUDED_A1 (coverage / ESPN kickoff errors, asserted exactly as run_strategy_b.games() does) = 963 games. Kickoff = espn_kickoff. Ticks: data/ticks/<game_id>_kalshi.parquet and <game_id>_polymarket.parquet (tick contract: price = P(home)).
- Prices per team: Kalshi K_X = last trade on X's own market (event-X ticker), as X's own YES price (away market: 1 - stored P(home); strategy_a.own_market_trades convention). polymarket.com has one market per game stored as P(home): Q_home = last trade price, Q_away = 1 - Q_home. All four inputs (K_home, K_away and the polymarket.com trade) must have ts in [t - 10 min, t]; otherwise the game is skipped ("stale or missing price").
- Larger g: if g_home == g_away, home is taken (deterministic; logged). Placebo picks the smaller g with the same tie rule.
- Orientation rule (B's 0014b1e rule applied at this idea's decision time, with K = K_home and PM = Q_home): FLAGGED if |K - PM| > 0.20 AND |K - (1 - PM)| < 0.05 AND |K - 0.5| > 0.10. As in B's disclosed action, the primary result keeps all games; a second line "excluding flagged games" is reported beside it with the flagged games listed.
- Fill: as spec. The spec has no "skip if fill is 0.99" clause for this idea, so a capped 0.99 fill is entered (counted as capped). Fill window: trades with ts in [t + 1 s, t + 1 s + 5 min].
- Settlement: data/raw/kalshi_market_meta.csv by the bought ticker, settlement_value_dollars (1, 0, or a scalar such as 0.5 for a tie); a market not finalized or missing is "void/unsettled", excluded and counted.
- ROC = net P&L / (fill x 10 + fee). Costs x2: fill + 1 more cent (same cap) and fees x2. Fees: strategy_a.fee_kalshi_direct, Webull $0.02 x 10.
- Daily P&L by ET date of t; Sharpe x365 on season-calendar days zero-filled (training season 2025-07-31 to 2026-01-25, as Idea 4) and daily Sharpe on game days.
- Strategy A training daily P&L for the correlation: out/strategy_a/rows.parquet, theta 0.80, favorite leg (placebo False), entered, Kalshi direct pnl, summed by its `date` column (ET kickoff date), as Idea 8; correlation over the union of days, zero-filled.
- Per-trade files are untracked and gitignored; summaries committed. No experiments/variants.csv rows (held for one later commit; 3 variants).
