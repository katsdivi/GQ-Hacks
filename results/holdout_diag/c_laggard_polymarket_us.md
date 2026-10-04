# c. Laggard, Polymarket US (exploratory, post-run)

From results/holdout/laggard_latency_curve.csv (the run's own curve; Polymarket US has no documented delay, so total latency = added latency).

| Latency | Trades | Games | Mean net c/contract | Game-bootstrap 95% CI |
|---|---|---|---|---|
| 1 s | 1686 | 71 | +1.480 | [+0.924, +1.998] |
| 2 s | 1689 | 71 | +1.329 | [+0.776, +1.842] |
| 5 s | 1697 | 71 | +0.930 | [+0.361, +1.432] |

- Fee: costs.fee -> Polymarket US taker 0.0695 x C x P x (1 - P), banker's rounding (half to even) to the cent per order, charged on entry and on exit (laggard.py fill_trades: f_in, f_out).
- Fill size: 10 contracts per trade (laggard.SETTING qty=10), no depth check: the Polymarket US poll carries no sizes, so every fill is assumed to get all 10 contracts at the recorded best quote; capacity is NaN (not measurable).
- Fill price: the recorded Polymarket US best ask (buy) / best bid (sell) in the last snapshot with ts <= fill time (backward as-of). Snapshot ts = local receipt time of a once-a-second batch poll.
