"""Check page switching without contacting the team's database."""
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


def test_sidebar_switch_preserves_paused_replay():
    """Navigating away must not advance playback while the page is hidden."""
    app = AppTest.from_file(str(Path(__file__).with_name("main.py"))).run(timeout=30)
    assert not app.exception
    app.button[0].click().run(timeout=30)
    cursor = app.session_state.cursor
    assert app.session_state.playing
    # Prevent live database access even if the developer has configured .env.
    with patch.dict("os.environ", {"TIGER_DSN": "", "TIGER_DATABASE_URL": ""}):
        app.switch_page("health.py").run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "Recorder health"
    assert not app.session_state.playing
    app.switch_page("replay.py").run(timeout=30)
    assert not app.exception
    assert app.session_state.cursor == cursor
    assert not app.session_state.playing
