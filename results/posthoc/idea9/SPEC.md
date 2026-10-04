# Post-hoc Idea 9: ESPN win probability vs Kalshi

**Label: post-hoc, exploratory; ESPN data used as a signal only; selected on training only.**

Committed before any strategy code touches real data. Real data seen so far (Step 0, no prices, no P&L): which
cached training ESPN summaries carry a `winprobability` series (539 of 540 cached at 04:02 ET), its fields on 5
games, and whether its `playId`s map to plays with a wallclock. Holdout only on the exact phrase
"run idea9 holdout".

## Spec (verbatim)

- Universe: Strategy A training set; v3 A4 holdout set (ESPN summaries fetched only if the holdout is run). Same exclusions as A; games without a win probability series or team mapping skipped and counted.
- ESPN probability for team X at play j = homeWinPercentage (or 1 - it for away), oriented by the Idea 6 name mapping, never by ESPN's home/away label alone.
- Known-time of play j = wallclock(j) + delay. delay in {60, 180} s.
- In-game window: kickoff + 20 min to the earlier of kickoff + 4 h or the first ESPN end-of-game marker.
- At each known-time t: Kalshi price K_X = last Kalshi YES trade for X at or before t, within 60 s of t, else skip that t. Gap g_X = ESPN_X - K_X.
- Signal: the first t in the window where g_X >= k for some X: buy 10 YES of X. One trade per game.
- k in {0.05, 0.10}. Variants = 2 k x 2 delay = 4.
- Fill = first Kalshi trade on that market at or after t + 1.0 s, plus 1 cent, capped 0.99; skip if none within 5 min or fill is 0.99. Hold to settlement. Ties 0.5, voids excluded and counted.
- Fees: Kalshi direct primary, Webull secondary, costs x2.
- Placebo: buy the team with g_X <= -k at the first such t (Kalshi rich vs ESPN).
- Selection on training only: highest ROC (Kalshi direct) among the 4 with >= 100 trades; tie -> larger delay, then larger k.
- Metrics as in Idea 8, plus mean g at entry and calibration of ESPN vs Kalshi at entry (Brier score of each on the traded games).
- Label: "post-hoc, exploratory; ESPN data used as a signal only; selected on training only".

## Implementation notes (fixed before the real-data run)

- Data. Training games and settlements: `strategy_a.load_games` on `data/raw/kalshi_only_games.csv` and
  `kalshi_market_meta.csv` (1,267 games, kickoff < 2026-08-01); Kalshi trades `data/raw/kalshi_only/`. Same
  exclusions as A = the game's `exclude` flag, kickoff not from ESPN, or a team market missing from the trades.
- ESPN source: summaries cached by the Idea 6 run (`../wt-idea6/data/espn_raw/<league>_<event id>.json`, ids in
  `ids_training.csv`), read only; a missing one is fetched into this worktree's `data/espn_raw/` (gitignored).
  No ESPN event id or no summary: skip and count.
- Team mapping: copied from branch posthoc-idea6 commit 0f57732 (`scripts/posthoc_idea6.py`, `orient()`): the
  orientation (same or swapped) with the higher `_name_score` sum over both teams using Kalshi team names and
  codes; skip ("team mapping") if the best sum is below 1.6 or the two orientations tie.
- Win probability series: `winprobability[*]` (`playId`, `homeWinPercentage`, `tiePercentage`). Each entry is
  joined to the play with the same id in `drives.previous[*].plays[*]`; entries whose play is missing or has no
  wallclock are dropped (they have no known-time). homeWinPercentage is ESPN's home team; ESPN_X for the Kalshi
  team X is homeWinPercentage if X is ESPN's home team under the mapping, else 1 - homeWinPercentage. If several
  plays share a known-time, the last one in ESPN's play order is the value at that time. Series empty after the
  join: skip ("no win probability series").
- End-of-game marker: the Idea 6 marker text rule (play text, stripped, trailing periods removed,
  case-insensitive, equal to "END GAME", "End of Game" or "End of 4th Quarter"); the window ends at the wallclock
  of the first such play, whatever the score. No marker: kickoff + 4 h.
- Known-times evaluated: the distinct wallclock(j) + delay over the joined series, in the window
  [kickoff + 20 min, end], both teams checked at each t; if both qualify at the same t, the larger g wins, home
  first on an exact tie. The signal leg and the placebo leg are found independently (each its own first t).
- Fill window: first trade on that market with t + 1 s <= ts <= t + 1 s + 300 s.
- Fees per order of 10: Kalshi direct 0.07 x C x P x (1 - P) rounded up to the cent (`strategy_a.fee_kalshi_direct`);
  Webull $0.02 per contract. Costs x2: fill + 1 more cent (same cap) and fees x2. ROC = net / (fill x 10 + fee).
- Metrics "as in Idea 8": trades, ROC with game-bootstrap 95% CI (2,000 reps, seed 20261004), P&L per contract,
  win rate vs mean fill, daily P&L on game days (ET date of t) with Sharpe annualized x365 (season-calendar days,
  zero-filled, as Idea 4) and daily Sharpe, max drawdown, skew, worst day, excluding top 5 games, correlation of
  daily P&L with Strategy A training daily P&L (Strategy A selected theta rows from `out/strategy_a/`, Kalshi
  direct, by ET kickoff date, on the union of days, zero-filled; reported n/a if that file is absent). Plus mean g
  at entry; Brier of ESPN_X and of K_X at entry vs the Kalshi payout of X, on the traded games.
- Caveat: the ESPN win probability series is the one served after the game. Whether every value equals what ESPN
  showed live at that play cannot be checked from this data.
- No `experiments/variants.csv` rows yet (held for one combined commit).
