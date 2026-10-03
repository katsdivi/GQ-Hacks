"""collector.merge_recordings on synthetic recorder dirs (no real data)."""
from pathlib import Path

import pandas as pd

from collector.merge_recordings import merge

DAY = 1_791_000_000_000_000_000  # 2026-10-03 UTC, ns
S = 1_000_000_000


def row(ts, kind, price, size, recv, market="M1", venue="kalshi", side="buy", **extra):
    return {"ts": ts, "venue": venue, "market_id": market, "kind": kind, "price": price, "size": size,
            "side": side, "recv_ns": recv, **extra}


def write(d: Path, venue: str, rows: list[dict], name: str = "1_1.parquet") -> None:
    p = d / venue / "20261003"
    p.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df = df.astype({"ts": "int64", "recv_ns": "int64"})
    df.to_parquet(p / name, index=False)


def make_inputs(tmp_path: Path) -> tuple[Path, Path]:
    a, b = tmp_path / "live", tmp_path / "live_alden"
    write(a, "kalshi", [
        row(DAY + 10 * S, "trade", 0.55, 3.0, DAY + 11 * S),               # in both
        row(DAY + 20 * S, "trade", 0.56, 1.0, DAY + 21 * S),               # only a
        row(DAY + 30 * S, "trade", 0.57, 2.0, DAY + 31 * S),               # same key twice in a
        row(DAY + 30 * S, "trade", 0.57, 2.0, DAY + 31 * S + 5),
        row(DAY + 40 * S, "bid", 0.50, 9.0, DAY + 40 * S),                 # book row, ts = recv
    ])
    write(b, "kalshi", [
        row(DAY + 10 * S, "trade", 0.55, 3.0, DAY + 11 * S + 250_000_000),  # same trade, later recv
        row(DAY + 25 * S, "trade", 0.58, 4.0, DAY + 26 * S, market="M2"),   # only b
        row(DAY + 30 * S, "trade", 0.57, 2.0, DAY + 31 * S + 7),            # pairs with first copy in a
        row(DAY + 40 * S + 3_000_000, "bid", 0.50, 9.0, DAY + 40 * S + 3_000_000),  # same book, own recv
    ])
    write(b, "polymarket", [
        row(DAY + 50 * S, "trade", 0.40, 5.0, DAY + 51 * S, venue="polymarket", market="T1",
            src_ts_ns=DAY + 50 * S, tx_hash="0xabc"),
    ])
    write(a, "polymarket", [
        row(DAY + 50 * S, "trade", 0.40, 5.0, DAY + 52 * S, venue="polymarket", market="T1",
            src_ts_ns=DAY + 50 * S, tx_hash="0xabc"),
        row(DAY + 60 * S, "ask", 0.45, 1.0, DAY + 60 * S, venue="polymarket", market="T1", side="sell"),
    ])
    return a, b


def test_overlap_dedupe_and_counts(tmp_path):
    a, b = make_inputs(tmp_path)
    counts = merge([a, b], tmp_path / "out")
    k = counts["kalshi"]
    # a: 5 rows, b: 4 rows. Matched: trade@10, first trade@30 -> 2 in both.
    assert k["in_2plus"] == 2
    assert k["only_live"] == 3          # trade@20, second trade@30, bid
    assert k["only_live_alden"] == 2    # M2 trade, bid
    assert k["total"] == 7 == k["only_live"] + k["only_live_alden"] + k["in_2plus"]
    out = pd.read_parquet(tmp_path / "out" / "kalshi" / "20261003.parquet")
    assert len(out) == 7
    p = counts["polymarket"]
    assert (p["in_2plus"], p["only_live"], p["only_live_alden"], p["total"]) == (1, 1, 0, 2)


def test_both_receipt_times_kept(tmp_path):
    a, b = make_inputs(tmp_path)
    merge([a, b], tmp_path / "out")
    out = pd.read_parquet(tmp_path / "out" / "kalshi" / "20261003.parquet")
    t = out[(out["ts"] == DAY + 10 * S) & (out["kind"] == "trade")]
    assert len(t) == 1
    assert t["recv_ns_live"].iloc[0] == DAY + 11 * S
    assert t["recv_ns_live_alden"].iloc[0] == DAY + 11 * S + 250_000_000
    assert t["sources"].iloc[0] == "live,live_alden"
    assert str(out["recv_ns_live"].dtype) == "Int64" and str(out["ts"].dtype) == "int64"
    # Same-key copies pair in receipt order: first a copy matches the b copy.
    dup = out[out["ts"] == DAY + 30 * S].sort_values("recv_ns_live")
    assert list(dup["sources"]) == ["live,live_alden", "live"]
    assert dup["recv_ns_live_alden"].iloc[0] == DAY + 31 * S + 7
    pm = pd.read_parquet(tmp_path / "out" / "polymarket" / "20261003.parquet")
    tr = pm[pm["kind"] == "trade"].iloc[0]
    assert tr["tx_hash"] == "0xabc" and tr["src_ts_ns"] == DAY + 50 * S
    assert tr["recv_ns_live"] == DAY + 52 * S and tr["recv_ns_live_alden"] == DAY + 51 * S
    assert "src_ts_ns" not in out.columns  # kalshi has no source timestamps


def test_unique_rows_from_each_side_kept(tmp_path):
    a, b = make_inputs(tmp_path)
    merge([a, b], tmp_path / "out")
    out = pd.read_parquet(tmp_path / "out" / "kalshi" / "20261003.parquet")
    only_a = out[out["sources"] == "live"]
    only_b = out[out["sources"] == "live_alden"]
    assert set(only_a["ts"]) == {DAY + 20 * S, DAY + 30 * S, DAY + 40 * S}
    assert set(only_b["ts"]) == {DAY + 25 * S, DAY + 40 * S + 3_000_000}
    assert only_a["recv_ns_live_alden"].isna().all() and only_b["recv_ns_live"].isna().all()
    # Book rows carry receipt time as ts, so both recorders' copies stay.
    assert (out["kind"] == "bid").sum() == 2


def test_sorted_and_deterministic(tmp_path):
    a, b = make_inputs(tmp_path)
    merge([a, b], tmp_path / "out1")
    merge([a, b], tmp_path / "out2")
    for v in ("kalshi", "polymarket"):
        x = pd.read_parquet(tmp_path / "out1" / v / "20261003.parquet")
        y = pd.read_parquet(tmp_path / "out2" / v / "20261003.parquet")
        pd.testing.assert_frame_equal(x, y)
        assert x.equals(x.sort_values(["ts", "kind", "market_id"], kind="stable").reset_index(drop=True))
    k = pd.read_parquet(tmp_path / "out1" / "kalshi" / "20261003.parquet")
    assert list(k.columns) == ["ts", "venue", "market_id", "kind", "price", "size", "side",
                               "recv_ns_live", "recv_ns_live_alden", "sources"]


def test_partition_by_ts_date_and_empty_input(tmp_path):
    a, b = tmp_path / "live", tmp_path / "live_alden"
    b.mkdir()
    # Written in the 20261003 folder but ts falls on the next UTC day.
    write(a, "kalshi", [row(DAY + 86_400 * S, "trade", 0.5, 1.0, DAY + 86_400 * S)])
    counts = merge([a, b], tmp_path / "out")
    assert counts["kalshi"]["total"] == 1 and counts["kalshi"]["only_live_alden"] == 0
    assert (tmp_path / "out" / "kalshi" / "20261004.parquet").exists()
