# Methods finding: trade-based lead/lag is biased by trading activity; book midpoints are not

Date: 2026-10-03. Simulated data only (no market prices). Code: tests/test_activity_bias.py, xcorr_lead.py.
Reports: out/activity_bias_report.csv (trade-based), out/activity_bias_quotes_report.csv (quote-based).

## Question

Kalshi game markets trade about 390 times a minute in game; polymarket.com about 5; Polymarket US about 1. If one venue trades far more often than the other, does a lead/lag statistic report a lead that is not there?

## Simulation

- Each simulated game: a hidden P(home) path for 7 hours at 1 s steps (small random steps plus 15 jumps of 3 to 10 cents).
- Three cases per venue pair:
  - no link: the two venues follow independent paths (what the unrelated-games placebo measures);
  - linked, zero lag: both venues follow the same path at the same time (a real link, no lead);
  - true 5 s lead: the same path, the second venue 5 s behind Kalshi.
- Trade-based version: each venue trades as a Poisson process at its own rate; a trade's price is the venue's path value plus 0.5 cent bid/ask bounce, rounded to the cent. Price series: trailing 3 s median of trades on the 1 s grid (the provisional spec).
- Quote-based version: each venue's best bid and ask track its path (rounded to the cent, 1 cent wide) with random one-tick spread flicker (Kalshi 6, polymarket.com-like 2, Polymarket-US-like 1 per minute). polymarket.com-like quotes are streamed on change; Polymarket-US-like quotes are sampled once a second with a 0.3 to 0.35 s receipt delay, like our poller. Price series: book midpoint on the 1 s grid.
- Statistic for both: the lag (s) that maximises the correlation of 1 s changes, max lag 15 s, positive = Kalshi first (leadlag.xcorr_lag).
- Decision rule (xcorr_lead.decide): Kalshi leads iff median lag >= 1 s (1.5 s for 1 s polled quotes), a two-sided Mann-Whitney test of real vs no-link placebo lags gives p < 0.05, and >= 60% of games have lag > 0; at least 30 games. Applied to 10 studies of 40 games against a 40-game no-link placebo; 400 games per case.

## Results

| Price series | Kalshi vs | Case | Median lag | Share of games with lag > 0 | Rule says "Kalshi leads" |
|---|---|---|---|---|---|
| Trades | 5 trades/min | no link | +1.0 s | 52% | 0 of 10 studies |
| Trades | 5 trades/min | linked, zero lag | +1.0 s | 62% | 3 of 10 (false) |
| Trades | 5 trades/min | true 5 s lead | +6.0 s | 100% | 10 of 10 |
| Trades | 1 trade/min | no link | 0.0 s | 48% | 0 of 10 |
| Trades | 1 trade/min | linked, zero lag | +5.0 s | 83% | 10 of 10 (false) |
| Trades | 1 trade/min | true 5 s lead | +8.0 s | 93% | 10 of 10 |
| Book mids | polymarket.com-like (streamed) | no link | 0.0 s | 48% | 0 of 10 |
| Book mids | polymarket.com-like (streamed) | linked, zero lag | 0 s in 100% of games | 0% | 0 of 10 |
| Book mids | polymarket.com-like (streamed) | true 5 s lead | 5 s in 100% of games | 100% | 5 of 10 |
| Book mids | Polymarket-US-like (1 s polled) | no link | +1.0 s | 51% | 0 of 10 |
| Book mids | Polymarket-US-like (1 s polled) | linked, zero lag | 0 s in 100% of games | 0% | 0 of 10 |
| Book mids | Polymarket-US-like (1 s polled) | true 5 s lead | 5 s in 100% of games | 100% | 5 of 10 |

Power of the rule for a true 5 s lead on book mids, by number of games (10 studies each): 30 games 6/10 (polymarket.com-like) and 7/10 (Polymarket-US-like); 60 games 7/10 and 7/10; 80 games 10/10 and 10/10.

## Interpretation

1. The unrelated-games placebo controls only the "no relationship" null. Its false-positive rate is 0 in every case, including the biased ones, so passing it does not rule out activity bias.
2. With trade-based prices, a thin venue looks late even when it is not: its price only moves when it trades, and the trailing median needs new trades. The bias is about +1 s at 5 trades/min and about +5 s at 1 trade/min; at 1 trade/min the rule declares a false Kalshi lead in every study.
3. Book midpoints move when quotes move, which does not need a trade, so a zero-lag link reads 0 s and a 5 s lead reads 5 s in every simulated game. The remaining limit is the rule's power, which needs about 80 games for a reliable result.
4. Consequences for the project (HYPOTHESIS_v2.md Amendment 2 draft): the confirmatory lead test uses recorded book midpoints on holdout games; all trade-based lag results (the polymarket.com training xcorr of median +7 s, and any Polymarket US Time & Sales result) are exploratory only; Polymarket US on trade data is not testable at about 1 trade/min.

## Limits

- The simulation's quote model is simple (one-tick spread, random flicker, immediate update on information). Real makers may update late; that would be a real lag on that venue, not an artefact, and is what the test is meant to find.
- Real polymarket.com in-game trade rates vary by game (median about 5/min on the three games checked); real Polymarket US training games trade a median of 1.0 per minute in game (NFL 0.0, CFB 3.0).
- An exploratory "activity-matched" null for trade data (the thin venue's trade times with Kalshi's own price) was tried on 40 games: it removed the 1/min false lead but also lost the true 5 s lead (p = 0.098), and did not remove the 5/min false lead. It is not used.
