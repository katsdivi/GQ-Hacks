"""Replay acceptance checks using synthetic data only; no pipeline execution."""
from pathlib import Path
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from app import replay


def test_expanding_scale_and_strict_gap_threshold():
    """Future extremes stay hidden; exactly two cents does not create shading."""
    prices = pd.DataFrame({"cme": [.52, .54, .95], "kalshi": [.50, .50, .50]},
                          index=[0, replay.SECOND, 2 * replay.SECOND])
    signals = pd.DataFrame(columns=replay.SIGNAL_COLUMNS)
    early = replay.price_chart(prices, signals, replay.SECOND)
    later = replay.price_chart(prices, signals, 2 * replay.SECOND)
    # The first completed interval differs by exactly two cents, so it is clear.
    assert len(early.data[0].x) == 0
    assert len(later.data[0].x) == 6
    assert early.layout.yaxis.range[1] < .95
    assert later.layout.yaxis.range[1] >= .95
    assert later.layout.yaxis.range[0] <= early.layout.yaxis.range[0]


def test_midpoints_do_not_look_ahead():
    """A subsecond quote must not leak into the preceding one-second step."""
    ticks = pd.DataFrame([
        (0, "cme", "bid", .4), (0, "cme", "ask", .6),
        (1_500_000_000, "cme", "bid", .6), (2_000_000_000, "cme", "ask", .8),
        (0, "kalshi", "trade", .45), (2_000_000_000, "kalshi", "trade", .5),
    ], columns=["ts", "venue", "kind", "price"])
    steps = replay.price_steps(ticks)
    assert steps.cme.tolist() == pytest.approx([.5, .5, .7])
    assert steps.kalshi.tolist() == pytest.approx([.45, .45, .5])


@pytest.mark.parametrize("speed", [1, 5, 20])
def test_sample_start_to_finish(speed):
    """Exercise every cursor transition, then render the full-game terminal frame."""
    prices, signals, curve, notes, end = replay.load_game("sample")
    cursor = int(prices.index.min())
    while cursor < end:
        previous = cursor
        cursor = replay.advance_cursor(cursor, end, speed)
        assert previous < cursor <= end
    assert cursor == end
    assert replay.advance_cursor(cursor, end, speed) == end
    assert replay.price_chart(prices, signals, cursor).to_json()
    assert replay.latency_chart(curve).to_json()


def test_fixture_markers_and_future_filter():
    """Markers match sample midpoints exactly, and future signals stay hidden."""
    prices, signals, _, _, _ = replay.load_game("sample")
    for row in signals.itertuples():
        assert row.price == pytest.approx(prices.loc[row.ts, row.venue])
    fig = replay.price_chart(prices, signals, int(signals.ts.min()) - 1)
    assert all(len(trace.x) == 0 for trace in fig.data if trace.mode == "markers")


@pytest.mark.parametrize("speed", [1, 5, 20])
def test_metrics_follow_elapsed_game_time(speed):
    """Skipped frames still include every entry and the latest supplied balance."""
    start = int(pd.Timestamp("2026-01-01T17:00:00Z").value)
    signals = pd.DataFrame([
        (start + replay.SECOND, "enter_long", .5, 3, .02, 0.),
        (start + 2 * replay.SECOND, "exit", .6, 3, .02, .27),
        (start + 3 * replay.SECOND, "enter_short", .6, 1, .02, .27),
        (start + 4 * replay.SECOND, "exit", .7, 1, .02, -.15),
    ], columns=replay.SIGNAL_COLUMNS)
    end = start + 10 * replay.SECOND
    cursor = start
    # Four 250 ms updates must equal one wall-clock second at every speed.
    for _ in range(4):
        cursor = replay.advance_cursor(cursor, end, speed, .25)
    assert cursor == min(start + speed * replay.SECOND, end)
    for seconds, profit, count in [(0, 0., 0), (1, 0., 1), (2, .27, 1),
                                    (3, .27, 2), (4, -.15, 2), (10, -.15, 2)]:
        # A delayed frame lands at this game time regardless of selected speed.
        cursor = replay.advance_cursor(start, end, speed, seconds / speed)
        metrics = replay.replay_metrics(signals, cursor)
        assert metrics["profit"] == pytest.approx(profit)
        assert metrics["entries"] == count
        assert metrics["time"] == f"12:00:{seconds:02d}"


def test_streamlit_controls():
    """Pause freezes metrics; elapsed playback and restart use the same cursor."""
    app = AppTest.from_file(str(Path(replay.__file__))).run(timeout=30)
    assert not app.exception
    start = app.session_state.cursor
    app.button[0].click().run(timeout=30)
    assert app.session_state.cursor >= start
    app.button[0].click().run(timeout=30)
    paused = app.session_state.cursor
    app.run(timeout=30)
    assert app.session_state.cursor == paused
    for speed in [1, 5, 20]:
        app.selectbox[1].select(speed).run(timeout=30)
        assert app.session_state.cursor == paused
        app.button[0].click().run(timeout=30)
        before = app.session_state.cursor
        # Simulate a delayed refresh without introducing a slow test sleep.
        app.session_state.clock_at -= 1.0
        app.run(timeout=30)
        assert app.session_state.cursor >= before + speed * replay.SECOND
        _, signals, _, _, _ = replay.load_game("sample")
        expected = replay.replay_metrics(signals, app.session_state.cursor)
        displayed = {metric.label: metric.value for metric in app.metric}
        assert displayed["Running profit"] == f"${expected['profit']:.2f}"
        assert displayed["Trades entered"] == str(expected["entries"])
        assert displayed["Replay time (ET)"] == expected["time"]
        app.button[0].click().run(timeout=30)
        paused = app.session_state.cursor
    _, _, _, _, end = replay.load_game("sample")
    app.session_state.cursor = end - replay.SECOND
    app.button[0].click().run(timeout=30)
    app.session_state.clock_at -= 1.0
    app.run(timeout=30)
    assert app.session_state.cursor == end
    assert not app.session_state.playing
    app.button[0].click().run(timeout=30)
    assert start <= app.session_state.cursor < end
    assert not app.exception
