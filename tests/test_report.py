"""Latency curve checks on the fake game (report.py)."""
import pandas as pd
import pytest

import make_sample
import report

BOUND = "kalshi traded (unshifted)"


@pytest.fixture(scope="module")
def lag5():
    return report.load_games([], fake_lag=5)


def test_fake_lag_is_restored_and_labelled(lag5):
    assert list(lag5) == ["sample_lag5"]
    assert make_sample.LAG_S == 2


def test_edge_shrinks_with_latency_when_lag_exceeds_detection_delay(lag5):
    df = report.curve(lag5, [0.0, 5.0])
    c = df[(df["direction"] == "cme->kalshi") & (df["bound"] == BOUND)].set_index("latency_s")
    assert c.loc[0.0, "n_trades"] > 0
    assert c.loc[0.0, "edge_cents_mean"] > 0
    assert c.loc[0.0, "edge_cents_mean"] > c.loc[5.0, "edge_cents_mean"]
    assert (c["ci_method"] == report.CI_TRADE).all()
    assert (c["edge_ci_low"] <= c["edge_cents_mean"]).all() and (c["edge_cents_mean"] <= c["edge_ci_high"]).all()


def test_csv_contract_columns_and_determinism(tmp_path):
    a = report.main(["--games", "sample", "--fake-lag", "5", "--latencies", "0,1"], out_dir=tmp_path / "a", stamp="T")
    b = report.main(["--games", "sample", "--fake-lag", "5", "--latencies", "0,1"], out_dir=tmp_path / "b", stamp="T")
    csv_a = (tmp_path / "a" / "latency_curve.csv").read_bytes()
    assert csv_a == (tmp_path / "b" / "latency_curve.csv").read_bytes()
    pd.testing.assert_frame_equal(a, b)
    cols = list(pd.read_csv(tmp_path / "a" / "latency_curve.csv").columns)
    assert cols[:6] == ["latency_s", "n_trades", "edge_cents_mean", "edge_ci_low", "edge_ci_high", "pnl_total"]
    assert cols[6:] == ["direction", "bound", "n_games", "ci_method"]
    assert len(a) == 2 * 2   # 2 directions x 1 bound x 2 latencies
    assert (tmp_path / "a" / "latency_curve_sample_lag5_T.png").exists()
    assert (tmp_path / "a" / "latency_curve_sample_lag5_T.csv").read_bytes() == csv_a


def test_game_bootstrap_used_with_two_games(lag5):
    ticks = lag5["sample_lag5"]
    df = report.curve({"g1": ticks, "g2": ticks}, [0.0])
    lead = df[df["direction"] == "cme->kalshi"]
    assert (lead["ci_method"] == report.CI_GAME).all()
    assert (df["n_games"] == 2).all()
    placebo = df[df["direction"] == "kalshi->cme"]   # no trades: row still emitted, CI n/a
    assert (placebo["n_trades"] == 0).all() and (placebo["ci_method"] == report.CI_NONE).all()


def test_test_game_refused_before_any_read():
    def row(g):
        return {"game_id": g, "kickoff_utc": "2026-09-01T00:00:00Z"}
    with pytest.raises(SystemExit, match="sealed test set"):
        report.load_games(["nfl_x"], game_row=row)


def test_cme_traded_rows_are_labelled_cme():
    import run
    from make_sample import build
    df, _ = build(seed=42)
    df = df.sort_values(["ts", "venue", "kind"], kind="stable")
    p = {**run.leadlag.PROVISIONAL, **run.strategy.PROVISIONAL}
    r = run.run_direction(df, "kalshi", "cme", {"D_p90_s": 0.0}, 1.0, p)
    assert list(r["fills"]) == ["cme traded (unshifted)"]


def test_each_run_writes_its_own_files(tmp_path):
    report.main(["--games", "sample", "--latencies", "0"], out_dir=tmp_path, stamp="20261003T000000Z")
    report.main(["--games", "sample", "--latencies", "0"], out_dir=tmp_path, stamp="20261003T000001Z")
    assert len(list(tmp_path.glob("latency_curve_sample_*.csv"))) == 2
    assert (tmp_path / "latency_curve.csv").exists()
