# Webull risk controls (Strategy A paper orders)

What the code applies today, with the line that applies it. Paper trading only (CLAUDE.md rule 6). The final holdout run does not import `execution/webull.py`; all reported A numbers come from the simulation in `strategy_a.py`.

## Applied in the simulation (`strategy_a.py`, every reported A number)

| Control | What it does | Where |
|---|---|---|
| Fixed size | 10 contracts per trade, never scaled | `QTY = 10` |
| One entry per game | one decision at kickoff - 5 min, favorite leg only; no adds, no exits before settlement | `decide`, `_leg` |
| Theta filter | enter only if the favorite's as-of price >= 0.80 (selected on training) | `_leg` |
| Skip: no pre-decision price | skip if either team market has no trade at or before t | `decide` |
| Skip: stale | skip if either team market has no trade in (t - 10 min, t] | `decide`, `STALE_S` |
| Skip: no favorite | skip if both as-of prices are equal | `decide` |
| Skip: no post-decision trade | skip if no trade in [t + 1 s, t + 5 min] (no fill assumed without a print) | `first_fill`, `FILL_WINDOW_S` |
| Skip: unsettled | skip if the market has no settlement result | `_leg` |
| Skip: missing market, non-ESPN kickoff | skip games without both team markets or without an ESPN kickoff | `load_games`, `KICKOFF_SOURCES` |
| Fill cap | fill price = first trade + 1 c, capped at 1 - tick of that market (1.00 is not a valid Kalshi price) | `fill_cap`, `_leg` |
| Latency | fills only from trades at or after t + 1 s | `LATENCY_S` |
| Costs always charged | Webull $0.02 per contract (primary); Kalshi direct 0.07 x C x P x (1 - P) rounded up (comparison) | `fee_webull`, `fee_kalshi_direct` |
| Holdout seal | games with kickoff >= 2026-08-01 refused unless run with the final-test flag | `SEAL`, `evaluate_game(final_test=...)` |

## Applied in the order path (`execution/webull.py`, tested in `tests/test_webull.py`, 9 tests)

| Control | What it does | Where |
|---|---|---|
| Dry run by default | `WebullPaper(dry_run=True)`: no network; logs the exact payload, returns status `dry_run_not_sent`, never reports a fill | `WebullPaper.dry_run`, `place_paper_order` |
| Sandbox host only | any host other than `api.sandbox.webull.com` raises at construction | `__post_init__` |
| Order validation | quantity must be a positive whole number; limit price must be 0.01 to 0.99 (rounded to the cent); otherwise the order is refused before sending | `build_payload` |
| Limit IOC only | every order is a LIMIT buy, time in force IOC (no resting orders, no market orders) | `build_payload` |
| Own market, yes side | buys the favorite's own Kalshi market, outcome "yes" | `build_payload`, `event_outcome` |
| Rate limit | at most 30 requests in any 60 s window (blocks before sending) | `RateLimiter` |
| No inferred fills | fills come only from the venue's order detail, never assumed | `order_status` |
| Keys from env only | `WEBULL_APP_KEY`, `WEBULL_APP_SECRET`, `WEBULL_ACCOUNT_ID` read from the environment; never printed, logged or written; missing keys raise without printing | `_sdk_trade_client` |
| Unique order ids | `client_order_id` is a fresh UUID per order (no accidental duplicate submits) | `place_paper_order` |
| Order log | every order (sent or dry run) appended to `out/webull_orders.jsonl` (gitignored) | `_log` |

Note: the order path takes `qty` and `limit_price` from the caller. The 10-contract size and the 1 - tick cap are enforced in the simulation, not inside `webull.py`; a caller could pass another quantity.

## Before live trading we would add (NOT implemented)

- **State gating.** No code checks the user's state. Kalshi event contracts through Webull are not offered in some states; Divi's list is NV, MD, CT, MI. That list is not sourced in this repo (unverified here); it needs a first-party Webull or Kalshi source and a hard block before any order.
- **Size and price limits inside the order path.** Enforce QTY = 10 and the 1 - tick cap in `webull.py` itself, not only in the simulation.
- **Daily and per-game loss limits, max open exposure.** None exist; A holds to settlement with no stop.
- **Kill switch.** No global halt flag or file checked before each order.
- **Duplicate-signal guard.** No check that a game already has an order (unique ids prevent duplicate submits of one call, not two calls for one game).
- **Reconciliation.** No job that compares the order log with the venue's order details and positions.
- **Sandbox behaviour checks.** IOC for EVENT orders is not shown in the SDK sample (it uses DAY); to confirm with Andrew in the sandbox.
- **Fee confirmation.** Webull's $0.02 per contract and Kalshi's maker fee are not confirmed first-party for live use (docs/research/fees.md; v3 Amendment 5).
- **Market-hours and halt checks.** No check that the market is open and not halted before sending.
