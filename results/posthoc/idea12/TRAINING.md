# Post-hoc Idea 12: training results

**Label: post-hoc, exploratory; selected on training only.** Spec SPEC.md (ca72fb9); script and tests de62d46 (11 synthetic tests passed). Run 2026-10-04 about 04:40 to 04:48 ET, nice -n 19, 963 Strategy B training games (977 minus the 14 Amendment 1 coverage games). Holdout not run (only on "run idea12 holdout").

## Selected k (training rule: >= 100 trades, highest Kalshi direct ROC, costs x1)

**k = 0.03.** Its ROC is negative and its CI includes 0: no edge. The placebo (Kalshi rich) loses more at k 0.03 and 0.05, so the gap points the right way, but not by enough to pay the 1 cent spread and fees.

## Main table (Kalshi direct, costs x1, all games)

| k | leg | trades | roc_mean | roc_ci_lo | roc_ci_hi | cents_per_contract | pnl_total | win_rate | mean_fill | mean_g | sharpe_x365 | sharpe_daily | max_drawdown | skew_daily | worst_day | excl_top5_roc | excl_top5_pnl |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.03 | signal | 829 | -0.0519 | -0.1358 | 0.0384 | -1.0969 | -90.93 | 0.4964 | 0.4935 | 0.0467 | -0.9651 | -0.0635 | 162.19 | -0.7012 | -58.46 | -0.0915 | -134.12 |
| 0.03 | placebo | 868 | -0.1323 | -0.2072 | -0.058 | -5.0802 | -440.96 | 0.4983 | 0.5355 | -0.0438 | -4.4686 | -0.2987 | 465.12 | -1.443 | -62.85 | -0.1716 | -484.16 |
| 0.05 | signal | 692 | -0.055 | -0.1475 | 0.0385 | -1.4931 | -103.32 | 0.4762 | 0.4767 | 0.0781 | -1.1185 | -0.0757 | 246.54 | 0.2123 | -43.03 | -0.101 | -146.3 |
| 0.05 | placebo | 747 | -0.1205 | -0.1998 | -0.0427 | -5.3826 | -402.08 | 0.5027 | 0.5421 | -0.0734 | -3.4506 | -0.2358 | 424.62 | -1.2529 | -75.58 | -0.163 | -444.85 |
| 0.08 | signal | 489 | -0.0646 | -0.1754 | 0.057 | -1.6642 | -81.38 | 0.4427 | 0.4449 | 0.1292 | -1.1846 | -0.0855 | 175.15 | 0.5779 | -30.47 | -0.127 | -123.62 |
| 0.08 | placebo | 544 | -0.0454 | -0.132 | 0.0421 | -2.3472 | -127.69 | 0.5726 | 0.5818 | -0.1249 | -1.6793 | -0.1208 | 150.57 | -1.2118 | -54.33 | -0.0936 | -169.41 |

## Selected k = 0.03, signal leg, all fee lines

| fee_line | costs | trades | roc_mean | roc_ci_lo | roc_ci_hi | cents_per_contract |
|---|---|---|---|---|---|---|
| kalshi_direct | x1 | 829 | -0.0519 | -0.1358 | 0.0384 | -1.0969 |
| kalshi_direct | x2 | 829 | -0.1049 | -0.1821 | -0.0226 | -3.483 |
| webull | x1 | 829 | -0.0671 | -0.149 | 0.0195 | -1.7081 |
| webull | x2 | 829 | -0.1295 | -0.2025 | -0.0526 | -4.7081 |

## Excluding the 12 stale-polymarket.com games, and excluding 0014b1e-flagged games (Kalshi direct, x1)

The 12 stale games (results/holdout_diag/d_b_big_diff_games.csv, class "stale venue (polymarket)") are holdout games; 0 are in the training sample, so "excl_stale12" equals "all".

| k | leg | subset | trades | roc_mean | roc_ci_lo | roc_ci_hi | cents_per_contract |
|---|---|---|---|---|---|---|---|
| 0.03 | signal | excl_stale12 | 829 | -0.0519 | -0.1358 | 0.0384 | -1.0969 |
| 0.03 | signal | excl_flagged | 828 | -0.0508 | -0.1365 | 0.0357 | -1.0478 |
| 0.03 | placebo | excl_stale12 | 868 | -0.1323 | -0.2072 | -0.058 | -5.0802 |
| 0.03 | placebo | excl_flagged | 868 | -0.1323 | -0.2072 | -0.058 | -5.0802 |
| 0.05 | signal | excl_stale12 | 692 | -0.055 | -0.1475 | 0.0385 | -1.4931 |
| 0.05 | signal | excl_flagged | 691 | -0.0537 | -0.1457 | 0.0383 | -1.4349 |
| 0.05 | placebo | excl_stale12 | 747 | -0.1205 | -0.1998 | -0.0427 | -5.3826 |
| 0.05 | placebo | excl_flagged | 746 | -0.1213 | -0.1982 | -0.0384 | -5.4358 |
| 0.08 | signal | excl_stale12 | 489 | -0.0646 | -0.1754 | 0.057 | -1.6642 |
| 0.08 | signal | excl_flagged | 486 | -0.0653 | -0.1767 | 0.0588 | -1.6753 |
| 0.08 | placebo | excl_stale12 | 544 | -0.0454 | -0.132 | 0.0421 | -2.3472 |
| 0.08 | placebo | excl_flagged | 541 | -0.0459 | -0.1316 | 0.0433 | -2.3569 |

Flagged entries (0014b1e rule at the entry decision):

| game_id | k | leg | team |
|---|---|---|---|
| cfb_20251018_pur_nw | 0.03 | signal | away |
| cfb_20251018_pur_nw | 0.05 | signal | away |
| cfb_20251018_pur_nw | 0.05 | placebo | home |
| cfb_20251018_pur_nw | 0.08 | signal | away |
| cfb_20251018_pur_nw | 0.08 | placebo | home |
| cfb_20251101_cmu_wmu | 0.08 | signal | away |
| nfl_20251214_ind_sea | 0.08 | signal | home |
| nfl_20251214_ind_sea | 0.08 | placebo | away |
| nfl_20260117_buf_den | 0.08 | placebo | home |

## Skips

| k | leg | games | skip_no_signal | skip_no_post-decision_trade | skip_fill_at_0.99 | skip_void_unsettled | skip_missing_market | flagged_games | trades |
|---|---|---|---|---|---|---|---|---|---|
| 0.03 | signal | 963 | 101 | 30 | 0 | 0 | 3 | 1 | 829 |
| 0.03 | placebo | 963 | 55 | 35 | 2 | 0 | 3 | 0 | 868 |
| 0.05 | signal | 963 | 247 | 21 | 0 | 0 | 3 | 1 | 692 |
| 0.05 | placebo | 963 | 189 | 24 | 0 | 0 | 3 | 1 | 747 |
| 0.08 | signal | 963 | 466 | 5 | 0 | 0 | 3 | 3 | 489 |
| 0.08 | placebo | 963 | 400 | 11 | 5 | 0 | 3 | 3 | 544 |

Full table (Webull, costs x2, all subsets): training_results.csv. Per-game rows: training_trades.csv (gitignored; regenerate with the command in README.md).
