## HYPOTHESIS_v4 numbers (added for the v4 edition; typed in appendix.tex and README, not \val keys)

| number | value | source |
|---|---|---|
| v4 commit and time | 94aa1a0, 2026-10-04 07:56:29 ET | git log origin/main HYPOTHESIS_v4.md |
| test set 1 eligible games | 0 (recordings end 00:34 ET) | posthoc-mm-v4 1d3d68a results/posthoc_mm_v4/LEDGER.md |
| origin P&L at +60 s | $46.53 | posthoc-mm-signal b346230 results.csv N_pnl60 |
| origin P&L held to settlement | $114.03 | posthoc-mm-signal results.csv N_pnlset |
| origin fills / games | 428 / 88 | posthoc-mm-signal results.csv, run.log |
| per contract at +60 s | +1.09 c [0.17, 2.12] | N_CHECK.md, n_check.json (863eb69) |
| excluding top 5 games | +0.15 c [-0.48, +0.77] | N_CHECK.md (863eb69) |
| share of 88 games positive | 38.6% | N_CHECK.md (863eb69) |
| spread captured / adverse selection | +$63.18 / -$15.65 | N_CHECK.md (863eb69) |
| share of games positive | 57.6% of 59 with fills (38.6% of all 88) | n_check.json 863eb69 |
| verdict | reading rule on the 59 games with fills: all four conditions pass, a lead worth testing live; over all 88 the game-share condition fails | N_CHECK.md 863eb69 |
| per-game Sharpe at +60 s | +0.22 [+0.06, +0.35] | coordinator recompute from n_detail_games.csv (8cb29f7), game bootstrap 2,000, seed 20261004 |
| per-game Sharpe held to settlement | +0.16 [-0.04, +0.35] | same |
| v3 Sharpe (x sqrt 365), block-bootstrap 95% CI | A -3.81 [-6.05, -0.50]; B -7.76 [-9.95, -6.07]; combined -7.78 [-10.13, -5.97] | coordinator recompute from main results/holdout/strategy_a_rows.parquet, strategy_b_trades.parquet (f4f3e28); point values equal numbers.json |
