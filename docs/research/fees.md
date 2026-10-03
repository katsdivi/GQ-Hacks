# Fees (Andrew's research)

Source: Andrew's fee research, relayed by Divi on 2026-10-03. Sources named: Webull FAQ 11052; docs.polymarket.com/changelog; help.polymarket.com (trading fees). Kalshi direct schedule: Andrew (effective 2026-07-07).

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

## Source facts (Divi, 2026-10-03)

- Webull: $0.01 commission + $0.01 exchange fee per contract per side = $0.02 total. The Kalshi taker fee is NOT stacked on the Webull route. (Webull FAQ 11052)
- polymarket.com sports taker: shares x feeRate x p x (1 - p); feeRate 0.05 since 2026-07-10, 0.03 from 2026-03-30, 0 for NFL before then. Maker 0. (docs.polymarket.com/changelog, help.polymarket.com)
- Costs as if traded today are applied to all games. Note: 2025 NFL games actually had 0 polymarket.com fees.

## Live check of the polymarket.com fee rate (2026-10-03 ~05:25 UTC): NOT a flat 0.05

Read from the Gamma API (market fields `feeType`, `feeSchedule`) and the CLOB API (`GET /markets/{condition_id}` -> `taker_base_fee`, `GET /fee-rate?token_id=` -> `base_fee`).

| Open moneylines | feeSchedule.rate 0.03 (`sports_fees_nfl_cfb_oct26`) | rate 0.05 (`sports_fees_v3`) | rate 0 (`zero_fees`) |
|---|---|---|---|
| NFL, 59 markets (series 12185) | 43 | 0 | 16 |
| CFB, 100 markets (series 12756) | 2 | 4 | 94 |

- Example: Colts vs. Commanders (2026-10-04 13:30 UTC): feeType `zero_fees`, feeSchedule rate 0; CLOB taker_base_fee 1000, fee-rate base_fee 1000.
- `taker_base_fee` / `base_fee` = 1000 on every market checked (sports and non-sports), so it is not the effective rate; likely a signing cap in bps. The effective rate is per market in `feeSchedule.rate`.
- Non-sports for comparison: politics 0.04, economics 0.05.
- The schedule name `sports_fees_nfl_cfb_oct26` suggests a new NFL/CFB schedule at 0.03 for October 2026, which conflicts with "0.05 since 2026-07-10". STOPPED here for Divi's decision; costs.py still uses 0.05.
