# Hypothesis

Committed before any backtest. The commit timestamp is the proof.

We expect Kalshi NFL and college football game contracts to move toward CME's price for the same game in the seconds after a large CME move, because Kalshi's order book is quoted largely by slower retail traders and resting limit orders that update after the institutional venue does.

The edge persists because the venues are fragmented: CME's sports contracts reach traders through futures brokers, Kalshi's through retail apps such as Webull, so few participants watch and trade both in real time.

**If true, we should see:**

1. Kalshi close most of a CME jump within seconds.
2. A net edge that shrinks as assumed reaction time grows.
3. No edge in the placebo where Kalshi is treated as the leader.

**It fails if:**

1. The lag is shorter than a realistic reaction time.
2. The edge disappears after Kalshi's fees and spread.
3. The profit comes from a handful of games.

**Edge category (track list):** structural or institutional constraint.

**Holdout:** tune on games before August 1, 2026. Test once on August 1 to October 2026.

---

## Retired before any backtest (2026-10-02)

This hypothesis is retired without being tested. The text above is unchanged.

Reason: it cannot be tested as registered. The committed holdout (August 1 to October 2026) contains 0 CME NFL single-game contracts on Databento (`GLBX.MDP3`), and the one college week-0 contract checked (CGFSUQ629, August 29 2026) had 0 trades. The training period has only about 18 CME games with trade data (Databento coverage of these contracts starts 2026-01-11), too few for the planned tuning and robustness checks.

Data examined before retiring: one exploratory training game, LAR at CHI on 2026-01-18 (CME FGCHIF618 C0001, Kalshi KXNFLGAME-26JAN18LACHI-CHI), used for the data check and a venue overlay chart. No backtest, strategy, or tuning was run. No holdout prices were loaded. The result on that one game is not used to form a new hypothesis.
