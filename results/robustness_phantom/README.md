# Data-quality check: book levels with 0 < size < 0.01 contracts

Branch check-phantom (not merged). Read-only on results/holdout/. Kalshi's minimum size granularity is 0.01
contracts, so a reconstructed level with 0 < size < 0.01 is floating-point residue, not a real quote.

## 1. Where books are reconstructed

- Kalshi: `collector/run.py`, `KalshiWS.handle()` (orderbook_snapshot /
  orderbook_delta) with `_levels()` and `_emit()`; written to disk by `top_rows()` (line 369).
  Sizes are Python **float** (`float(q)` from `yes_dollars_fp` / `no_dollars_fp` snapshot levels;
  `float(msg["delta_fp"])` for deltas). A delta is ADDED to the stored float size; the level is deleted when
  the running sum is **<= 1e-9** (line 529, epsilon rule), not at exactly 0 and not below 0.01. Float sums of
  fractional deltas therefore can leave a level with a size such as 0.00999 or 1e-6 that stays in the book.
- polymarket.com: same file, `PolymarketWS.handle()` for event_type book / price_change. Sizes are **float**; price_change
  carries the NEW absolute size (replace, not add), and the level is deleted when size is **exactly 0**
  (line 713). No running sums, so no float residue can build up.
- Only the TOP OF BOOK is written to disk (one bid row, one ask row per snapshot change, P(home) terms). Every
  reader of the recordings therefore sees top of book only: the lead test (`holdout_mid.py` ->
  `xcorr_lead.mid_snapshots` / `mid_grid`) and the post-hoc Ideas 1, 2 and 11 that read the same files.

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
rerun with residue rows removed. Script scripts/phantom_lead_rerun.py: holdout_mid.run_all(holdout_run=True) on
the frozen run inputs (Vultr then Mac, frozen GAPS and heartbeats, holdout_candidates.csv, holdout_maps), code
unchanged except that book rows (bid/ask) with 0 < size < 0.01 are dropped when read. Run 04:40 to 05:05 ET.
Rows dropped during the rerun: Kalshi 232,094 of 37,950,660 read; polymarket.com 0 of 6,838,073;
Polymarket US 0 of 300,807. Outputs (labeled "robustness, post-run: residue levels removed"):
lead_comparison.csv, lead_decisions.json, lead_<test>_per_game.csv, lead_<test>_placebo.csv, rerun.log.

| | polymarket.com pre-registered | polymarket.com residue removed | Polymarket US pre-registered | Polymarket US residue removed |
|---|---|---|---|---|
| decision (Holm) | neither venue leads consistently | neither venue leads consistently | kalshi leads | kalshi leads |
| qualifying games | 88 | 86 | 76 | 75 |
| median corrected lag (s) | 0.0 | 0.0 | 7.5 | 7.0 |
| median game lag (s) | 0.0 | 0.0 | 7.5 | 7.0 |
| share positive | 0.125 | 0.128 | 0.921 | 0.920 |
| placebo median (s) | -1.0 | -1.0 | 0.0 | 1.0 |
| Mann-Whitney p | 0.709 | 0.785 | 3.2e-08 | 4.0e-07 |
| Holm level | 0.05 | 0.05 | 0.025 | 0.025 |
| games whose lag changed (of those qualifying in both) | | 1 | | 5 |

**No change to either pre-registered decision.** The two polymarket.com games lost are nd_unc and msu_wis
(below 50 Kalshi mid changes once residue is removed); Polymarket US loses one game. The pre-registered results
in results/holdout/ are unchanged and remain the reported results.
