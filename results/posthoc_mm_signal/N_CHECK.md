# N (no-signal) maker on polymarket.com: descriptive check

**Label: descriptive, post-hoc, not pre-registered, one day.** Source: the committed posthoc-mm-signal run (b346230).
The per-fill rows on disk (data/mm_cache/fills.parquet, gitignored) were verified first: 428 N fills, +60 s P&L
$46.53, both equal to results.csv, so nothing was rerun. Script: scripts/posthoc_mm_signal_n_check.py; numbers in
n_check.json. Same settings as the run: join best bid and ask, 10 contracts, inventory +/- 50, strict trade-through
fills, kickoff cut, maker fee 0. Data: Oct 3 and Oct 4 Vultr polymarket.com feed, 88 games, of which 59 had N fills.
Per-contract figures divide by all 4,280 filled contracts, the same convention as results.csv (38 fills have no mid
at +60 s and contribute 0 to the +60 s P&L).

| Measure | +60 s mark | Held to settlement |
|---|---|---|
| P&L per contract, game-bootstrap 95% CI (2,000, seed 20261004) | +1.09 c [+0.17, +2.12] | +2.66 c [-0.62, +6.06] |
| Excluding the top 5 games | +0.15 c [-0.48, +0.77] | -0.01 c [-3.36, +3.00] |
| Share of games positive (59 with fills) | 57.6% | 52.5% |
| Share of all 88 games positive | 38.6% | 35.2% |
| Break-even maker fee per contract | 1.09 c | 2.66 c |

Split of the +60 s P&L (388 fills with a mid both just before the fill and at +60 s):
- spread captured (mid before fill minus our price, signed): +$63.18, +1.63 c per contract
- mark-to-mid move from fill to +60 s (adverse selection): -$15.65, -0.40 c per contract
- the other 2 fills have no pre-fill mid; their +60 s P&L (-$1.00) is in the $46.53 but not in the split
  ($63.18 - $15.65 - $1.00 = $46.53).

Maker fee for these markets: 0, no rebate. The Gamma market metadata cached by posthoc-idea11
(wt-idea11/data/pm_resolution/<condition>.json, 84 of 84 markets) shows feeType "zero_fees", feeSchedule rate 0,
rebateRate 0, takerOnly true. The same files carry makerBaseFee 1000 and takerBaseFee 1000; their meaning is not
documented in the repo, and under feeType zero_fees they are read as inactive.

Reading: on one day the plain maker's +60 s P&L CI excludes zero, but the result rests on a few games (excluding the
top 5 it is about zero), fewer than half of all games were positive, and the settlement P&L CI includes zero. Not
pre-registered, one day, top of book only, queue position unknown (strict trade-through is a lower bound on fills),
and polymarket.com is not available to US persons.
