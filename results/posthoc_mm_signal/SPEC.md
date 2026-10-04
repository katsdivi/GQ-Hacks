# Post-hoc: Kalshi-signal market making on the slow venue

Label: post-hoc, exploratory; historical local files only; no API calls, no keys, no orders. Written and committed
before any real-data run. Divi's text is the authority; this file restates it and fixes the implementation details.

## Data (local only)

- polymarket.com: Oct 3 Vultr feed, data/vultr/data/live/polymarket/20261003 (top of book only, P(home), venue time
  src_ts_ns, receipt recv_ns; trade rows kind=trade with price, size, side, src_ts_ns). Windows: polymarket.com rows of
  `git show feadc99:data/live/holdout_windows.csv`, qualifying, vultr, no exclusion flags (as posthoc-idea11 windows()).
  Kalshi signal source for this test: the Kalshi home-market Vultr book in the same window, venue time, residue levels
  (0 < size < 0.01) removed (check-phantom ec2c401, posthoc-idea11). Instrument maps: data/live/holdout_maps.
  Settlement of the polymarket.com home token: cached Gamma files ../wt-idea11/data/pm_resolution/<condition>.json
  (written by posthoc-idea11, no new API call); if missing, Kalshi home settlement (data/holdout_raw/settlements.csv),
  counted. polymarket.com maker fee: no per-market fee data found in the repo; assumed 0 and stated.
  Taker delay: data/live/holdout_seconds_delay.csv (default 1 s if missing, counted).
- CME: 14 training games, map data-cme-train 6b484c6 (data/raw/cme_train_v2/map.csv), book data/raw/cme_train_v2/
  jan_mbp1.dbn.zst (top of book with sizes, ts_event venue time), trades data/raw/fg_cg_train_trades.parquet (ts_event,
  price, size). $1 contracts, 0.01 ticks. Kalshi trades: data/raw/kalshi_only and data/raw/cme_train_v2/kalshi (4
  substitute championship markets). Window [kickoff - 2 h, kickoff + 5 h] (as posthoc-kalshi-cme Stage 1).
  CME fee $0.01 per contract per trade (CME 25-466 Appendix D, cited in posthoc-kalshi-cme SPEC 657c5b6).
- Polymarket US: not testable (cached quotes only); skipped.

Reused (cited): posthoc-idea11 snapshots()/windows()/instrument maps (scripts/posthoc_idea11.py at 0487ebf);
posthoc-kalshi-cme kalshi_phome()/signals()/Book (scripts/kalshi_cme_stage1.py at e05f28c).

## Makers (the slow venue = polymarket.com or CME)

- Quote both sides at the current best bid and best ask (join, never improve), 10 contracts each. Re-quote when the
  best price on that side changes (the order moves to the new best price; for F2 the queue resets).
- Inventory limit +/- 50 contracts: stop quoting the side that would exceed it.
- (N) no-signal maker: never pulls.
- (S) signal maker: Kalshi signal = Kalshi move >= 3 c within 10 s (polymarket.com test: Kalshi Vultr book mid, venue
  time; CME test: Kalshi trade prices, signal time = trade timestamp, which is already ns/us precise so the "end of
  timestamp interval" adds nothing; 10 s refractory after a signal, as Stage 1). Kalshi up: pull our ask; Kalshi down:
  pull our bid. The pull is effective at t + L (L in {0.25, 1.0} s) and lasts until t + 10 s, then the side re-quotes.
- Kickoff cut [kickoff - 2 min, kickoff + 20 min]: no quotes, no fills.
- All prices in P(home) of the slow venue's home contract; Kalshi direction in the same P(home) terms. CME: each team
  contract is handled in its own YES terms (Kalshi direction flipped for the away contract).

## Fill rules (slow-venue trades at venue time)

- F1 strict trade-through: a live order fills (full remaining size, up to 10) only if a later slow-venue trade prints
  strictly through its price (bid: trade price < our bid; ask: trade price > our ask).
- F2 queue (CME only): at quote time we join behind the displayed size at our price (mbp-1 top size). Trades AT our
  price after our quote time reduce the queue ahead; once cumulative traded volume at our price exceeds the queue, the
  excess fills us (up to remaining size). A trade strictly through our price fills our remaining size.
- polymarket.com taker-delay rule: a taker trade at venue time tau was submitted at tau - delay; our quote is hit only
  if it was still live at tau (a pull effective before tau protects us).
- "Later": strictly after the order's placement time.

## P&L and metrics

- Per fill: side (+1 bought on our bid, -1 sold on our ask), price, qty, fee (CME $0.01 per contract; polymarket.com 0).
- (a) marked to the slow venue's mid at fill + 60 s: side x (mid(t+60) - price) x qty - fee.
- (b) held to settlement: side x (payout - price) x qty - fee.
- Adverse selection: side x (mid(t+10 s) - mid(t)) and side x (mid(t+60 s) - mid(t)), mid(t) just before the fill;
  negative = adverse.
- Main metric: P&L(S) - P&L(N) per game, game-bootstrap 95% CI (2,000 reps, seed 20261004), both P&L definitions.
- Per maker: fills, contracts, P&L per filled contract, adverse selection.

## Pre-fixed reading rule (Divi's, verbatim)

"makes sense" ONLY if S minus N is positive with CI above zero under F1, AND has the same sign under F2 (CME), AND S's
own P&L after costs is positive. Anything else: "does not make sense on this data". Applied per venue and latency on
the (a) +60 s mark (primary) and reported for (b).

## Variants

2 venues x 2 latencies (S) = 4 variants, plus the N baselines. Logged in LEDGER.md. No variants.csv writes.
Hard stop 08:20 ET: commit and push whatever exists.
