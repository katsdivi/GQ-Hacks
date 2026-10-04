# Post-hoc Idea 10: scoring-event fade

**Label: post-hoc, exploratory; selected on training only.**

Committed before any strategy code touches real data. Real-data work before this commit: Step 0 only (ESPN summary
field inspection on cached training summaries; no Kalshi prices, no P&L). Holdout only on the exact phrase
"run idea10 holdout".

## Spec (verbatim)

- Universe: Strategy A training set; v3 A4 holdout set (ESPN fetched only if holdout is run). Same exclusions as A.
- Events: ESPN scoring plays (touchdowns, field goals, safeties) with kickoff + 20 min <= wallclock <= kickoff + 4 h.
- Decision t = wallclock + 60 s. Pre-price = last Kalshi YES trade for the scoring team at or before wallclock (within 120 s, else skip). Post-price = last trade for that team at or before t (within 30 s of t, else skip). Move m = post - pre.
- Hypothesis (fixed): retail overreacts to scores. If m >= s, buy 10 YES of the OTHER team. Exit = sell at first trade on that market at or after t + 180 s, minus 1 cent. One position per game at a time; events during an open position are ignored.
- s in {0.03, 0.05, 0.10}: 3 variants.
- Entry fill = first trade on that market at or after t + 1.0 s, plus 1 cent, capped 0.99; skip if none within 60 s. Exit fill skip rule: if no trade within 120 s after t + 180 s, exit at settlement and count it.
- Fees: Kalshi direct on both legs (primary), Webull $0.02/contract per leg (secondary), costs x2.
- Placebo: FOLLOW the move (buy the scoring team) with the same rules.
- Also report, descriptive: median Kalshi move at +10, +30, +60, +180, +300 s after scoring plays, by play type. (Event study; not a variant.)
- Selection on training only: highest mean net c/contract (Kalshi direct) among s with >= 200 trades; tie -> larger s.
- Metrics: trades, mean net c/contract with game-bootstrap 95% CI (2,000 reps, seed 20261004), gross c/contract, per-trade Sharpe (not annualized), daily P&L Sharpe x365 on game days, max DD, skew, excluding top 5 games.
- Label: "post-hoc, exploratory; selected on training only".

## Implementation notes (choices the spec leaves open, fixed here before any run)

1. ESPN data. Event ids and summaries from Idea 6's cache (`../wt-idea6/data/espn_raw/`, read-only; ids from
   `ids_training.csv`, built by `scripts/posthoc_idea6_ids.py` on branch posthoc-idea6, commit 0f57732). A game
   with no id or no summary is skipped and counted.
2. Team mapping: Idea 6's `orient` (posthoc-idea6, 0f57732): ESPN home/away -> Kalshi code by
   `ingest.kalshi_only_train._name_score` over both orientations, Kalshi team names from `ids_training.csv`;
   weak (< 1.6) or tied match -> game skipped and counted. ESPN's home/away label is never used alone.
3. Scoring play = a play in `drives.previous[*].plays[*]` with `scoringPlay` true and `scoringType.name` in
   {touchdown, field-goal, safety}. Scoring team = the ESPN side whose score (`homeScore`/`awayScore`) rose versus
   the previous play; if neither or both rose, the event is skipped and counted. Play type for the event study =
   `scoringType.name`. Plays with no wallclock are skipped and counted (Step 0: 43 of 4,941 scoring plays in the
   first 556 cached summaries).
4. Kalshi prices are each team's own YES price (`strategy_a.own_market_trades` convention). "Within 120 s" for the
   pre-price means wallclock - 120 s <= trade ts <= wallclock; "within 30 s of t" for the post-price means
   t - 30 s <= ts <= t. Events are processed in wallclock order (ties: ESPN play order).
5. Entry: market = the OTHER team's market (fade) or the scoring team's market (placebo). Entry fill = first trade
   with t + 1 s <= ts <= t + 1 s + 60 s; price + 1 cent, capped 0.99 (a capped fill is still entered; the only
   entry skip is no trade within 60 s). A skipped entry leaves the game free for later events.
6. Exit: first trade on the same market with t + 180 s <= ts <= t + 180 s + 120 s; exit price = trade price - 1 cent,
   floored at 0.01. Else exit at Kalshi settlement of that market (1, 0, or 0.5 for a tie; no exit fee) and counted.
   A void / unsettled market in that case: trade excluded and counted. The position is open from entry fill to
   exit fill (or to settlement); events with wallclock before the exit time are ignored.
7. Fees per leg of 10 contracts: Kalshi direct 0.07 x C x P x (1 - P) rounded up to the cent
   (`strategy_a.fee_kalshi_direct`), Webull $0.02 per contract. Costs x2: entry + 1 more cent (cap 0.99), exit - 1
   more cent (floor 0.01), fees x2.
8. Net c/contract = (exit - entry) x 100 - fees per contract (cents). Gross c/contract = (exit - entry) x 100.
   Daily P&L by ET date of t; Sharpe x365 on game days only (mean / sd of daily P&L x sqrt(365)), as the spec says.
   Per-trade Sharpe = mean / sd of per-trade net P&L. Bootstrap resamples games (all of a game's trades together).
   Excluding top 5 games = drop the 5 games with the highest total net P&L.
9. Fade and placebo are simulated independently (each with its own one-position-at-a-time state).
10. Event study: for every scoring play with a wallclock in the in-game window, scoring team's own YES price, last
    trade at or before wallclock + h (h in 10, 30, 60, 180, 300 s) minus the pre-price (same 120 s rule); medians
    by play type and n. Descriptive only.
11. No experiments/variants.csv rows written here (Divi adds post-hoc rows in one commit later).
