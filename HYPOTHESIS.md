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
