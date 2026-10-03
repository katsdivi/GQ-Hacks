"""Polymarket US snapshot dedup: a missing side (NaN) must not emit a row on every poll."""
from collector.run import PolymarketUS


def make():
    p = PolymarketUS.__new__(PolymarketUS)
    p.top, p.markets = {}, {"s": {"long_is_away": True}}
    return p


def test_nan_side_dedups():
    p = make()
    nan = float("nan")
    assert len(p._rows("s", nan, 0.97, nan, nan, 1)) == 1          # first snapshot: home bid only
    assert p._rows("s", float("nan"), 0.97, float("nan"), float("nan"), 2) == []   # unchanged, fresh NaN objects
    assert len(p._rows("s", 0.01, 0.97, nan, nan, 3)) == 2          # bid appears: both rows


def test_change_emits():
    p = make()
    assert len(p._rows("s", 0.40, 0.42, 1.0, 1.0, 1)) == 2
    assert p._rows("s", 0.40, 0.42, 1.0, 1.0, 2) == []
    assert len(p._rows("s", 0.41, 0.42, 1.0, 1.0, 3)) == 2
