# Post-hoc Kalshi leads, trade CME (two-stage test approved by Divi, 2026-10-04)

Label: descriptive, post-hoc, 14 games (Stage 1). Stage 2 is one out-of-sample run of one frozen rule (1 trial),
only if Stage 1 passes its gate. Written before any Stage 1 computation; the only prior knowledge is the descriptive
leadlag2 Round 3 result (branch posthoc-leadlag2 80e3613: on 10 of these games Kalshi leads CME, median lag -4 s, CME
responds to Kalshi 3 c jumps in about 6.5 s), which motivates this test.

## Data (Stage 1, training games only)

- Map: branch data-cme-train 6b484c6, results/data_cme/map.csv (ignored copy data/raw/cme_train_v2/map.csv). One row
  per CME "win" contract (symbol, team, game_id, kickoff). Games with both CME depth and Kalshi trades: 14.
- CME book: data/raw/cme_train_v2/jan_mbp1.dbn.zst (every top-of-book change, Databento MBP-1), read with
  databento.DBNStore.from_file(path).to_df(). Book state at a time T = the latest update with venue time ts_event <=
  T (bid_px_00, ask_px_00, bid_sz_00, ask_sz_00). Mid only when both sides exist.
- Kalshi: data/raw/kalshi_only/<game_id>.parquet (10 games) and data/raw/cme_train_v2/kalshi/<game_id>.parquet (4
  games from Jan 19 on, championship-series markets that pay as game winners). Prices P(ESPN home), venue time ts.
- Settlement: the game result (Kalshi settlement_result / market meta), which is also the CME contract's outcome
  (C0001 pays $1 if the team wins).
- CME fees: $0.01 per contract per CME Globex trade, $0.00 cash settlement fee, for all membership types including
  non-members: CME Submission 25-466, "Initial Listing of Event Contract Swaps on Pro Basketball Games, Pro Football
  Games, Pro Football Season Championship, and College Football Games", Appendix D "Exchange Fees",
  https://www.cftc.gov/sites/default/files/filings/ptc/25/11/ptc11192532737.pdf (filed 11/19/25). No separate
  clearing fee is listed there; FCM/broker commissions are NOT included and are stated as such. Contract size $1.

## Stage 1 (descriptive)

Signal (Kalshi leads): at each Kalshi trade time t (venue time) in [kickoff - 2 h, kickoff + 5 h], Kalshi P(home)
(last trade, either team market, oriented to home) compared with the min and max of Kalshi P(home) trades in
[t - 10 s, t]; a rise of >= J is an up signal (favours home), a fall of >= J a down signal (favours away). After a
signal, no new signal for 10 s (one signal per move). J in {3, 4, 5} c (3 c is Divi's stated signal; 4 and 5 c let
Stage 2 freeze "one threshold").

For each signal and each CME contract of that game (home team C0001 and away team C0001):
- direction: buy the contract of the team the Kalshi move favours (lift the CME ask); sell the other team's
  contract (hit the CME bid).
- CME mid at t (state at ts_event <= t) and at t + L, L in {1, 2, 5} s: "not moved" = the mid change in the signal
  direction is < 1 c.
- Executable at t + L: the needed side (ask to buy, bid to sell) exists with displayed size >= 1, AND the mid has not
  moved. Size = min(10, displayed size at t + L). Entry price = that ask (buy) or bid (sell).
- Exit (a): at t + 60 s, the opposite side (sell at bid / buy back at ask); if missing, the trade is counted as
  "no exit quote" and excluded from (a). Exit (b): hold to settlement ($1 or $0).
- Profit per contract = (exit - entry) for buys, (entry - exit) for sells, minus $0.01 per Globex trade (entry, and
  the exit trade in (a)); settlement fee $0.00.
- Report per (J, L, exit): signals, CME-contract signals, share not moved, executable share, mean displayed size,
  profit per contract with a game-bootstrap 95% CI (2,000, seed 20261004), total P&L, the same excluding the top 5
  games, and the placebo.
- Placebo: Kalshi signals from an unrelated game applied to the same CME contract at the same time since kickoff
  (game B's signal at kickoff_B + x, with B's home/away direction, applied to game A's home/away contracts at
  kickoff_A + x), every ordered pair A != B; same execution and exits.

## Gate and Stage 2 (frozen rule)

Selection rule (Divi's): among the 18 (J, L, exit) cells, the one with the best placebo-adjusted profit per contract
(real minus placebo, after CME fees) with >= 50 executable signals; if no cell has >= 50, stop.

Gate: Stage 2 runs only if the selected cell's real profit per contract after costs is > 0 AND the placebo is
clearly worse: the game-bootstrap 95% CI of (real minus placebo) profit per contract has a lower bound > 0. If the
gate fails, Stage 2 does not run and that is the result.

Stage 2 (only if the gate passes): commit the frozen rule (J, L, exit) with time BEFORE downloading any 2026 CME
data; print and log the Databento cost (session cap $60, $0.88 used), report it to the coordinator, pull, map to
the holdout-period Kalshi trades already on disk (data/holdout_raw/kalshi/), run once, commit unedited. Counts as 1
trial.

Stop at 08:00 ET whatever the state. No experiments/variants.csv writes. LEDGER.md logs every step.
