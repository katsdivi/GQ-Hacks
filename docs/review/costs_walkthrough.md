# costs.py walkthrough (Rule-7 review packet)

File: costs.py at b632053 (branch t15-final), 112 lines. Used by the run through laggard.py (costs.fee, polymarket.com and Polymarket US fills). Strategy A and B use their own Kalshi fee functions (strategy_a.fee_webull / fee_kalshi_direct), which tests/test_strategy_a_fees.py checks equal to this file.

Tags at line end: **[TIME]** touches decision time, fill time, windows, outages or timestamps. **[MONEY]** touches price, fee, spread, threshold or P&L. Tests per block: every test that calls a function defined in the block.

## Lines 1 to 21

Module docstring: the four schedules (Webull $0.02/contract/fill; Kalshi direct 0.07 C P(1-P) rounded up; polymarket.com 0.05 C P(1-P) to 5 decimals; Polymarket US 0.0695 C P(1-P) banker's-rounded to the cent from 2026-10-01 14:00 UTC), applied to every game as if traded today.

```python
  1  """Trading costs from Andrew's fee research (docs/research/fees.md).
  2
  3  Costs as if traded today: the current schedules are applied to every game, including games
  4  played before the schedules took effect.
  5
  6    Kalshi via Webull (primary):     $0.02 per contract per fill                                                       [TIME] [MONEY]
  7    Kalshi direct taker (comparison): 0.07 x C x P x (1 - P), rounded UP to the cent per order                         [MONEY]
  8    polymarket.com taker:            0.05 x C x P x (1 - P), rounded to 5 decimal places (no cent ceiling)             [MONEY]
  9                                     (docs.polymarket.com/trading/fees, checked 2026-10-03)                            [TIME] [MONEY]
 10    Polymarket US taker:             0.0695 x C x P x (1 - P), rounded to the nearest $0.01 with banker's              [TIME] [MONEY]
 11                                     rounding (half to even), per order. Effective 2026-10-01 10:00 ET                 [TIME]
 12                                     (14:00 UTC); any earlier timestamp raises. Taker only: we never post,             [MONEY]
 13                                     so the maker rebate never applies (docs.polymarket.us/fees, checked 2026-10-03)
 14
 15  C = contracts in the order, P = fill price in dollars. Kalshi direct rounding up per order is the
 16  conservative reading; Kalshi's exact rounding is unconfirmed (open question in fees.md).
 17
 18  Spread: trades-only history has no book, so fills are trade price plus or minus HALF_SPREAD                          [MONEY]
 19  (PROVISIONAL, pre-spec; Alden to confirm).                                                                           [MONEY]
 20  """
 21  from __future__ import annotations
```

Tests: none (constants/docstring)

## Lines 22 to 46

Imports and constants: order size 10, Webull route by default, the four rates, the Polymarket US effective time, the provisional 0.5 cent half-spread, the label printed with every result, and the two rounding quanta (cent, 5 decimals).

```python
 22
 23  import numbers
 24  from decimal import ROUND_CEILING, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
 25
 26  import pandas as pd
 27
 28  ORDER_SIZE = 10                  # contracts per signal (default; part of the frozen stats plan)                [MONEY]
 29  KALSHI_ROUTE = "webull"          # primary; "direct" is the comparison line
 30  WEBULL_PER_CONTRACT = 0.02       # dollars per contract per fill                                                [MONEY]
 31  KALSHI_DIRECT_RATE = 0.07        # schedule effective 2026-07-07                                                [MONEY]
 32  POLYMARKET_RATE = 0.05           # polymarket.com (international) sports taker rate                             [MONEY]
 33  POLYMARKET_US_RATE = 0.0695      # Polymarket US taker theta                                                    [MONEY]
 34  POLYMARKET_US_EFFECTIVE = pd.Timestamp("2026-10-01 14:00", tz="UTC")   # 10:00 ET (EDT, UTC-4)                  [TIME]
 35  HALF_SPREAD = 0.005              # dollars. PROVISIONAL (pre-spec), used only when no book exists.              [MONEY]
 36
 37  FEE_LABEL = ("costs as if traded today: Kalshi via Webull $0.02/contract/fill "
 38               "(Kalshi direct 0.07*C*P*(1-P) rounded up as comparison); polymarket.com 0.05*C*P*(1-P) "
 39               "rounded to 5 decimals; Polymarket US 0.0695*C*P*(1-P) banker's-rounded to the cent per order, "
 40               "from 2026-10-01 14:00 UTC")
 41
 42
 43  CENT = Decimal("0.01")                                                                                          [MONEY]
 44  FIVE_DP = Decimal("0.00001")                                                                                    [MONEY]
 45
 46
```

Tests: none (constants/docstring)

## Lines 47 to 71

Exact-decimal helpers: prices and rates rounded to 4 decimals then converted to Decimal (no float noise); raw fee rate x C x P x (1 - P); Kalshi direct rounded UP to the cent; polymarket.com rounded to 5 decimals (half up, our assumption).

```python
 47  def _dec(x: float) -> Decimal:                                                                                    [MONEY]
 48      """Exact decimal of a price or rate. Fill prices are on a 1/10000 dollar grid (cents, or cents plus or
 49      minus the half-cent HALF_SPREAD), so rounding the float to 4 places recovers the intended value exactly."""
 50      return Decimal(str(round(float(x), 4)))                                                                       [MONEY]
 51
 52
 53  def _raw_fee(rate: float, qty: float, price: float) -> Decimal:                                                   [MONEY]
 54      """rate x C x P x (1 - P) in exact decimal arithmetic (no float noise)."""
 55      p = _dec(price)                                                                                               [MONEY]
 56      return _dec(rate) * _dec(qty) * p * (1 - p)                                                                   [MONEY]
 57
 58
 59  def _rate_fee(rate: float, qty: float, price: float) -> float:                                                    [MONEY]
 60      """Kalshi direct: raw fee rounded UP to the cent per order.
 61      Float ceil would overcharge on noise (0.07 * 100 * 0.5 * 0.5 = 1.7500000000000002 -> 1.76)."""
 62      return float(_raw_fee(rate, qty, price).quantize(CENT, rounding=ROUND_CEILING))                               [MONEY]
 63
 64
 65  def _polymarket_com_fee(rate: float, qty: float, price: float) -> float:                                          [MONEY]
 66      """polymarket.com: "Fees are rounded to 5 decimal places. The smallest fee charged is 0.00001 USDC."
 67      The docs do not state the rounding direction; ROUND_HALF_UP is our assumption (it only matters when the
 68      6th decimal onward is exactly 5)."""
 69      return float(_raw_fee(rate, qty, price).quantize(FIVE_DP, rounding=ROUND_HALF_UP))                            [MONEY]
 70
 71
```

Tests: `test_costs.py::test_direct_fee_no_float_ceil_overcharge (via fee)`, `test_costs.py::test_half_cent_fill_prices_exact (via fee)`, `test_costs.py::test_kalshi_direct_rounds_up_per_order (via fee)`, `test_costs.py::test_kalshi_webull_is_two_cents_per_contract (via fee)`, `test_costs.py::test_polymarket_com_exact_cent_and_tiny_fee (via fee)`, `test_costs.py::test_polymarket_com_five_decimals_no_cent_ceiling (via fee)`, `test_costs.py::test_polymarket_comparison_rate_override (via fee)`, `test_costs.py::test_polymarket_us_doc_examples (via fee)`, `test_costs.py::test_polymarket_us_effective_time_gate (via fee)`, `test_costs.py::test_polymarket_us_half_even_ties (via fee)`, `test_costs.py::test_polymarket_us_hand_derived_c10 (via fee)`, `test_costs.py::test_reference_grid_all_four_schedules (via fee)`, `test_costs.py::test_unknown_venue_raises (via fee)`, `test_laggard.py::test_polymarket_us_has_no_delay_and_cent_fees (via fee)`

## Lines 72 to 83

Polymarket US fee: requires the fill timestamp, refuses fills before the schedule's effective time, rounds to the cent with banker's rounding.

```python
 72  def _polymarket_us_fee(qty: float, price: float, ts) -> float:                                                      [TIME] [MONEY]
 73      """Polymarket US taker: 0.0695 x C x P x (1 - P), nearest cent, banker's rounding (half to even), per order.
 74      ts: fill time (int UTC ns, or anything pd.Timestamp accepts). Raises before the schedule's effective time."""   [TIME]
 75      if ts is None:                                                                                                  [TIME]
 76          raise ValueError("Polymarket US fee needs the fill timestamp (schedule effective 2026-10-01 14:00 UTC)")    [TIME]
 77      t = pd.Timestamp(int(ts), unit="ns") if isinstance(ts, numbers.Integral) else pd.Timestamp(ts)                  [TIME]
 78      t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")                                           [TIME]
 79      if t < POLYMARKET_US_EFFECTIVE:                                                                                 [TIME]
 80          raise ValueError(f"no Polymarket US fee schedule before {POLYMARKET_US_EFFECTIVE} (fill at {t})")           [TIME]
 81      return float(_raw_fee(POLYMARKET_US_RATE, qty, price).quantize(CENT, rounding=ROUND_HALF_EVEN))                 [MONEY]
 82
 83
```

Tests: `test_costs.py::test_direct_fee_no_float_ceil_overcharge (via fee)`, `test_costs.py::test_half_cent_fill_prices_exact (via fee)`, `test_costs.py::test_kalshi_direct_rounds_up_per_order (via fee)`, `test_costs.py::test_kalshi_webull_is_two_cents_per_contract (via fee)`, `test_costs.py::test_polymarket_com_exact_cent_and_tiny_fee (via fee)`, `test_costs.py::test_polymarket_com_five_decimals_no_cent_ceiling (via fee)`, `test_costs.py::test_polymarket_comparison_rate_override (via fee)`, `test_costs.py::test_polymarket_us_doc_examples (via fee)`, `test_costs.py::test_polymarket_us_effective_time_gate (via fee)`, `test_costs.py::test_polymarket_us_half_even_ties (via fee)`, `test_costs.py::test_polymarket_us_hand_derived_c10 (via fee)`, `test_costs.py::test_reference_grid_all_four_schedules (via fee)`, `test_costs.py::test_unknown_venue_raises (via fee)`, `test_laggard.py::test_polymarket_us_has_no_delay_and_cent_fees (via fee)`

## Lines 84 to 112

fee(): dispatch by venue (Kalshi route webull or direct; polymarket.com with an optional comparison rate; Polymarket US with ts; CME fake game charged the Webull line); any other venue raises.

```python
 84  def fee(price: float, qty: float, side: str, venue: str, route: str | None = None,                               [MONEY]
 85          polymarket_rate: float | None = None, ts=None) -> float:                                                 [TIME]
 86      """Fee in dollars for one order of qty contracts filled at price.
 87
 88      venue "kalshi": route "webull" (default, KALSHI_ROUTE) or "direct".
 89      venue "polymarket": polymarket.com taker schedule; primary rate 0.05 flat, 5-decimal rounding.
 90        polymarket_rate overrides it for the comparison line (per-market feeSchedule.rate listed on 2026-10-03).
 91      venue "polymarket_us": Polymarket US taker schedule; ts (fill time) required, raises before                  [TIME]
 92        2026-10-01 14:00 UTC.                                                                                      [TIME]
 93      venue "cme": fake game only, charged the Webull line. Any other venue raises.
 94      side is accepted for the fixed signature; current schedules are symmetric.
 95      """
 96      c, p = abs(qty), float(price)                                                                                [MONEY]
 97      if venue == "kalshi":
 98          r = route or KALSHI_ROUTE
 99          if r == "webull":
100              return WEBULL_PER_CONTRACT * c                                                                       [MONEY]
101          if r == "direct":
102              return _rate_fee(KALSHI_DIRECT_RATE, c, p)                                                           [MONEY]
103          raise ValueError(f"unknown Kalshi route {r!r}")
104      if venue == "polymarket":
105          rate = POLYMARKET_RATE if polymarket_rate is None else polymarket_rate                                   [MONEY]
106          return _polymarket_com_fee(rate, c, p)                                                                   [MONEY]
107      if venue == "polymarket_us":
108          return _polymarket_us_fee(c, p, ts)                                                                      [TIME] [MONEY]
109      if venue == "cme":
110          # Fake game only (CME is not a trading venue in this project): charge the Webull line.
111          return WEBULL_PER_CONTRACT * c                                                                           [MONEY]
112      raise ValueError(f"no fee schedule for venue {venue!r}")
```

Tests: `test_costs.py::test_direct_fee_no_float_ceil_overcharge`, `test_costs.py::test_half_cent_fill_prices_exact`, `test_costs.py::test_kalshi_direct_rounds_up_per_order`, `test_costs.py::test_kalshi_webull_is_two_cents_per_contract`, `test_costs.py::test_polymarket_com_exact_cent_and_tiny_fee`, `test_costs.py::test_polymarket_com_five_decimals_no_cent_ceiling`, `test_costs.py::test_polymarket_comparison_rate_override`, `test_costs.py::test_polymarket_us_doc_examples`, `test_costs.py::test_polymarket_us_effective_time_gate`, `test_costs.py::test_polymarket_us_half_even_ties`, `test_costs.py::test_polymarket_us_hand_derived_c10`, `test_costs.py::test_reference_grid_all_four_schedules`, `test_costs.py::test_unknown_venue_raises`, `test_laggard.py::test_polymarket_us_has_no_delay_and_cent_fees`

## Where a lookahead could hide, and why each is safe

1. **The Polymarket US effective-time gate (lines 77 to 80).** The fee is chosen by the FILL timestamp passed in, not the decision time or the current clock, so a fill is charged the schedule in force when it happened, and a pre-schedule fill raises instead of silently using a later schedule. Every holdout recording (from the evening of 2026-10-02) is after 2026-10-01 14:00 UTC, so no holdout fill reaches the raise; a training-period fill on Polymarket US would raise rather than be charged a later schedule. Test: `test_polymarket_us_effective_time_gate`.

2. **"Costs as if traded today" (lines 3 to 4, 28 to 33).** Training games (2025 season) are charged the schedules of 2026-10-03, not the fees in force at the time. This is a deliberate, disclosed anachronism, and conservative for the sports rates (polymarket.com sports fees were 0 or 0.03 earlier; 0.05 is the documented maximum). It cannot make a past trade look better than it was. No price is read from the future.

3. **The comparison-rate override (lines 89 to 90, 105).** The polymarket.com comparison line uses each market's feeSchedule.rate as listed on 2026-10-03, which is later information for training games. It only feeds the comparison line, never the primary number or any selection. Test: `test_polymarket_comparison_rate_override`.

## Points for your line-by-line review (choices to confirm)

- Line 50: prices and rates are rounded to 4 decimals before Decimal. Correct for the cent grid and half-cent fills (`test_half_cent_fill_prices_exact`); a price with more than 4 decimals would be silently rounded.
- Line 62: Kalshi direct rounds UP per order. Kalshi's exact rounding is unconfirmed (open question in docs/research/fees.md); up is the conservative reading.
- Line 69: polymarket.com rounding direction is not documented; HALF_UP is an assumption (matters only when the 6th decimal onward is exactly 5).
- Lines 96 and 94: `side` is unused (current schedules are symmetric); `qty` is taken as abs(qty).
- Line 100: Webull is $0.02 per contract per FILL; Strategy A charges it on entry only (settlement is not a fill), B and the laggard on entry and exit.
- Lines 109 to 111: the CME branch exists only for the fake game.
