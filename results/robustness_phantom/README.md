# Data-quality check: book levels with 0 < size < 0.01 contracts

Branch check-phantom (not merged). Read-only on results/holdout/. Kalshi's minimum size granularity is 0.01
contracts, so a reconstructed level with 0 < size < 0.01 is floating-point residue, not a real quote.

## 1. Where books are reconstructed

- Kalshi: `collector/run.py`, class handling the Kalshi websocket, `handle()` (orderbook_snapshot /
  orderbook_delta) with `_levels()` and `_emit()`; written to disk by `top_rows()` (line 369).
  Sizes are Python **float** (`float(q)` from `yes_dollars_fp` / `no_dollars_fp` snapshot levels;
  `float(msg["delta_fp"])` for deltas). A delta is ADDED to the stored float size; the level is deleted when
  the running sum is **<= 1e-9** (line 529, epsilon rule), not at exactly 0 and not below 0.01. Float sums of
  fractional deltas therefore can leave a level with a size such as 0.00999 or 1e-6 that stays in the book.
- polymarket.com: same file, `handle()` for event_type book / price_change. Sizes are **float**; price_change
  carries the NEW absolute size (replace, not add), and the level is deleted when size is **exactly 0**
  (line 713). No running sums, so no float residue can build up.
- Only the TOP OF BOOK is written to disk (one bid row, one ask row per snapshot change, P(home) terms). The
  lead test (`holdout_mid.py` -> `xcorr_lead.mid_snapshots` / `mid_grid`), Idea 1 and Idea 2 all read these
  recorded top-of-book rows; none rebuilds deeper levels.

What item 2 can and cannot measure: "level update" = a recorded top-of-book row (bid or ask). Removing a
residue row can only make that side EMPTY at that snapshot, because the next level was never recorded; the mid
is then undefined (never filled across an empty side). Residue levels that were never at the top of the book
are invisible here.

## 2. Vultr Oct 3 books, the 88 qualifying polymarket.com lead-test games

Windows, machine (all Vultr) and book-wipe exclusion per game from results/holdout/lead_polymarket.com_per_game.csv;
game set identical to data/live/holdout_windows.csv at feadc99 (asserted). Script: scripts/phantom_check.py.
Outputs: item2_summary.csv, item2_per_game.csv.

| | Kalshi | polymarket.com |
|---|---|---|
| a) top-of-book rows in windows | 9,120,086 | 3,655,289 |
| a) rows with 0 < size < 0.01 | 58,213 (0.638%) | 0 |
| games with any residue row | 63 of 88 | 0 |
| b) share of 1 s grid points (outside book-wipe exclusion) with a residue best bid or ask | 1.208% (16,092 of 1,332,138) | 0 |
| c) grid points where the mid differs without residue | 1.208%; all 16,092 go from defined to undefined, 0 change value | 0 |
| c) games with mids differing on > 0.1% of grid points | 48 of 88 (max 50.8%, cfb_20261003_msu_wis) | 0 |
| d) mid changes, all rows vs residue removed (sum over games) | 96,459 vs 95,253 (52 games differ) | 111,737 vs 111,737 |
| d) games falling below the 50-change qualifying bar | 2 (nd_unc 82 -> 28, msu_wis 150 -> 15) | 0 |

Worst Kalshi games (share of grid points whose mid differs): msu_wis 50.8%, mich_minn 18.9%, ala_msst 12.2%,
nd_unc 9.8%, osu_iowa 5.7%; median game 0.14%.

## 3. Decision

The threshold (mids differ on more than 0.1% of grid points in any game) is met (48 games), so the lead test was
rerun with residue rows removed: see the section below.
