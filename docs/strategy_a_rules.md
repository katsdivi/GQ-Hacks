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

The game's kickoff in the table comes from the Kalshi event date (`kickoff_source = kalshi_date`) because our ESPN name match failed, so it falls under rule 3 and is excluded.

## 3. Kickoff times

- ESPN public scoreboard, `groups=90` (all divisions; `groups=80` and `limit=1000` cut the college board to about 25 games a day). NFL from the NFL scoreboard.
- Kickoffs come from ESPN only (v3). A game with no ESPN kickoff match is excluded from Strategy A and listed here. A kickoff is never inferred from the Kalshi event date or from trading.
- Games with no ESPN kickoff match (training plan of 1,267 games: 1,266 matched, 1 not):
  - cfb_20250830_alby_iowa (KXNCAAFGAME-25AUG30ALBYIOWA): excluded.

Open question for Divi (decide before any Strategy A result): v3 says "Games ESPN does not have are dropped". ESPN does list this game ("UAlbany Great Danes at Iowa Hawkeyes", event 401752799, 2025-08-30T22:00Z); only our name matcher missed it. Two options: keep the exclusion above, or allow hand-checked ESPN event ids (as `ingest/holdout_candidates.py` does for 3 holdout games). Either way, the choice applies to the test set too.

## Disclosure

Seen while setting these rules (incidental, no Strategy A computation): the Albany at Iowa settlement (Iowa won), the existence and ids of the 3 blank-result preseason games, and per-game trade counts in the download log. No entry prices, returns or win rates by price have been computed or looked at.
