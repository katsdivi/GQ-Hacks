# Post-hoc T&S laggard test results

**EXPLORATORY, selected after seeing the holdout.** Does not change any pre-registered result. This adds 3 variants (L = 1, 2, 5 s) to the DSR total.

SPEC: results/posthoc_tns/SPEC.md, commit a510ba090d09ffe86648227b2198f135cb094cc0 (2026-10-04 03:33:08 ET) (committed before any test code existed).

Universe: 57 qualifying Polymarket US games with laggard window start before 17:00 ET Oct 3 (SPEC note (a)); games with at least one signal: 50.

## Results (primary: L = 1 s)

| latency_s | primary | signals | trades | games_with_trades | mean_net_c_per_contract | ci_low | ci_high | share_games_positive | per_game_sharpe_not_annualized | mean_net_c_excl_top5_games | trades_excl_top5 | pnl_total_usd | skips_no_entry_trade | skips_no_exit_trade | outside_coverage_not_skips |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0000 | True | 821 | 231 | 32 | -4.0429 | -4.3726 | -3.6792 | 0.0625 | -0.8342 | -4.1235 | 226 | -93.3900 | 10 | 6 | 574 |
| 2.0000 | False | 821 | 231 | 32 | -4.1385 | -4.4559 | -3.7668 | 0.0625 | -0.8447 | -4.2212 | 226 | -95.6000 | 10 | 6 | 574 |
| 5.0000 | False | 821 | 231 | 32 | -4.3753 | -4.6955 | -4.0933 | 0.0312 | -0.8933 | -4.4345 | 226 | -101.0700 | 11 | 5 | 574 |

Skips by reason are the skips_* columns; outside_coverage_not_skips counts round trips whose decision or a needed fill print falls at or after 17:00 ET (excluded, not skips).

## Comparison only (not the same fill model)

run's own Polymarket US laggard (recorded polled quotes), total latency 1 s, same 57 games, exit fill before 17:00 ET: 604 fills, 39 games, +2.240 c/contract [+1.585, +2.742]

## 5 random filled trades at L = 1 s (random_state 20261003)

- cfb_20261003_morg_vill (aec-cfb-morgst-vill-2026-10-03), direction -1, exit reason gap_closed
  - decision 2026-10-03 16:10:07.000000000 ET; Kalshi mid at decision 0.7000; T&S home price at decision (last print <= decision) 0.7350; T&S grid price used by the signal 0.7350
  - entry time 2026-10-03 16:10:08.000000000 ET; entry print 2026-10-03 16:10:08.179672576 ET at 0.7150; entry fill 0.7050; fee 0.14
  - exit time 2026-10-03 16:10:10.000000000 ET; exit print 2026-10-03 16:10:11.547777280 ET at 0.6850; exit fill 0.6950; fee 0.15
  - P&L -0.1900 USD, net -1.9000 c/contract
- cfb_20261003_rich_laf (aec-cfb-rich-lafay-2026-10-03), direction -1, exit reason gap_closed
  - decision 2026-10-03 15:38:42.000000000 ET; Kalshi mid at decision 0.0800; T&S home price at decision (last print <= decision) 0.1150; T&S grid price used by the signal 0.1150
  - entry time 2026-10-03 15:38:43.000000000 ET; entry print 2026-10-03 15:39:10.208819712 ET at 0.0850; entry fill 0.0750; fee 0.05
  - exit time 2026-10-03 15:39:19.000000000 ET; exit print 2026-10-03 15:39:23.911671552 ET at 0.0500; exit fill 0.0600; fee 0.04
  - P&L +0.0600 USD, net +0.6000 c/contract
- cfb_20261003_mrmk_yale (aec-cfb-merri-yale-2026-10-03), direction -1, exit reason gap_closed
  - decision 2026-10-03 14:21:30.000000000 ET; Kalshi mid at decision 0.6000; T&S home price at decision (last print <= decision) 0.6400; T&S grid price used by the signal 0.6400
  - entry time 2026-10-03 14:21:31.000000000 ET; entry print 2026-10-03 14:21:37.374346752 ET at 0.6250; entry fill 0.6150; fee 0.16
  - exit time 2026-10-03 14:21:57.000000000 ET; exit print 2026-10-03 14:22:18.713816832 ET at 0.6200; exit fill 0.6300; fee 0.16
  - P&L -0.4700 USD, net -4.7000 c/contract
- cfb_20261003_cit_scst (aec-cfb-cita-scarst-2026-10-03), direction -1, exit reason gap_closed
  - decision 2026-10-03 16:20:15.000000000 ET; Kalshi mid at decision 0.2550; T&S home price at decision (last print <= decision) 0.3100; T&S grid price used by the signal 0.3100
  - entry time 2026-10-03 16:20:16.000000000 ET; entry print 2026-10-03 16:20:16.369599744 ET at 0.2800; entry fill 0.2700; fee 0.14
  - exit time 2026-10-03 16:20:30.000000000 ET; exit print 2026-10-03 16:20:35.298592256 ET at 0.2600; exit fill 0.2700; fee 0.14
  - P&L -0.2800 USD, net -2.8000 c/contract
- cfb_20261003_ust_pre (aec-cfb-stmn-presb-2026-10-03), direction -1, exit reason gap_closed
  - decision 2026-10-03 12:46:36.000000000 ET; Kalshi mid at decision 0.5000; T&S home price at decision (last print <= decision) 0.5300; T&S grid price used by the signal 0.5300
  - entry time 2026-10-03 12:46:37.000000000 ET; entry print 2026-10-03 12:46:38.258249728 ET at 0.5350; entry fill 0.5250; fee 0.17
  - exit time 2026-10-03 12:46:42.000000000 ET; exit print 2026-10-03 12:46:49.371424512 ET at 0.5400; exit fill 0.5500; fee 0.17
  - P&L -0.5900 USD, net -5.9000 c/contract

## Unit tests

tests/test_posthoc_tns.py: 10 passed in 0.33s (synthetic T&S and synthetic Kalshi books only); tests/test_laggard.py with it: 31 passed

Prices are home-oriented (home = 1 - T&S Last Price for long_is_away slugs). Times are venue time (T&S) and recorder receipt time (Kalshi), no clock correction.
## Correction note (display only, added after the run; numbers unchanged)

The *_trade_et string columns in trades.csv (entry_trade_et, exit_trade_et) and the "entry print" / "exit print"
times in the 5 sample trades above were formatted after a nullable-integer column passed through float64, so
their last digits are off by less than 256 ns. The integer columns entry_trade_ns and exit_trade_ns in
trades.csv are exact and are what the fills used (the fill search works on the exact int64 arrays). Exact print
times of the 5 sample trades, formatted from those integer columns (same 5 rows, random_state 20261003):

| game | entry print (exact) | exit print (exact) |
|---|---|---|
| cfb_20261003_morg_vill | 2026-10-03 16:10:08.179672492 ET | 2026-10-03 16:10:11.547777377 ET |
| cfb_20261003_rich_laf | 2026-10-03 15:39:10.208819793 ET | 2026-10-03 15:39:23.911671466 ET |
| cfb_20261003_mrmk_yale | 2026-10-03 14:21:37.374346792 ET | 2026-10-03 14:22:18.713816829 ET |
| cfb_20261003_cit_scst | 2026-10-03 16:20:16.369599680 ET | 2026-10-03 16:20:35.298592360 ET |
| cfb_20261003_ust_pre | 2026-10-03 12:46:38.258249696 ET | 2026-10-03 12:46:49.371424581 ET |

Status counts over all three latencies (trades.csv): filled 693, outside coverage 1722, no entry trade within
60 s 31, no exit trade within 60 s 17. Universe 57 games; 50 with at least one signal; 32 with a filled trade
in coverage at every L. Reminder: this test adds 3 variants to the DSR total.
