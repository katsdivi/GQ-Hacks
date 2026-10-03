# Strategy A data rules (v3), fixed before any Strategy A result exists

Decided by Divi on 2026-10-03, ~10:50 ET. Written and committed before strategy.py contains any Strategy A code and before any Strategy A computation (entries, returns, win rates by price) has been run. These rules apply to the training set built by `ingest/kalshi_only_train.py` (`data/raw/kalshi_only_games.csv`) and, unchanged, to the test set at the final test run.

## 1. Ties

A Kalshi game market that settles at 0.5 (a tie; Kalshi marks it "scalar") pays 0.5 per contract. Tied games stay in the sample and are never dropped.

In `kalshi_only_games.csv` a tie currently shows as a blank `settlement_result`. Before a blank is treated as a tie, the Kalshi market metadata must show the scalar settlement at 0.5. A blank that is not a confirmed 0.5 settlement is an unsettled market: it is excluded and listed with the reason.

Training games with a blank result so far (download about 30% done; all NFL preseason): nfl_20250808_lv_sea, nfl_20250810_mia_chi, nfl_20250817_jac_no.

## 2. Albany at Iowa, 2025-08-30 (KXNCAAFGAME-25AUG30ALBYIOWA)

The download title parse was suspect, so home/away and the result were resolved from Kalshi's own metadata (checked 2026-10-03):

- Event title "University at Albany at Iowa", sub_title "ALBY at IOWA (Aug 30)": away = Albany (ALBY), home = Iowa (IOWA).
- Markets: KXNCAAFGAME-25AUG30ALBYIOWA-IOWA (yes_sub_title "Iowa", result yes, finalized) and -ALBY (yes_sub_title "University at Albany", result no, finalized). Rules text: "If Iowa wins the University at Albany vs Iowa college football game originally scheduled for Aug 30, 2025, then the market resolves to Yes."
- Home/away and result are unambiguous: home Iowa, home win = 1. This matches the row already in `kalshi_only_games.csv`.

Decided by Divi on 2026-10-03, ~11:05 ET: the game is INCLUDED. v3 drops only games ESPN does not have, and ESPN has this one ("UAlbany Great Danes at Iowa Hawkeyes", event 401752799, kickoff 2025-08-30T22:00Z); only our name match missed it. Its kickoff comes from that hand-checked ESPN event (`ESPN_EVENT_OVERRIDE` in `ingest/kalshi_only_train.py`, `kickoff_source = espn_event_id`). Its first download used the Kalshi event date (12:00Z) as kickoff, so the trade window missed the game; that file and its games-table row are re-fetched with the ESPN kickoff once the full download finishes.

## 3. Kickoff times

- ESPN public scoreboard, `groups=90` (all divisions; `groups=80` and `limit=1000` cut the college board to about 25 games a day). NFL from the NFL scoreboard.
- Kickoffs come from ESPN only (v3). A kickoff is never inferred from the Kalshi event date or from trading. A game ESPN does not have is excluded from Strategy A and listed here.
- When ESPN has a game but our name match misses it, the kickoff may come from a hand-checked ESPN event id (checked against both teams' ESPN schedules). The same rule applies to the test set.
- Training plan of 1,267 games: 1,266 matched by name, 1 not. Hand-matched games (the only one): cfb_20250830_alby_iowa (KXNCAAFGAME-25AUG30ALBYIOWA) -> ESPN event 401752799.
- Games excluded because ESPN does not have them: none so far.

## Disclosure

Seen while setting these rules (incidental, no Strategy A computation): the Albany at Iowa settlement (Iowa won), the existence and ids of the 3 blank-result preseason games, and per-game trade counts in the download log. No entry prices, returns or win rates by price have been computed or looked at.
