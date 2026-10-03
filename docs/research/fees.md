# Fees (Andrew's research)

Source: Andrew's fee research, relayed by Divi on 2026-10-03. The schedule effective dates below are the ones Andrew gave. The underlying source documents (Webull and Kalshi fee pages, Polymarket fee page) are not attached here yet; Andrew to add links.

| Venue / route | Formula per order | Rounding | Schedule effective | Role in the backtest |
|---|---|---|---|---|
| Kalshi via Webull | $0.02 per contract per fill | none | as of 2026-10-03 (Andrew) | primary |
| Kalshi direct, taker | 0.07 x C x P x (1 - P) | rounded UP to the cent per order (conservative; Kalshi's exact rounding unconfirmed) | 2026-07-07 | comparison line |
| polymarket.com, taker | 0.05 x C x P x (1 - P) | rounded UP to the cent per order | 2026-07-10 | the only polymarket.com schedule; venue to confirm: polymarket.com vs Polymarket US |

C = contracts in the order, P = fill price in dollars (0.01 to 0.99).

Rules for using these (from Divi, 2026-10-03):

- The current schedules are applied to ALL games, including games played before the effective dates. Every output labels this "costs as if traded today".
- Order size per signal is a parameter, default 10 contracts. It is part of the frozen stats plan.
- Fees enter the who-leads and tuning pipeline only. They are not used to re-run nfl_20251116_was_mia, and no alternative fee values are tried on it.

Open questions for Andrew:

1. Kalshi direct rounding: per order or per fill, and up or nearest cent.
2. Whether the polymarket.com 0.05 sports rate is the international venue's (polymarket.com) or Polymarket US's. Polymarket US's own fee page (effective 2026-10-01) lists taker theta 0.0695 and a maker rebate; see STATUS.md.
3. Links to each source page.
