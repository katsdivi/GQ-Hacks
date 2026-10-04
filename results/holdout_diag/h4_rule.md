exploratory, post-run, partial: before 17:00 ET Oct 3

h4 rule: a fill leg is CONFIRMED if some T&S trade on that slug printed at home price <= our price + 1e-9 for a buy of home, or >= our price - 1e-9 for a sell of home, with venue time in [fill time - 1 s, fill time + 2 s] (inclusive). Entry: buy home at entry_px if direction == +1 else sell home at entry_px. Exit: the opposite side at exit_px. Fill times are entry_fill_ns / exit_fill_ns of the trade row.

Top 5 games = the 5 largest per-game sums of pnl_cents. CI = laggard.game_bootstrap_ci(per-game sum, per-game n) of edge_cents_per_contract.

| source | latency_s | share_entry_confirmed | share_exit_confirmed | share_both_confirmed | set | n_fills | n_games | mean_net_c_per_contract | ci95_low | ci95_high | share_games_pnl_pos | mean_net_c_excl_top5_games | n_fills_excl_top5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| results/holdout/laggard_trades.csv | 1.0 | 0.052980132450331126 | 0.41721854304635764 | 0.023178807947019868 | all subset fills | 604 | 39 | 2.2397350993377487 | 1.584876412862525 | 2.7422080634233397 | 0.8205128205128205 | 1.5201044386422975 | 383 |
| results/holdout/laggard_trades.csv | 1.0 | 0.052980132450331126 | 0.41721854304635764 | 0.023178807947019868 | both legs confirmed | 14 | 10 | -4.092857142857143 | -5.465 | -2.369916666666667 | 0.2 | -5.4 | 9 |
| results/holdout/laggard_trades.csv | 2.0 | 0.05785123966942149 | 0.39173553719008264 | 0.01818181818181818 | all subset fills | 605 | 39 | 2.0171900826446283 | 1.3841687234015578 | 2.5173891095428913 | 0.8205128205128205 | 1.3127937336814621 | 383 |
| results/holdout/laggard_trades.csv | 2.0 | 0.05785123966942149 | 0.39173553719008264 | 0.01818181818181818 | both legs confirmed | 11 | 6 | -3.9545454545454546 | -5.344444444444445 | -3.12 | 0.0 | -3.6999999999999997 | 3 |

Full run (all fills, no 17:00 cut), laggard_latency_curve.csv:

| latency_s | n_trades | n_games | edge_cents_mean | edge_ci_low | edge_ci_high | ci_method | pnl_total | per_trade_normal_ci_low (not the plan's CI) | per_trade_normal_ci_high (not the plan's CI) | n_skipped_no_quote | n_skipped_break | n_skipped_after_end | venue |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | 1686 | 71 | 1.4803677342823252 | 0.924048738842622 | 1.997610467795829 | block bootstrap by game, 2000, seed 20261003 | 249.59 | 1.191055335759656 | 1.7696801328049945 | 0 | 89 | 0 | polymarket_us |
| 2.0 | 1689 | 71 | 1.3287744227353464 | 0.7761211875675227 | 1.8420961781798328 | block bootstrap by game, 2000, seed 20261003 | 224.43 | 1.039431843710644 | 1.6181170017600488 | 0 | 86 | 0 | polymarket_us |
