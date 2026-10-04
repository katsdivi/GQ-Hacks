"""Fee lines from docs/research/fees.md."""
import numpy as np
import pandas as pd
import pytest

import costs


def test_kalshi_webull_is_two_cents_per_contract():
    assert costs.fee(0.5, 10, "buy", "kalshi") == pytest.approx(0.20)
    assert costs.fee(0.9, 10, "sell", "kalshi", route="webull") == pytest.approx(0.20)


def test_kalshi_direct_rounds_up_per_order():
    # 0.07 * 10 * 0.5 * 0.5 = 0.175 -> 0.18
    assert costs.fee(0.5, 10, "buy", "kalshi", route="direct") == pytest.approx(0.18)
    # 0.07 * 1 * 0.9 * 0.1 = 0.0063 -> 0.01
    assert costs.fee(0.9, 1, "buy", "kalshi", route="direct") == pytest.approx(0.01)


# polymarket.com: 5 decimal places, no cent ceiling. Hand-derived, C = 10: 0.05 x 10 x P x (1 - P).
@pytest.mark.parametrize("p, want", [(0.10, 0.045), (0.50, 0.125), (0.85, 0.06375)])
def test_polymarket_com_five_decimals_no_cent_ceiling(p, want):
    assert costs.fee(p, 10, "buy", "polymarket") == want
    assert costs.fee(p, 10, "sell", "polymarket") == want


def test_polymarket_com_exact_cent_and_tiny_fee():
    assert costs.fee(0.2, 100, "buy", "polymarket") == 0.80          # 0.05 * 100 * 0.2 * 0.8
    assert costs.fee(0.01, 1, "buy", "polymarket") == 0.0005          # 0.05 * 0.01 * 0.99 = 0.000495 -> 0.0005
    assert costs.fee(0.99, 1, "buy", "polymarket") == 0.0005


# Polymarket US: 0.0695 x C x P x (1 - P), banker's rounding to the cent, per order, from 2026-10-01 14:00 UTC.
AFTER = pd.Timestamp("2026-10-03 18:00", tz="UTC")


@pytest.mark.parametrize("p, want", [(0.10, 0.06),     # raw 0.06255
                                     (0.50, 0.17),     # raw 0.17375
                                     (0.85, 0.09)])    # raw 0.0886125
def test_polymarket_us_hand_derived_c10(p, want):
    assert costs.fee(p, 10, "buy", "polymarket_us", ts=AFTER) == want


def test_polymarket_us_doc_examples():
    assert costs.fee(0.50, 100, "buy", "polymarket_us", ts=AFTER) == 1.74     # raw 1.7375 (fee page maximum)
    assert costs.fee(0.50, 1000, "buy", "polymarket_us", ts=AFTER) == 17.38   # raw 17.375, half to even (8)


def test_polymarket_us_half_even_ties():
    # C = 120, P = 0.50: raw exactly 2.085 -> 2.08 (half to even; half up would give 2.09)
    assert costs.fee(0.50, 120, "buy", "polymarket_us", ts=AFTER) == 2.08
    # C = 40, P = 0.50: raw exactly 0.695 -> 0.70 (even digit is up here)
    assert costs.fee(0.50, 40, "buy", "polymarket_us", ts=AFTER) == 0.70


def test_polymarket_us_effective_time_gate():
    eff_ns = int(pd.Timestamp("2026-10-01 14:00", tz="UTC").value)
    assert costs.fee(0.5, 10, "buy", "polymarket_us", ts=eff_ns) == 0.17                  # int ns, at the boundary
    assert costs.fee(0.5, 10, "buy", "polymarket_us", ts=np.int64(eff_ns)) == 0.17
    assert costs.fee(0.5, 10, "buy", "polymarket_us", ts="2026-10-01 10:00-04:00") == 0.17  # 10 AM ET
    for bad in (eff_ns - 1, "2026-10-01 09:59:59-04:00", pd.Timestamp("2025-11-16", tz="UTC")):
        with pytest.raises(ValueError):
            costs.fee(0.5, 10, "buy", "polymarket_us", ts=bad)
    with pytest.raises(ValueError):
        costs.fee(0.5, 10, "buy", "polymarket_us")                                         # no timestamp


def test_unknown_venue_raises():
    with pytest.raises(ValueError):
        costs.fee(0.5, 1, "buy", "nyse")


def test_label_has_no_placeholder():
    assert "PLACEHOLDER" not in costs.FEE_LABEL
    assert "as if traded today" in costs.FEE_LABEL


def test_backtest_kalshi_route_switch():
    import pandas as pd
    from legacy import backtest
    sig = pd.DataFrame([{"entry_g": 0, "exit_g": 5, "direction": 1, "qty": 10, "exit_reason": "gap_closed",
                         "entry_decision_ns": 1_000_000_000, "exit_decision_ns": 6_000_000_000,
                         "gap_at_entry_cents": 3.0}])
    q = pd.DataFrame({"ts": [0, 5_000_000_000], "bid": [0.49, 0.54], "ask": [0.51, 0.56]})
    web = backtest.simulate(sig, q, q, "kalshi", 0.0)
    direct = backtest.simulate(sig, q, q, "kalshi", 0.0, kalshi_route="direct")
    assert web["fees"].iloc[0] == pytest.approx(0.40)              # 2 fills x 10 x $0.02
    assert direct["fees"].iloc[0] == pytest.approx(0.18 + 0.18)   # ceil(0.07*10*0.51*0.49), ceil(0.07*10*0.54*0.46)


def test_polymarket_comparison_rate_override():
    assert costs.fee(0.5, 10, "buy", "polymarket", polymarket_rate=0.03) == 0.075
    assert costs.fee(0.5, 10, "buy", "polymarket", polymarket_rate=0.0) == 0.0


# C = 100: float 0.07 * C * P * (1 - P) carries noise above the exact cent value, so a plain float ceil charges
# one cent too much (e.g. 1.7500000000000002 -> 1.76). Exact values by hand: 7 x P x (1 - P) dollars.
FLOAT_NOISE = {0.10: 0.63, 0.20: 1.12, 0.40: 1.68, 0.50: 1.75, 0.60: 1.68, 0.70: 1.47, 0.80: 1.12}


@pytest.mark.parametrize("p", sorted(FLOAT_NOISE))
def test_direct_fee_no_float_ceil_overcharge(p):
    import math
    assert math.ceil(0.07 * 100 * p * (1 - p) * 100) / 100 == pytest.approx(FLOAT_NOISE[p] + 0.01)  # the trap
    assert costs.fee(p, 100, "buy", "kalshi", route="direct") == FLOAT_NOISE[p]


def test_half_cent_fill_prices_exact():
    # backtest trades-only fills are trade price +/- HALF_SPREAD 0.005: 0.07 * 10 * 0.505 * 0.495 = 0.1749825 -> 0.18
    assert costs.fee(0.505, 10, "buy", "kalshi", route="direct") == 0.18
    # 0.05 * 100 * 0.495 * 0.505 = 1.249875 -> 1.24988 (5 decimals, the 6th digit is exactly 5: half up)
    assert costs.fee(0.495, 100, "buy", "polymarket") == 1.24988
    # 0.0695 * 10 * 0.505 * 0.495 = 0.17373... -> 0.17
    assert costs.fee(0.505, 10, "buy", "polymarket_us", ts=AFTER) == 0.17


def _ref_units(num: int, den: int, scale: int, mode: str) -> int:
    """Integer reference: round num/den dollars to 1/scale dollar units. No Decimal, no float."""
    q, r = divmod(num * scale, den)
    if mode == "ceil":
        return q + (r > 0)
    if mode == "half_up":
        return q + (2 * r >= den)
    if mode == "half_even":
        return q + (2 * r > den or (2 * r == den and q % 2 == 1))
    raise ValueError(mode)


def test_reference_grid_all_four_schedules():
    """19,900 cases per schedule: prices 0.005..0.995 in half cents (199) x C = 1..100. The earlier 59,700-case
    check was these 19,900 x 3 schedules; with Polymarket US added: 19,900 x 4 = 79,600. Price in 1/1000 dollars: raw = rate_num * C * pm * (1000 - pm) /
    (rate_den * 10**6)."""
    rated = [("kalshi", {"route": "direct"}, 7, 100, 100, "ceil"),
             ("polymarket", {}, 5, 100, 10**5, "half_up"),
             ("polymarket_us", {"ts": AFTER}, 695, 10000, 100, "half_even")]
    n = 0
    for pm in range(5, 1000, 5):
        p = pm / 1000
        for c in range(1, 101):
            assert costs.fee(p, c, "buy", "kalshi") == pytest.approx(0.02 * c, abs=1e-12)
            n += 1
            for venue, kw, rn, rd, scale, mode in rated:
                want = _ref_units(rn * c * pm * (1000 - pm), rd * 10**6, scale, mode) / scale
                assert costs.fee(p, c, "buy", venue, **kw) == want, (venue, p, c)
                n += 1
    assert n == 4 * 19_900
