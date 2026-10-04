# Post-hoc Idea 13: NFL closing moneyline as fair value at kickoff

**Label: post-hoc, exploratory; sportsbook closing line used as a signal only; selected on training only.**

Committed before any strategy code touches real data. The only real-data work so far is STEP 0: the nflverse
games file (data/nflverse_raw/games.csv, gitignored) and the game mapping by date and team names
(scripts/posthoc_idea13_map.py), which reads no Kalshi trades.

## Spec (verbatim)

- Universe: NFL games in the Strategy A training set (kickoff < 2026-08-01) and v3 A4 holdout set with nflverse moneylines. Preseason games are skipped if nflverse has no line (counted).
- Fair value p_X = no-vig probability from the closing moneylines (implied probabilities normalized to sum 1).
- Decision t = kickoff. K_X = last Kalshi YES trade for X at or before t, within 10 min before t, else skip.
- Buy 10 Kalshi YES of the team with the larger p_X - K_X, only if p_X - K_X >= e. One trade per game.
- e in {0.02, 0.04, 0.06}: 3 variants.
- Fill = first Kalshi trade on that market at or after t + 1.0 s, plus 1 cent, capped 0.99; skip if none within 5 min or fill is 0.99. Hold to settlement. Ties 0.5.
- Fees: Kalshi direct primary, Webull secondary, costs x2.
- Placebo: buy the team with K_X - p_X >= e.
- Selection on training only: highest ROC (Kalshi direct) among e with >= 40 trades; tie -> larger e.
- Metrics: trades, ROC with game-bootstrap 95% CI (2,000 reps, seed 20261004), P&L per contract, Brier score of p vs K on all matched games, daily P&L Sharpe x365 on game days, max DD, skew, excluding top 5 games.
- Limitation stated: nflverse line timestamps are not published; a line captured after kickoff would be lookahead.
- Label: "post-hoc, exploratory; sportsbook closing line used as a signal only; selected on training only".

## Implementation notes (fixed before the real-data run)

- nflverse source: https://github.com/nflverse/nfldata/raw/master/data/games.csv, downloaded 2026-10-04 04:37 ET.
  Its documentation (DATASETS.md, README.md) does not state the source or capture time of `away_moneyline` /
  `home_moneyline`; treated as closing lines of unknown timing (see the limitation above).
- Mapping (STEP 0, scripts/posthoc_idea13_map.py): same unordered team pair (Kalshi aliases JAC -> JAX,
  LAR -> LA) and nflverse `gameday` equal to the ET date of the ESPN kickoff, +-1 day, nearest wins. Each Kalshi
  team gets its own moneyline by team code (never by the home/away label). Training: 331 NFL games, 282 matched
  (all with both lines), 49 unmatched, all preseason (nflverse has no preseason games). Holdout: 98 NFL games, 49
  matched, 49 unmatched, all preseason.
- Kickoff = ESPN kickoff (as Strategy A). Strategy A exclusions apply (`strategy_a.load_games`: non-ESPN
  kickoff, missing market, exclusion flags); skips counted by reason.
- American odds to implied probability: negative m -> -m / (-m + 100); positive m -> 100 / (m + 100). p_X = that
  team's implied probability over the sum of both.
- K_X uses the team's own-market YES price (`strategy_a.own_market_trades`), trades with ts <= t only, and the
  last one must have ts >= t - 600 s. If either team has no such K, the game is skipped ("no Kalshi price"); the
  Brier comparison uses the matched games where both K are available, K oriented to the home team as K_home.
  Brier of p and of K: (p_home - home_won)^2 averaged, using Kalshi settlement for home_won (ties 0.5); voids
  excluded.
- If both teams have equal p_X - K_X, the home team is taken (deterministic; noted).
- Fill window: first trade with t + 1 s <= ts <= t + 1 s + 300 s. Ties 0.5; voids (NaN settlement) excluded and
  counted.
- Costs x2: fill + 1 more cent (same cap) and fees x2, as Ideas 4 and 6. ROC = net P&L / (fill x 10 + fee).
- Daily P&L by ET date of t; Sharpe x365 on season-calendar days (zero-filled) and daily Sharpe on game days, as
  Idea 4.
- Per-trade output files are untracked and gitignored; summary tables are committed.
- No experiments/variants.csv rows written here (3 variants, held for a later combined commit).
