# Kalshi leads, trade CME: results

Label: descriptive, post-hoc, 14 games. Spec 657c5b6, code 74b13ce (4 synthetic tests passed). Profit is per
contract after the CME exchange fee ($0.01 per contract per Globex trade, CME 25-466 Appendix D) and BEFORE broker
commissions. CI = game-bootstrap 95% (2,000, seed 20261004), 14 games.

## Stage 1

Data: 14 training games (12 NFL playoff games Jan 10 to 18, the CFP final Jan 19, two conference championships Jan
25, the Super Bowl Feb 8), 28 CME win contracts, CME MBP-1 top of book at venue time, Kalshi trades at venue time.

| J | L | exit | signals_real | executable_share | traded_n | profit_pc | ci_lo | ci_hi | excl_top5_profit_pc | placebo_profit_pc | real_minus_placebo | diff_ci_lo | diff_ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3 | 1 | settle | 3527 | 0.8313 | 5864 | -0.0303 | -0.0409 | -0.0179 | -0.0407 | -0.0329 | 0.0027 | -0.0097 | 0.0164 |
| 3 | 1 | t60 | 3527 | 0.8313 | 5659 | -0.0658 | -0.0704 | -0.0616 | -0.0658 | -0.0651 | -0.0007 | -0.0033 | 0.0017 |
| 3 | 2 | settle | 3527 | 0.7855 | 5541 | -0.0305 | -0.0397 | -0.0199 | -0.0396 | -0.0322 | 0.0017 | -0.0093 | 0.0140 |
| 3 | 2 | t60 | 3527 | 0.7855 | 5338 | -0.0660 | -0.0706 | -0.0619 | -0.0661 | -0.0649 | -0.0011 | -0.0037 | 0.0012 |
| 3 | 5 | settle | 3527 | 0.6883 | 4855 | -0.0320 | -0.0429 | -0.0213 | -0.0396 | -0.0320 | -0.0001 | -0.0121 | 0.0127 |
| 3 | 5 | t60 | 3527 | 0.6883 | 4682 | -0.0663 | -0.0706 | -0.0623 | -0.0664 | -0.0646 | -0.0017 | -0.0045 | 0.0007 |
| 4 | 1 | settle | 2174 | 0.8015 | 3485 | -0.0344 | -0.0464 | -0.0217 | -0.0437 | -0.0336 | -0.0008 | -0.0136 | 0.0124 |
| 4 | 1 | t60 | 2174 | 0.8015 | 3337 | -0.0598 | -0.0636 | -0.0560 | -0.0608 | -0.0648 | 0.0050 | 0.0012 | 0.0084 |
| 4 | 2 | settle | 2174 | 0.7387 | 3212 | -0.0378 | -0.0500 | -0.0243 | -0.0454 | -0.0327 | -0.0051 | -0.0184 | 0.0096 |
| 4 | 2 | t60 | 2174 | 0.7387 | 3074 | -0.0599 | -0.0637 | -0.0560 | -0.0612 | -0.0646 | 0.0047 | 0.0005 | 0.0089 |
| 4 | 5 | settle | 2174 | 0.6122 | 2662 | -0.0401 | -0.0572 | -0.0221 | -0.0512 | -0.0316 | -0.0085 | -0.0266 | 0.0102 |
| 4 | 5 | t60 | 2174 | 0.6122 | 2554 | -0.0624 | -0.0665 | -0.0584 | -0.0633 | -0.0643 | 0.0019 | -0.0022 | 0.0060 |
| 5 | 1 | settle | 1396 | 0.7837 | 2188 | -0.0241 | -0.0598 | 0.0055 | -0.0513 | -0.0342 | 0.0100 | -0.0237 | 0.0391 |
| 5 | 1 | t60 | 1396 | 0.7837 | 2083 | -0.0558 | -0.0609 | -0.0508 | -0.0585 | -0.0648 | 0.0089 | 0.0034 | 0.0144 |
| 5 | 2 | settle | 1396 | 0.7249 | 2024 | -0.0249 | -0.0566 | 0.0030 | -0.0452 | -0.0334 | 0.0086 | -0.0221 | 0.0366 |
| 5 | 2 | t60 | 1396 | 0.7249 | 1934 | -0.0547 | -0.0597 | -0.0496 | -0.0576 | -0.0646 | 0.0099 | 0.0042 | 0.0155 |
| 5 | 5 | settle | 1396 | 0.5820 | 1625 | -0.0147 | -0.0578 | 0.0181 | -0.0499 | -0.0333 | 0.0186 | -0.0244 | 0.0517 |
| 5 | 5 | t60 | 1396 | 0.5820 | 1564 | -0.0595 | -0.0646 | -0.0547 | -0.0622 | -0.0643 | 0.0047 | -0.0010 | 0.0105 |

Columns: signals_real = Kalshi signals (per game, not per contract); executable_share = share of contract-signals
where the CME mid had not moved 1 c in the signal direction by t + L and the needed side was quoted; traded_n =
executable contract-signals with an exit; placebo = game B's signals on game A's CME contracts at the same time since
kickoff.

What it shows:
- CME is usually stale after a Kalshi move: 58% to 83% of contract-signals still have an unmoved CME mid 1 to 5 s
  later, and the quote side is there (mean displayed size about 30,000 contracts).
- But the CME book is wide. The entry pays a median half-spread of 2.5 c (mean 2.8 c) relative to the mid at t, and
  the 60 s round trip costs a full spread: the gross 60 s result is a median -4.0 c per contract before fees.
- The Kalshi signal does carry information for CME. Real minus placebo is positive in most cells and its CI is above
  0 in 4 of the 60 s cells (J 4 c and 5 c, L 1 and 2 s: +0.5 to +1.0 c per contract). But the absolute profit is
  negative in every one of the 18 cells: -1.5 to -6.6 c per contract.

## Gate decision

Selection rule (Divi's): best placebo-adjusted profit with >= 50 executable signals: J = 5 c, L =
5 s, exit = settle (1625 trades): real -0.0147 [-0.0578,
+0.0181] per contract, placebo -0.0333, real minus placebo +0.0186
[-0.0244, +0.0517].

Gate: real profit after costs > 0: NO; placebo clearly worse (diff CI lower bound >
0): NO. **Gate FAILED. Stage 2 does not run, no 2026 CME data is downloaded, no money is spent, and that is the result.**


## Amendment 1: CME maker variant (spec f1b2677, code e05f28c, 6 synthetic tests passed)

Label: descriptive, post-hoc, 14 games; queue position unknown, trade-through fill is a lower bound on fills.

1,437 Kalshi signals at J = 5 c gave 2,449 contract attempts (343 more had no CME quote on the needed side at t).
Resting limit at the CME best bid (buy) or best ask (sell), size 10, filled only on a CME trade print strictly
through the limit within W.

| W_s | exit | attempts | fills | fill_rate | traded | games | gross_pc | profit_pc | ci_lo | ci_hi | excl_top5_profit_pc | breakeven_commission_per_contract_per_trade | placebo_fill_rate | placebo_profit_pc | real_minus_placebo | diff_ci_lo | diff_ci_hi |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5 | settle | 2449 | 11 | 0.0045 | 11 | 5 | 0.0400 | 0.0300 | -0.3882 | 0.4479 | nan | 0.0300 | 0.0013 | -0.0416 | 0.0716 | -0.3078 | 0.4545 |
| 5 | t60 | 2449 | 11 | 0.0045 | 11 | 5 | -0.0845 | -0.1045 | -0.1767 | -0.0133 | nan | -0.0523 | 0.0013 | -0.0543 | -0.0502 | -0.1250 | 0.0541 |
| 30 | settle | 2449 | 164 | 0.0670 | 164 | 13 | -0.0064 | -0.0164 | -0.0917 | 0.0571 | -0.1072 | -0.0164 | 0.0561 | -0.0252 | 0.0088 | -0.0628 | 0.0856 |
| 30 | t60 | 2449 | 164 | 0.0670 | 153 | 13 | -0.0328 | -0.0528 | -0.0732 | -0.0338 | -0.0613 | -0.0264 | 0.0561 | -0.0427 | -0.0101 | -0.0305 | 0.0061 |

What it shows:
- Fills are rare: 0.45% of attempts within 5 s and 6.7% within 30 s (placebo 0.13% and 5.6%), as expected from a
  strict trade-through rule (a lower bound on fills).
- W = 5 s: 11 fills in 5 games, far too few to say anything (settlement +3.0 c [-38.8, +44.8]).
- W = 30 s: 164 fills in 13 games. Held to settlement -1.6 c per contract [-9.2, +5.7] after the CME fee; the 60 s
  exit -5.3 c [-7.3, -3.4]. Real minus placebo +0.9 c [-6.3, +8.6] (settlement) and -1.0 c [-3.1, +0.6] (60 s).
- Break-even broker commission is negative in every cell with enough fills, i.e. no commission level makes it
  profitable. Maker fills on CME, like maker fills on Kalshi, come when the market is about to move against the
  order.
