# v2 who-leads result (pre-registered rule, training games)

Source: out/who_leads_summary.json (the run itself is in out/, not committed). Recorded here on 2026-10-03 so the committed record matches; numbers copied, nothing rerun.

| | Real games | Unrelated-games placebo |
|---|---|---|
| Games / qualifying | 916 / 838 | 749 / 603 |
| Kalshi first / polymarket.com first / ties | 827 / 9 / 2 | 492 / 96 / 15 |
| Median L (95% CI) | +8.0 s (7.5 to 8.0) | +7.0 s (6.0 to 8.0) |
| Rule output | "kalshi leads" | "kalshi leads"; 95.7% of pairs \|L\| >= 1 s |

Status: INCONCLUSIVE. The placebo also says "Kalshi leads", so the pre-registered rule cannot separate a real lead from an artifact; the simulation in docs/results/activity_bias.md shows trade-based lags are biased by activity. The confirmatory test is Amendment 2 (book midpoints on recorded holdout games).

T8 kickoff check (2026-10-03): 14 of 977 T8 games have a T8 kickoff more than 15 min from ESPN (docs/results/t8_kickoff_check.md); all 14 are in the 916-game v2 run. v2 is not rerun; its game windows used the T8 kickoff.
