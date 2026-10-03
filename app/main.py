"""Shared Streamlit entry point: streamlit run app/main.py.

Streamlit runs only the selected page, so database polling and replay refreshes
do not compete while the other page is hidden. Existing standalone commands
remain available for development.
"""
import time

import streamlit as st


def main():
    """Expose both pages in the sidebar and pause replay when leaving it."""
    st.set_page_config(page_title="StaleLine", layout="wide", initial_sidebar_state="expanded")
    page = st.navigation([
        st.Page("replay.py", title="Replay", icon=":material/play_circle:", default=True),
        st.Page("health.py", title="Recorder Health", icon=":material/monitor_heart:"),
    ], position="sidebar")

    # Preserve the last displayed replay cursor without advancing it during
    # time spent on the health page. Returning to Replay requires pressing Play.
    if page.title != "Replay":
        st.session_state.playing = False
        st.session_state.clock_at = time.monotonic()

    with st.sidebar:
        st.caption("StaleLine | Paper trading")
    page.run()


if __name__ == "__main__":
    main()
