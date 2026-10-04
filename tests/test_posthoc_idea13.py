"""Synthetic tests for scripts/posthoc_idea13.py (post-hoc Idea 13). No real data."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[1] / "scripts")]
import posthoc_idea13 as I  # noqa: E402
import strategy_a as A  # noqa: E402

NS = 1_000_000_000
KO = pd.Timestamp("2025-10-05 17:00", tz="UTC")
T = KO.value


def game(result=1.0, home="H", away="W"):
    return A.Game("nfl_test", "NFL", home, away, "EV", KO, "espn", result)


def tr(rows):
    """rows: (offset_s, team, own_yes_price, home) -> tick-contract rows (price = P(home); away flipped)."""
    out = []
    for off, team, px, home in rows:
        out.append({"ts": T + int(off * NS), "venue": "kalshi", "market_id": f"EV-{team}", "kind": "trade",
                    "price": px if team == home else 1 - px, "size": 10.0, "side": "buy"})
    return pd.DataFrame(out)


BASE = [(-60, "H", 0.50, "H"), (-60, "W", 0.50, "H"), (2, "H", 0.52, "H"), (2, "W", 0.48, "H")]


def entered(rows, e, leg):
    return [r for r in rows if r["e"] == e and r["leg"] == leg][0]


def test_no_kalshi_trade_after_t_used():
    g = game()
    # line: home -150, away +130 -> p_home ~0.583; K = 0.50 -> signal buys H with gap ~0.083
    r1, _ = I.evaluate_game(tr(BASE), g, -150.0, 130.0)
    later = BASE + [(0.5, "H", 0.95, "H"), (0.9, "W", 0.05, "H"), (0.0001, "H", 0.90, "H")]
    r2, _ = I.evaluate_game(tr(later), g, -150.0, 130.0)
    for e in I.ES:
        a, b = entered(r1, e, "signal"), entered(r2, e, "signal")
        assert a.get("gap") == b.get("gap") and a.get("team") == b.get("team")


def test_trade_at_exactly_t_is_used_and_stale_skipped():
    g = game()
    _, info = I.evaluate_game(tr([(0, "H", 0.40, "H"), (0, "W", 0.60, "H"), (2, "H", 0.41, "H")]), g, -150.0, 130.0)
    assert info["k_home"] == pytest.approx(0.40)
    rows, info = I.evaluate_game(tr([(-601, "H", 0.5, "H"), (-60, "W", 0.5, "H"), (2, "H", 0.5, "H"),
                                    (2, "W", 0.5, "H")]), g, -150.0, 130.0)
    assert info["status"] == "no Kalshi price"


def test_fill_never_before_t_plus_1s():
    g = game()
    rows, _ = I.evaluate_game(tr(BASE[:2] + [(0.5, "H", 0.30, "H"), (0.999, "H", 0.31, "H"), (1.0, "H", 0.55, "H")]),
                              g, -150.0, 130.0)
    r = entered(rows, 0.02, "signal")
    assert r["entered"] and r["fill_ts"] >= T + NS and r["trade_px"] == pytest.approx(0.55)
    rows, _ = I.evaluate_game(tr(BASE[:2] + [(301.5, "H", 0.55, "H")]), g, -150.0, 130.0)
    assert entered(rows, 0.02, "signal")["skip"] == "no post-decision trade"


def test_no_vig_hand_examples():
    assert I.no_vig(-110, -110) == pytest.approx((0.5, 0.5))
    a, b = I.no_vig(-200, 170)          # 0.66667, 0.37037 -> /1.03704
    assert a == pytest.approx((2 / 3) / (2 / 3 + 100 / 270)) and a + b == pytest.approx(1.0)
    a, b = I.no_vig(150, -180)          # 0.4, 0.642857
    assert a == pytest.approx(0.4 / (0.4 + 180 / 280)) and b == pytest.approx(1 - a)


def test_orientation_swap_gives_mirrored_trade():
    g1 = game(result=1.0, home="H", away="W")
    r1, _ = I.evaluate_game(tr(BASE), g1, -150.0, 130.0)
    g2 = game(result=0.0, home="W", away="H")
    swapped = [(off, team, px, "W") for off, team, px, _ in BASE]
    r2, _ = I.evaluate_game(tr(swapped), g2, 130.0, -150.0)
    for e in I.ES:
        for lg in ("signal", "placebo"):
            a, b = entered(r1, e, lg), entered(r2, e, lg)
            assert a.get("team") == b.get("team") and a.get("gap") == pytest.approx(b.get("gap"))
            assert a.get("payout") == b.get("payout") and a.get("fill") == b.get("fill")


def test_fee_function():
    assert I.fee_direct(Decimal("0.3")) == Decimal("0.15")    # 0.07*10*0.21 = 0.147 -> 0.15
    assert I.fee_direct(Decimal("0.5")) == Decimal("0.18")    # 0.175 -> 0.18
    assert I.fee_direct(Decimal("0.8")) == Decimal("0.12")    # 0.112 -> 0.12
    assert I.fee_webull(Decimal("0.5")) == Decimal("0.20")


def test_payout_is_kalshi_settlement_and_placebo_side():
    g = game(result=0.0)
    rows, _ = I.evaluate_game(tr(BASE), g, -150.0, 130.0)
    s, p = entered(rows, 0.02, "signal"), entered(rows, 0.02, "placebo")
    assert s["team"] == "H" and s["payout"] == 0.0 and p["team"] == "W" and p["payout"] == 1.0


def test_holdout_game_refused():
    g = A.Game("nfl_x", "NFL", "H", "W", "EV", pd.Timestamp("2026-09-20 17:00", tz="UTC"), "espn", 1.0)
    with pytest.raises(ValueError):
        I.evaluate_game(tr(BASE), g, -150.0, 130.0)


def test_no_line_skipped():
    rows, info = I.evaluate_game(tr(BASE), game(), float("nan"), float("nan"))
    assert info["status"] == "no nflverse line" and all(r["skip"] == "no nflverse line" for r in rows)
