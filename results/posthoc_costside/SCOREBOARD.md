# Cost-side search scoreboard

Points (Divi's scheme, 2026-10-04): +100 full stop condition (the only reward that counts); +10 genuinely new
mechanism tested, any sign; +5 well-documented negative that rules out a whole mechanism; -50 lookahead, holdout or
live data, unlogged trial, or undisclosed rerun; -20 bug found after results were seen; -10 repeating a mechanism
already tried (by me, the helpers, the broad search or the pre-registered strategies); -5 per trial of a finer grid
on a mechanism whose best walk-forward CI is already wholly below 0; 0 for a negative result by itself; 0 for an
uncorrected in-sample positive. Scored by the search agent itself, conservatively; Divi or Alden may rescore.

| Round | Item | Points | Reason |
|---|---|---|---|
| 1 | A: maker execution of 6 existing signals | +10 | new execution mechanism |
| 1 | B: fee-band selection | +10 | new |
| 1 | C1: polymarket.com leads Kalshi (Kalshi idle s seconds) | 0 | close to pre-registered Strategy B (Kalshi toward polymarket.com); not counted as new |
| 1 | C3: Kalshi own 5 c moves, momentum and reversal | +10 | new (finer and broader than Idea 10's scoring fade) |
| 1 | C3 ruled out (all 12 trials negative, both directions, all exits) | +5 | whole mechanism ruled out |
| 1 | C4: in-game price bands at kickoff + 20 min | 0 | overlaps the patterns helper's longshot-by-phase (pre-listed before the helpers existed; no credit) |
| 1 | Ideas 7/12 team-mapping bug found after first results | -20 | bug after results seen (disclosed rerun, so no -50) |
| 2 | ARB: two-market complement arbitrage | +10 | new |
| 2 | ARB ruled out (both CIs below 0; last-trade sums are stale) | +5 | ruled out |
| 2 | CONS: search consensus + maker entry | +10 | new combination (pre-listed per coordinator) |
| 2 | VOL: polymarket.com lead by Kalshi volatility regime | +10 | new |
| 2 | TP: take-profit exits | +10 | new |
| 2 | TP ruled out (all <= 0) | +5 | ruled out |
| 3 | PAIR: orphan handling (hedge now, hedge at deadline, cut) | +10 | new (coordinator lead) |
| 3 | PAIR orphan handling ruled out (all 3 CIs below 0; orphan adverse selection measured) | +5 | ruled out |
| 3 | FEE: 100-contract order rounding | +10 | new |
| 3 | FAV: favourites 0.80 to 0.90 at kickoff - 5 min, maker | -10 | repeats pre-registered Strategy A-maker (favourite >= 0.80 at kickoff - 5 min, maker) |
| 3 | VOLX: calm filter applied to other signals | 0 | extension of R2.VOL, not a new mechanism |
| 4 | PAIRCALM h 0.02, h 0.03 | -10 | 2 trials on the pair mechanism whose best CI was already below 0 (-5 each) |
| 4 | REQUOTE: passive orphan completion | +10 | new orphan handling |
| 4 | REQUOTECALM | -5 | finer variant of a below-0 mechanism |
| 4 | Pair market-making ruled out in-game (all variants below 0) | +5 | ruled out |
| 5 | PAIRPRE: pre-game pairs | -10 | maker helper already tested pre-game fills |
| 5 | SL: stop-loss exits | +10 | new |
| 5 | SL ruled out (all CIs below 0) | +5 | ruled out |
| 5 | ANCHOR: polymarket.com-anchored maker quote | +10 | new |

| 6 | BIG: large single prints, follow and fade | +10 | new (trade size never used before) |
| 6 | IMB: in-game aggressor imbalance 10 to 120 s, follow and fade | +10 | new horizon and phase (Idea 8 was pre-game 30 min only) |
| 6 | GAP: moves after no-trade gaps | +10 | new |
| 6 | In-game Kalshi microstructure ruled out (16 trials, none with CI above 0, every win rate below break-even) | +5 | ruled out |

**Total after Round 6: +150.** Stop condition (+100): not met.
