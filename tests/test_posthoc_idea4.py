"""Synthetic tests for scripts/posthoc_idea4.py (post-hoc, exploratory; designed and selected on training only;
holdout run once)."""
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import posthoc_idea4 as P  # noqa: E402
import strategy_a as A  # noqa: E402

NS = 1_000_000_000
KO = pd.Timestamp("2025-10-01 20:00", tz="UTC")


def game(result=1.0):
    return A.Game("g1", "NFL", "HOM", "AWY", "EV", KO, "espn", result)


def tr(rows):
    """rows: (seconds after kickoff, team, own YES price). Stored as P(home) like the tick contract."""
    out = []
    for s, team, p in rows:
        out.append({"ts": KO.value + int(s * NS), "venue": "kalshi", "market_id": f"EV-{team}", "kind": "trade",
                    "price": p if team == "HOM" else round(1 - p, 4)})
    return pd.DataFrame(out)


BASE = [(1200, "AWY", 0.30), (1200, "HOM", 0.70),       # in window but below theta
        (1500, "HOM", 0.88), (1530, "HOM", 0.91),        # 0.91 >= 0.90, previous HOM trade 30 s earlier -> t
        (1531, "HOM", 0.92), (1540, "AWY", 0.08)]


def test_a_later_trade_does_not_change_decision():
    g = game()
    d0 = P.decide(tr(BASE), g, 0.90)
    assert d0["team"] == "HOM" and d0["t_ns"] == KO.value + 1530 * NS
    # a later trade that would make AWY a huge favorite, and an earlier-ns-ordering trap after t
    later = BASE + [(1600, "AWY", 0.99), (1601, "AWY", 0.99), (1530.5, "AWY", 0.95)]
    d1 = P.decide(tr(later), g, 0.90)
    assert d1 == d0
    # crossing for 0.93 is unaffected by trades after its own t as well
    d2 = P.decide(tr(BASE + [(1531.5, "HOM", 0.94), (1532, "HOM", 0.94)]), g, 0.93)
    d3 = P.decide(tr(BASE + [(1531.5, "HOM", 0.94), (1532, "HOM", 0.94), (1533, "AWY", 0.99)]), g, 0.93)
    assert d2 == d3 and d2["t_ns"] == KO.value + int(1531.5 * NS)


def test_freshness_and_window():
    g = game()
    # previous trade 61 s before -> not eligible; window opens at kickoff + 20 min
    rows = [(1000, "HOM", 0.95), (1300, "HOM", 0.95), (1361, "HOM", 0.95)]
    d = P.decide(tr(rows), g, 0.90)
    assert d is None
    rows = [(1100, "HOM", 0.95), (1150, "HOM", 0.95), (1199, "HOM", 0.95), (1200, "HOM", 0.95)]
    assert P.decide(tr(rows), g, 0.90)["t_ns"] == KO.value + 1200 * NS


def test_b_fill_never_before_t_plus_1s():
    g = game()
    t = KO.value + 1530 * NS
    rows = BASE[:-2] + [(1530.2, "HOM", 0.80), (1530.999, "HOM", 0.81), (1531.0, "HOM", 0.93)]
    r = P.leg(tr(rows), g, "HOM", t)
    assert r["entered"] and r["fill_ts"] >= t + NS
    assert r["fill_ts"] == KO.value + 1531 * NS and r["fill"] == pytest.approx(0.94)
    # no trade within 5 min -> skip
    r = P.leg(tr(BASE[:4] + [(1530 + 301, "HOM", 0.9)]), g, "HOM", t)
    assert not r["entered"] and r["skip"] == "no post-decision trade"
    # fill at the 0.99 cap -> skip
    r = P.leg(tr(BASE[:4] + [(1532, "HOM", 0.98)]), g, "HOM", t)
    assert not r["entered"] and r["skip"] == "fill at 0.99"


@pytest.mark.parametrize("p", ["0.90", "0.95", "0.97", "0.99"])
def test_c_fee(p):
    dp = Decimal(p)
    exp = (Decimal("0.07") * 10 * dp * (1 - dp)).quantize(Decimal("0.01"), rounding=ROUND_CEILING)
    assert P.fee_direct(dp) == exp
    assert {"0.90": Decimal("0.07"), "0.95": Decimal("0.04"), "0.97": Decimal("0.03"), "0.99": Decimal("0.01")}[p] == exp


def test_d_loss_costs_fill_plus_fee():
    g = game(result=0.0)                                   # home loses
    t = KO.value + 1530 * NS
    r = P.leg(tr(BASE), g, "HOM", t)                       # fill 0.92 + 0.01 = 0.93
    fill = Decimal("0.93")
    fee = P.fee_direct(fill)
    assert Decimal(str(r["pnl_direct"])) == -(fill * 10 + fee)
    assert Decimal(str(r["pnl_webull"])) == -(fill * 10 + Decimal("0.20"))


def test_e_tie_pays_5():
    g = game(result=0.5)
    t = KO.value + 1530 * NS
    for team in ("HOM", "AWY"):
        r = P.leg(tr(BASE + [(1532, "AWY", 0.07)]), g, team, t)
        fill = Decimal(str(r["fill"]))
        assert Decimal(str(r["payout"])) * 10 == Decimal("5.0")
        assert Decimal(str(r["pnl_webull"])) == Decimal("5.00") - fill * 10 - Decimal("0.20")


def test_refuses_sealed_game():
    g = A.Game("g2", "NFL", "HOM", "AWY", "EV", pd.Timestamp("2026-09-01", tz="UTC"), "espn", 1.0)
    with pytest.raises(ValueError):
        P.evaluate_game(tr(BASE), g)
