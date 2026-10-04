# Post-hoc Idea 12: in-game Kalshi vs polymarket.com gap, Kalshi leg only, hold to settlement

**Label: post-hoc, exploratory; selected on training only.**

Committed before any real-data code runs. Holdout only on the exact phrase "run idea12 holdout".

## Spec (verbatim)

- Universe: Strategy B training set (Kalshi + polymarket.com trades, kickoff < 2026-08-01) and v3 A4 holdout set with polymarket.com matched. Same exclusions as B, including the 14 ESPN kickoff-error games and the B orientation rule (0014b1e).
- Window: kickoff + 20 min to kickoff + 4 h (the polymarket.com kickoff wipe is excluded).
- At each Kalshi or polymarket.com trade time t in the window: K_X = last Kalshi YES trade for team X at or before t; Q_X = last polymarket.com trade for X at or before t (venue time), oriented to X. Both must be within 30 s before t, else no signal at t.
- Gap g_X = Q_X - K_X. Signal at the first t where g_X >= k for some X AND g_X >= k held continuously for the previous 10 s (same persistence as B). Buy 10 Kalshi YES of X. One trade per game.
- k in {0.03, 0.05, 0.08}: 3 variants.
- Fill = first Kalshi trade on that market at or after t + 1.0 s, plus 1 cent, capped 0.99; skip if none within 60 s or fill is 0.99. Hold to settlement. Ties 0.5, voids excluded and counted.
- Fees: Kalshi direct 0.07 x C x P(1-P) rounded up per order (primary); Webull $0.02/contract (secondary); costs x2.
- Placebo: same rule with g_X <= -k (buy X when Kalshi is RICH vs polymarket.com).
- Selection on training only: highest ROC (Kalshi direct) among k with >= 100 trades; tie -> larger k.
- Metrics, training and holdout separately: trades, ROC with game-bootstrap 95% CI (2,000 reps, seed 20261004), P&L per contract, mean g at entry, win rate vs mean fill, daily P&L on game days with Sharpe annualized x365 and daily Sharpe, max DD, skew, worst day, excluding top 5 games, and the result excluding the 12 stale-polymarket.com games flagged in B's diagnostics.
- Label: "post-hoc, exploratory; selected on training only".

## Implementation notes (fixed before any real-data run)

- Training games: Strategy B's set, `run_strategy_b.games()` logic: the 977 T8 games in `out/strategy_b/b_games_espn.csv`, minus the 14 v3 Amendment 1 coverage games (`run_strategy_b.EXCLUDED_A1`, asserted), 963 games. Ticks: `data/ticks/<game_id>_kalshi.parquet` and `<game_id>_polymarket.parquet` (tick contract, prices P(home); polymarket.com timestamps are block (venue) time). Kickoff = ESPN kickoff.
- Prices per team X: K_home = last Kalshi trade on the home market (P(home) = home YES price); K_away = 1 - last trade on the away market (its stored P(home) flipped back to away YES). polymarket.com has one market per game in P(home): Q_home = last trade price, Q_away = 1 - last trade price.
- State: (K_X, Q_X, valid) changes only at trade times and when a trade ages past 30 s; valid at time s iff both last trades have ts <= s and s - ts <= 30 s. Persistence: the condition (valid and g_X >= k) holds at every instant of [t - 10 s, t], evaluated on that step function (only trades at or before t are used). Candidate t = every Kalshi trade (either market) or polymarket.com trade time in [kickoff + 20 min, kickoff + 4 h]. Equal t for both teams: larger |g|, then home.
- Fill window: first Kalshi trade on X's market with ts in [t + 1 s, t + 60 s] (Strategy B's first_fill convention); own YES price + 1 cent, cap 0.99; fill at 0.99 is skipped.
- Settlement: Kalshi market result of X's ticker from `data/raw/kalshi_kxnflgame_historical.parquet` / `kalshi_kxncaafgame_historical.parquet` (`settlement_value_dollars`, status finalized/settled); missing or not settled = void, excluded and counted.
- Orientation rule (0014b1e) applied to Idea 12 entries: at the entry decision (the game's only, hence median, decision), K and PM = Strategy B grid prices (strategy_b.venue_grid, trailing 3 s median, label floor(t) - 1 s); FLAGGED if |K - PM| > 0.20 and |K - (1 - PM)| < 0.05 and |K - 0.5| > 0.10. Primary result unchanged; an "excluding flagged" line is reported if any game is flagged.
- 12 stale-polymarket.com games: `results/holdout_diag/d_b_big_diff_games.csv`, class "stale venue (polymarket)" (STATUS.md diagnostics d). They are holdout games; the "excluding stale" line is computed on whatever game ids exist in the sample (none in training).
- Daily P&L: ET date of t; Sharpe x365 on the season calendar zero-filled (training 2025-07-31 to 2026-01-25, as Idea 4); daily Sharpe on game days. Money in Decimal; fees via strategy_a.fee_kalshi_direct; costs x2 = fill + 1 more cent (cap 0.99) and fees x2. ROC = net / (fill x 10 + fee).
- No experiments/variants.csv rows here (held for a later combined commit). Per-trade outputs are gitignored.
