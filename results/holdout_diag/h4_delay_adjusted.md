exploratory, post-run, partial: before 17:00 ET Oct 3

h3 median delay d = 19.227186402 s. Available polymarket_us latencies: [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0]. Nearest to 1 + d = 20.227186402: 10.0; nearest to 2 + d = 21.227186402: 10.0 (lower on a tie). Consistency: parquet 1 s subset n = 604 (run file: 604).

h4 rule: a fill leg is CONFIRMED if some T&S trade on that slug printed at home price <= our price + 1e-9 for a buy of home, or >= our price - 1e-9 for a sell of home, with venue time in [fill time - 1 s, fill time + 2 s] (inclusive). Entry: buy home at entry_px if direction == +1 else sell home at entry_px. Exit: the opposite side at exit_px. Fill times are entry_fill_ns / exit_fill_ns of the trade row.

| source | latency_s | share_entry_confirmed | share_exit_confirmed | share_both_confirmed | set | n_fills | n_games | mean_net_c_per_contract | ci95_low | ci95_high | share_games_pnl_pos | mean_net_c_excl_top5_games | n_fills_excl_top5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| results/holdout_diag/g_laggard_trades.parquet | 10.0 | 0.15435139573070608 | 0.3793103448275862 | 0.05747126436781609 | all subset fills | 609 | 39 | 0.7932676518883415 | 0.13494827097505663 | 1.3538366529263794 | 0.46153846153846156 | 0.07788461538461536 | 416 |
| results/holdout_diag/g_laggard_trades.parquet | 10.0 | 0.15435139573070608 | 0.3793103448275862 | 0.05747126436781609 | both legs confirmed | 35 | 15 | -3.3000000000000003 | -4.197732558139535 | -2.2438166666666675 | 0.06666666666666667 | -3.76 | 30 |
| results/holdout_diag/g_laggard_trades.parquet | 10.0 | 0.15435139573070608 | 0.3793103448275862 | 0.05747126436781609 | all subset fills | 609 | 39 | 0.7932676518883415 | 0.13494827097505663 | 1.3538366529263794 | 0.46153846153846156 | 0.07788461538461536 | 416 |
| results/holdout_diag/g_laggard_trades.parquet | 10.0 | 0.15435139573070608 | 0.3793103448275862 | 0.05747126436781609 | both legs confirmed | 35 | 15 | -3.3000000000000003 | -4.197732558139535 | -2.2438166666666675 | 0.06666666666666667 | -3.76 | 30 |
