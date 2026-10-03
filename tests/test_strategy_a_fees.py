"""strategy_a fee functions equal costs.fee on branch t9-costs (not merged yet).
The constants were first generated from t9-costs:costs.py at 6213f5d, then re-derived independently with
Decimal (0.07 x C x P x (1 - P), ROUND_CEILING to the cent; Webull 0.02 x C): all 114 entries agree, and
test_constants_match_decimal re-checks that here. When t9-costs is merged, replace the constants with direct
calls to costs.fee."""
import math
from decimal import ROUND_CEILING, Decimal

import pytest

import strategy_a as A

PS = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
CS = [1, 10, 100]
WEBULL = {(0.05, 1): 0.02, (0.05, 10): 0.2, (0.05, 100): 2.0, (0.1, 1): 0.02, (0.1, 10): 0.2, (0.1, 100): 2.0, (0.15, 1): 0.02, (0.15, 10): 0.2, (0.15, 100): 2.0, (0.2, 1): 0.02, (0.2, 10): 0.2, (0.2, 100): 2.0, (0.25, 1): 0.02, (0.25, 10): 0.2, (0.25, 100): 2.0, (0.3, 1): 0.02, (0.3, 10): 0.2, (0.3, 100): 2.0, (0.35, 1): 0.02, (0.35, 10): 0.2, (0.35, 100): 2.0, (0.4, 1): 0.02, (0.4, 10): 0.2, (0.4, 100): 2.0, (0.45, 1): 0.02, (0.45, 10): 0.2, (0.45, 100): 2.0, (0.5, 1): 0.02, (0.5, 10): 0.2, (0.5, 100): 2.0, (0.55, 1): 0.02, (0.55, 10): 0.2, (0.55, 100): 2.0, (0.6, 1): 0.02, (0.6, 10): 0.2, (0.6, 100): 2.0, (0.65, 1): 0.02, (0.65, 10): 0.2, (0.65, 100): 2.0, (0.7, 1): 0.02, (0.7, 10): 0.2, (0.7, 100): 2.0, (0.75, 1): 0.02, (0.75, 10): 0.2, (0.75, 100): 2.0, (0.8, 1): 0.02, (0.8, 10): 0.2, (0.8, 100): 2.0, (0.85, 1): 0.02, (0.85, 10): 0.2, (0.85, 100): 2.0, (0.9, 1): 0.02, (0.9, 10): 0.2, (0.9, 100): 2.0, (0.95, 1): 0.02, (0.95, 10): 0.2, (0.95, 100): 2.0}
DIRECT = {(0.05, 1): 0.01, (0.05, 10): 0.04, (0.05, 100): 0.34, (0.1, 1): 0.01, (0.1, 10): 0.07, (0.1, 100): 0.63, (0.15, 1): 0.01, (0.15, 10): 0.09, (0.15, 100): 0.9, (0.2, 1): 0.02, (0.2, 10): 0.12, (0.2, 100): 1.12, (0.25, 1): 0.02, (0.25, 10): 0.14, (0.25, 100): 1.32, (0.3, 1): 0.02, (0.3, 10): 0.15, (0.3, 100): 1.47, (0.35, 1): 0.02, (0.35, 10): 0.16, (0.35, 100): 1.6, (0.4, 1): 0.02, (0.4, 10): 0.17, (0.4, 100): 1.68, (0.45, 1): 0.02, (0.45, 10): 0.18, (0.45, 100): 1.74, (0.5, 1): 0.02, (0.5, 10): 0.18, (0.5, 100): 1.75, (0.55, 1): 0.02, (0.55, 10): 0.18, (0.55, 100): 1.74, (0.6, 1): 0.02, (0.6, 10): 0.17, (0.6, 100): 1.68, (0.65, 1): 0.02, (0.65, 10): 0.16, (0.65, 100): 1.6, (0.7, 1): 0.02, (0.7, 10): 0.15, (0.7, 100): 1.47, (0.75, 1): 0.02, (0.75, 10): 0.14, (0.75, 100): 1.32, (0.8, 1): 0.02, (0.8, 10): 0.12, (0.8, 100): 1.12, (0.85, 1): 0.01, (0.85, 10): 0.09, (0.85, 100): 0.9, (0.9, 1): 0.01, (0.9, 10): 0.07, (0.9, 100): 0.63, (0.95, 1): 0.01, (0.95, 10): 0.04, (0.95, 100): 0.34}


@pytest.mark.parametrize("p", PS)
@pytest.mark.parametrize("c", CS)
def test_fees_match_t9_costs(p, c):
    assert A.fee_webull(p, c) == pytest.approx(WEBULL[(p, c)], abs=1e-12)
    assert A.fee_kalshi_direct(p, c) == pytest.approx(DIRECT[(p, c)], abs=1e-12)


def _dec_direct(p: float, c: int) -> float:
    d = Decimal(str(p))
    return float((Decimal("0.07") * c * d * (1 - d)).quantize(Decimal("0.01"), rounding=ROUND_CEILING))


def test_constants_match_decimal():
    for (p, c), v in DIRECT.items():
        assert v == _dec_direct(p, c)
    for (p, c), v in WEBULL.items():
        assert v == float(Decimal("0.02") * c)


# C = 100: float 0.07 * C * P * (1 - P) carries noise above the exact cent value, so a plain float ceil charges
# one cent too much (e.g. 1.7500000000000002 -> 1.76). Exact values by hand: 7 x P x (1 - P) dollars.
FLOAT_NOISE = {0.10: 0.63, 0.20: 1.12, 0.40: 1.68, 0.50: 1.75, 0.60: 1.68, 0.70: 1.47, 0.80: 1.12}


@pytest.mark.parametrize("p", sorted(FLOAT_NOISE))
def test_direct_fee_no_float_ceil_overcharge(p):
    assert math.ceil(0.07 * 100 * p * (1 - p) * 100) / 100 == pytest.approx(FLOAT_NOISE[p] + 0.01)  # the trap
    assert A.fee_kalshi_direct(p, 100) == FLOAT_NOISE[p]
