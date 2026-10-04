# Post-hoc Idea 6: buy the winner just after the game ends, hold to settlement

**Label: post-hoc, exploratory; designed and selected on training only.**

Written and committed before any strategy code runs on real data. The only real-data work so far is the
Step 0 feasibility check (5 training games: ESPN summary fields, Kalshi trade timing; no P&L computed).
Holdout (v3 A4 holdout A/B set, 768 games) is run once, only on the exact phrase "run idea6 holdout".

## Data

- Games. Training: the Strategy A training set, `data/raw/kalshi_only_games.csv` (1,267 games, kickoff before
  2026-08-01), loaded with `strategy_a.load_games` (settlements from `data/raw/kalshi_market_meta.csv`).
  Holdout: the 768-game v3 A4 holdout A set, built exactly as `scripts/final_test_run.real_ctx` (same
  construction as Post-hoc Idea 4: `events.csv` with an ESPN kickoff at or before 2026-10-03 20:00 ET,
  settlements from `settlements.csv`).
- Kalshi trades: the tick files already on disk (window ESPN kickoff - 2 h to + 5 h). Prices are each team's own
  YES price (`strategy_a.own_market_trades`).
- ESPN event id: no stored mapping exists. Recovered from the cached scoreboards (`data/raw/espn/`,
  `data/holdout_raw/espn/`): same league and exact ESPN kickoff timestamp; if several events share it, the best
  `ingest.kalshi_only_train._name_score` match of both teams (Kalshi team names: `yes_sub_title` from the Kalshi
  historical market files for training, `k_home`/`k_away` from `events.csv` for holdout). Step 0 coverage:
  training 1,267 of 1,267, holdout 768 of 768. A game with no event id is skipped and counted.
- ESPN summary (`site.api.espn.com/apis/site/v2/sports/football/{nfl|college-football}/summary?event=ID`)
  fetched once per game and cached under `data/espn_raw/<league>_<event id>.json` (gitignored, never committed).
  Holdout summaries are fetched only after "run idea6 holdout".

## Game end E (end-marker rule)

- Plays = `drives.previous[*].plays[*]` in ESPN's order.
- Marker play: text, stripped, trailing periods removed, case-insensitive, equal to "END GAME", "End of Game" or
  "End of 4th Quarter".
- E = wallclock of the FIRST marker play where the score at that play (`homeScore`, `awayScore`) is not tied,
  AND no non-marker play comes after it in the play list, AND no ESPN scoring play (`scoringPlays`) has a
  wallclock after it.
- Skip and count, by reason:
  1. no ESPN event id;
  2. ESPN status not final (`header.competitions[0].status.type.completed` is not true);
  3. no marker play with an untied score (includes OT games ending on a scoring play);
  4. a non-marker play, or a later scoring play, after the first untied marker (game not over at the marker);
  5. marker play has no wallclock.
- Winner = the team ahead in the score at E (public at E). Never the ESPN final score, never the Kalshi result.
- ESPN team -> Kalshi team code: the orientation (same or swapped) with the higher sum of `_name_score` over
  both teams, using Kalshi team names and codes; skip and count ("team mapping") if the best sum is below 1.6
  or both orientations tie. ESPN's home/away label is not used to decide orientation.

## Decision, fill, payout

- Decision t = E + D, D in {60, 180, 600} s: 3 variants.
- Entry: buy 10 YES of the winner. Fill = first Kalshi trade on that market at or after t + 1.0 s (no upper time
  bound inside the trade file), trade price + 1 cent, capped at 0.99. Skip if there is no such trade ("no
  post-decision trade"), or if the fill price is 0.99 ("fill at 0.99"). Hold to settlement.
- Payout = Kalshi's actual settlement of that market (an early or wrong settlement counts as it happened).
  Tie 0.5. Void / unsettled (NaN result): excluded and counted.
- Fees, per order of 10: Kalshi direct 0.07 x C x P x (1 - P) rounded up to the cent (primary,
  `strategy_a.fee_kalshi_direct`); Webull $0.02 per contract (secondary). Costs x2: fill + 1 more cent (same cap)
  and fees x2.
- ROC = net P&L / (fill x 10 + fee).
- Placebo: buy the LOSER's YES at the same t with the same fill rule (same skips). Expected to lose.

## Selection (training only)

Highest mean ROC, Kalshi direct, costs x1, winner leg, among D with at least 50 trades; tie -> larger D.
Recorded, not re-tuned on holdout.

## Metrics, training and holdout separately (per D, per leg, per fee line, costs x1 and x2)

trades; games with any Kalshi trade (either team) after t; mean ROC with game-bootstrap 95% CI (2,000 reps, seed
20261004); P&L per contract (cents); number of losing trades with game ids; daily P&L on game days (ET date of
t), Sharpe annualized x365 (on season-calendar days, zero-filled, as Idea 4) and daily Sharpe (game days); max
drawdown; skew of daily P&L; worst trade; ROC and P&L excluding the top 5 games by P&L; median time from E to
Kalshi's last trade (either team market) in the file; capacity = contracts traded on the winner's market after
t + 1 s, per game (median, mean).

## Descriptive outputs (not variants), training and holdout separately

a) games with a clean E, and skip counts by reason;
b) time from E to the winner's first trade at >= 0.99 (median, p90; games with no such trade counted);
c) share of clean-E games with any winner trade <= 0.97 after E + 60 s, after E + 180 s, after E + 600 s;
d) sanity: for each D, games where the winner's last Kalshi trade at or before E + D is below 0.90, listed with
   game ids (may indicate a bad E); also the count of games where the ESPN winner at E differs from Kalshi's
   settlement (listed);
e) Western Michigan vs Michigan (early Sept 2026, holdout): its E, the winner's prices after E, and Kalshi's
   settlement; reported with the holdout run.

## Tests (synthetic, before real data)

fill never before t + 1 s; winner never uses data after E; payout uses Kalshi settlement, not ESPN; fee
function at P = 0.95, 0.98, 0.99; a game with a play after an "End of 4th Quarter" marker is skipped.

## Records

No `experiments/variants.csv` rows (post-hoc; outputs under `results/posthoc_idea6/` instead, as Idea 4).
