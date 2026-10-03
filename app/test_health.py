"""Health-page checks with fake database responses; no credentials or network."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import psycopg
import pytest
from streamlit.testing.v1 import AppTest

from app import health

NOW = datetime(2026, 1, 1, 17, 30, 25, tzinfo=timezone.utc)


@pytest.mark.parametrize("age,status", [(0, "Healthy"), (59.9, "Healthy"),
                                       (60, "Stale"), (600, "Stale"), (-1, "Clock issue")])
def test_freshness_threshold(age, status):
    """A stopped recorder crosses the threshold without needing new rows."""
    result = health.venue_health(NOW - timedelta(seconds=age), NOW)
    assert result[0] == status
    assert result[2] == (status == "Healthy")
    assert health.venue_health(None, NOW)[0] == "No data"


def test_history_zero_fills_missing_minutes():
    """Every venue gets sixty complete buckets, including silent venues."""
    minute = NOW.replace(second=0) - timedelta(minutes=1)
    frame = health.history_frame([("kalshi", minute, 42)], ["cme", "kalshi"], NOW)
    assert len(frame) == 120
    assert frame[frame.venue == "cme"].rows.sum() == 0
    assert frame[frame.venue == "kalshi"].rows.sum() == 42
    assert frame.minute.max() == minute
    assert frame.minute.min() == NOW.replace(second=0) - timedelta(hours=1)
    assert health.activity_chart(frame).to_json()


def test_database_queries_are_read_only_and_share_a_clock():
    """Verify the transaction guard and shared timestamp without connecting."""
    connection = MagicMock()
    cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (NOW,)
    cursor.fetchall.side_effect = [[("kalshi", NOW, 100)], []]
    with patch.object(health.psycopg, "connect", return_value=connection):
        now, summary, history = health.fetch_snapshot("test-only")
    queries = cursor.execute.call_args_list
    assert "READ ONLY" in queries[0].args[0]
    assert "statement_timeout" in queries[1].args[0]
    assert queries[-2].args[1] == queries[-1].args[1] == {"now": NOW}
    assert now == NOW and summary[0][2] == 100 and history == []


def test_page_refreshes_rates_and_stale_status():
    """Ten-minute count / ten is displayed; an unchanged feed turns red."""
    snapshot = (NOW, [("kalshi", NOW - timedelta(seconds=55), 125)], [])
    app = AppTest.from_string("from app.health import main\nmain()")
    with patch.object(health, "database_dsn", return_value="test-only"), \
         patch.object(health, "fetch_snapshot", return_value=snapshot) as fetch:
        app.run()
        assert not app.exception
        assert any(metric.value == "12.5" for metric in app.metric)
        assert any(item.value == "Healthy" for item in app.success)
        fetch.return_value = (NOW + timedelta(seconds=10), snapshot[1], [])
        app.run()
        assert not app.success
        assert any(item.value == "Stale" for item in app.error)
        # A failed poll clears healthy cards and does not expose exception text.
        fetch.side_effect = psycopg.OperationalError("private connection details")
        app.run()
        assert not app.metric
        assert "Health is unknown" in app.error[0].value
        assert "private" not in app.error[0].value


def test_unconfigured_page_does_not_connect():
    """A clean checkout offers setup instructions instead of a traceback."""
    with patch.object(health, "database_dsn", return_value=None), \
         patch.object(health, "fetch_snapshot") as fetch:
        app = AppTest.from_string("from app.health import main\nmain()").run()
        assert not app.exception
        assert "TIGER_DSN" in app.info[0].value
        fetch.assert_not_called()
