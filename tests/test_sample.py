"""Guards the fake game, the ground truth every lead/lag and strategy test relies on."""
import pandas as pd

from make_sample import LAG_S, N_JUMPS, build, validate


def test_sample_is_deterministic_and_valid():
    df1, truth1 = build(seed=42)
    df2, _ = build(seed=42)
    validate(df1, truth1)
    pd.testing.assert_frame_equal(df1, df2)
    assert len(truth1) == N_JUMPS
    assert (truth1["planted_lag_s"] == LAG_S).all()


def test_ts_is_nanoseconds():
    df, _ = build(seed=42)
    assert df["ts"].dtype == "int64"
    assert len(str(int(df["ts"].iloc[0]))) == 19
