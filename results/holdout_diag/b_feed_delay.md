# b. Polymarket US feed delay (exploratory, post-run)

- Why receipt_diagnostic.csv has 0 rows for polymarket_us: holdout_mid.Machine.receipt_lags_s uses rows with a venue-side timestamp (src_ts_ns) and recv_ns. Every recorded Polymarket US row has src_ts_ns null (Vultr: 317,105 rows, 0 non-null), so there is nothing to subtract.
- Timestamp fields recorded per feed (parquet schema, identical columns): ts, recv_ns, src_ts_ns (plus tx_hash).
  - kalshi: src_ts_ns = Kalshi message timestamp (websocket).
  - polymarket (polymarket.com): src_ts_ns = the message's "timestamp" field (ms) on book and trade messages (collector/run.py:705, 718, 731).
  - polymarket_us: book only (bid/ask rows from the batch poll GET /v1/markets?slug=..., collector/run.py PolymarketUS.poll_batch / _rows). ts = recv = time.time_ns() taken after the HTTP response (ts == recv_ns in 99.96% of rows). No server or exchange timestamp is recorded; sizes are not recorded either (size null in all rows). There is no Polymarket US trade feed in the recordings (trades were planned from the daily Time & Sales files).
- Can any recorded data bound the delay? No. The collector records no request send time or round-trip time; the heartbeat only says the feed delivered a message (last_ok). A row's ts is the receipt time of the poll in which a quote change was first seen, so the quote may have changed at any time since the previous poll (about 1 s earlier) plus the unmeasured request latency.
- Not done: Polymarket US's public daily Time & Sales files (nanosecond execution times) for 2026-10-03 could give a lower-bound style check (trade prints vs first poll that shows the new quote). They are not on disk (data/raw/polymarket_us_tns has no holdout files) and were not downloaded.
