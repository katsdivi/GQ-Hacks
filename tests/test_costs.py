"""Fee lines from docs/research/fees.md."""
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


def test_polymarket_rounds_up_per_order():
    # 0.05 * 10 * 0.5 * 0.5 = 0.125 -> 0.13
    assert costs.fee(0.5, 10, "buy", "polymarket") == pytest.approx(0.13)
    # exact cent stays: 0.05 * 100 * 0.2 * 0.8 = 0.80
    assert costs.fee(0.2, 100, "buy", "polymarket") == pytest.approx(0.80)


def test_unknown_venue_raises():
    with pytest.raises(ValueError):
        costs.fee(0.5, 1, "buy", "nyse")


def test_label_has_no_placeholder():
    assert "PLACEHOLDER" not in costs.FEE_LABEL
    assert "as if traded today" in costs.FEE_LABEL


def test_backtest_kalshi_route_switch():
    import pandas as pd
    import backtest
    sig = pd.DataFrame([{"entry_g": 0, "exit_g": 5, "direction": 1, "qty": 10, "exit_reason": "gap_closed",
                         "entry_decision_ns": 1_000_000_000, "exit_decision_ns": 6_000_000_000,
                         "gap_at_entry_cents": 3.0}])
    q = pd.DataFrame({"ts": [0, 5_000_000_000], "bid": [0.49, 0.54], "ask": [0.51, 0.56]})
    web = backtest.simulate(sig, q, q, "kalshi", 0.0)
    direct = backtest.simulate(sig, q, q, "kalshi", 0.0, kalshi_route="direct")
    assert web["fees"].iloc[0] == pytest.approx(0.40)              # 2 fills x 10 x $0.02
    assert direct["fees"].iloc[0] == pytest.approx(0.18 + 0.18)   # ceil(0.07*10*0.51*0.49), ceil(0.07*10*0.54*0.46)


def test_polymarket_comparison_rate_override():
    assert costs.fee(0.5, 10, "buy", "polymarket", polymarket_rate=0.03) == pytest.approx(0.08)  # 0.075 -> 0.08
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
    # 0.05 * 100 * 0.495 * 0.505 = 1.2498750 -> 1.25
    assert costs.fee(0.495, 100, "buy", "polymarket") == 1.25
