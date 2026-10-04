# Audit of the Kalshi-leads-CME results (Stage 1 taker and Amendment 1 maker)

Written 2026-10-04 after Divi's question "are you sure about CME orders not filling on time and fills?".
Descriptive checks only; no new trials. Script: scripts/kalshi_cme_audit.py. Outputs (no prices):
audit_coverage.csv, audit_orientation.csv, audit_fill_bounds.csv. All numbers below are from that run.

## 1. Timestamps

- CME: every computation uses ts_event (CME venue/match time) for both MBP-1 book updates and trade prints; ts_recv
  is never used for decisions (kalshi_cme_stage1.Book and kalshi_cme_maker both convert ts_event). Databento's
  receive time minus venue time is small: median 0.51 ms (p90 10.8 ms) for MBP-1 and 0.67 ms (p90 10.7 ms) for
  trades, so ts_event is well behaved.
- Kalshi: the training files use Kalshi's own trade time (created_time from the Kalshi API, venue time). No receipt
  clock exists for training Kalshi trades.
- Clock offset between the venues cannot be measured directly on these games: there is no common event stamped by
  both. What can be measured is the price lead (leadlag2 R3: Kalshi leads CME by a median 4 s, CME follows Kalshi 3 c
  jumps in about 6.5 s), which mixes true lead and any clock offset.
- Sensitivity, CME times shifted by -2, -1, +1, +2 s against Kalshi (maker attempts, J 5 c): the strict fill rate
  stays 0.45 to 0.57% at W 5 s and 6.3 to 7.0% at W 30 s; the at-price upper bound stays 10.2 to 11.5% (5 s) and 25.2
  to 29.4% (30 s). A 1 to 2 s clock error does not change any fill count materially or any conclusion.

## 2. Fill rule: three bounds (J 5 c, real signals, shift 0; c per contract after the $0.01 CME fee per trade)

| W | attempts | (i) strict trade-through: fill rate, settle, 60 s exit | (ii) prints AT or through our price (upper bound, sized by print size): fill rate, settle, 60 s exit | (iii) queue estimate: fill rate |
|---|---|---|---|---|
| 5 s | 2,449 | 0.45%, +3.0 c (11 fills), -10.5 c | 10.4%, +2.7 c, -1.4 c | 0.00% |
| 30 s | 2,449 | 6.7%, -1.6 c, -5.3 c | 26.8%, +2.2 c, -2.6 c | 0.08% (2 fills) |

- (ii) is a true upper bound: it assumes we were first in the queue at a level where the displayed size is a median
  10,000 contracts, which we would not be.
- (iii) uses the displayed size at our level when we post (MBP-1 bid or ask size; MBP-10 adds nothing because our
  limit is at the best level, so MBP-1 already gives the queue at that level) as the queue ahead of us, and fills
  only if the volume printed at or through our price within W reaches queue + 10. The median queue ahead is 10,000
  contracts while prints are a median 30 to 66 contracts, so a back-of-queue order essentially never fills.
- Settlement P&L in (ii) is slightly positive (+2.2 to +2.7 c), but the 60 s exit is negative (-1.4 to -2.6 c), and
  (ii) overstates fills. The realistic case lies between (i) and (iii) on fills, i.e. very few. No bound changes the
  conclusion that there is no tradable maker edge. The settlement figures carry game-level noise (a handful of games
  decide them).

## 3. Data sanity

- Print activity: overall 2.2 CME prints per minute per contract in the window. Around signals, within 30 s: median
  1 print (p75 3, p90 5); 21% of attempts see ANY print within 5 s and 65% within 30 s. The tiny 5 s strict fill
  rate is mostly because the CME contract simply does not trade in most 5 s windows, not a code error.
- Coverage: MBP-1 and trades start and end together for every contract (audit_coverage.csv): from about kickoff -
  2 h (CHI/GB at kickoff - 1 h; LA at CAR at kickoff + 2.5 h, mid-game, as Opus A noted) to kickoff + 2.7 to 3.9 h,
  i.e. the end of the game. Not truncated.
- Orientation: for all 28 contracts the last CME print in the window is on the side of the actual result (winner
  0.68 to 0.99, loser 0.01 to 0.32; audit_orientation.csv). 28 of 28 consistent.
- Hand checks (5 random real attempts with at least one print within 30 s; full listing in the script output):
  1. LA at CAR, CAR contract, sell limit at the ask 0.62 (queue 1,500): 7 prints at 0.52 to 0.58, all below our ask,
     so none at or through: no fill under any rule.
  2. LA at SEA, LA contract, sell limit 0.32 (queue 25,000): prints at 0.31 and 0.27: below our ask: no fill.
  3. SF at PHI, SF contract, buy limit at the bid 0.21 (queue 1,500): 3 prints at 0.27, above our bid: no fill.
  4. LA at CHI, CHI contract, sell limit 0.46 (queue 25,000): 3 prints at exactly 0.46 (sizes 20, 125, 2): fills only
     under the at-price upper bound (ii); the queue estimate says no (147 printed vs 25,000 ahead).
  5. LA at CHI, CHI contract, sell limit 0.42 (queue 24,071): prints at exactly 0.42 (sizes 1, 1, 104): same as 4.
  Every case was classified correctly by the code. (The hand-check printout shows the Kalshi 10 s window as min ->
  last, which for a down move understates the range; the signal itself uses max - last.)

## 4. Size units

- CME Submission 25-466 (Appendix A, contract specs): contract size $1.00, prices in U.S. dollars and cents, tick
  0.01 = $0.01. So one CME contract has the same $1 payout as one Kalshi contract, and all c-per-contract figures are
  already in the right unit. No correction is needed.
- Databento MBP sizes are in contracts. Displayed top-of-book sizes are large round numbers (7,500 to 100,000, median
  10,000 to 15,000 at our level): market-maker quotes of $7,500 to $100,000 notional. Trade prints are small (median
  29 to 66 contracts, p90 144 to 714). That mismatch is real, and it is why the queue-based fill estimate is near
  zero.

## 5. Taker results recheck (Stage 1)

With units confirmed ($1 contracts) and orientation confirmed (28 of 28), the Stage 1 numbers stand. The entry pays a
median 2.5 c half-spread (mean 2.8 c) against the mid at t, and the 60 s round trip is a median -4.0 c gross,
-6 c after fees. Real minus placebo is positive (CME does follow Kalshi), but no cell is profitable after the spread.

## What changes

Nothing in the conclusions. No unit or orientation error. The clock-shift sensitivity leaves the fills unchanged.
The maker result depends on the fill model: under the generous at-price upper bound, settlement P&L is +2 to +3 c
per contract on 10 to 27% fills, but the 60 s exit is still negative. Realistic queue position (10,000+ contracts
ahead at the best level) implies almost no fills. The Kalshi-leads-CME signal is real but not tradable at retail
size on CME's top of book after the spread.
