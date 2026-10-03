"""Deliverable 2: read-only recorder health. Run: streamlit run app/health.py.

Freshness measures tick timestamps, not recorder process uptime. No orders,
tick ingestion, schema changes, or files are written by this page.
"""
from datetime import datetime, timezone
from pathlib import Path
import os

import pandas as pd
import plotly.graph_objects as go
import psycopg
from dotenv import load_dotenv
import streamlit as st

APP = Path(__file__).resolve().parent
DEFAULT_VENUES = ("cme", "kalshi", "polymarket")

# One grouped query supplies the newest tick and the exact ten-minute count.
# Future timestamps remain visible as clock problems, but do not inflate rates.
SUMMARY_SQL = """
SELECT venue, max(ts) AS latest,
       count(*) FILTER (WHERE ts > %(now)s - interval '10 minutes'
                          AND ts <= %(now)s) AS recent_rows
FROM ticks
GROUP BY venue ORDER BY venue
"""

# Sixty completed minute buckets avoid presenting a partly elapsed minute as
# a sudden traffic drop. The UI explicitly labels this choice.
HISTORY_SQL = """
SELECT venue, date_trunc('minute', ts) AS minute, count(*) AS rows
FROM ticks
WHERE ts >= date_trunc('minute', %(now)s::timestamptz) - interval '1 hour'
  AND ts < date_trunc('minute', %(now)s::timestamptz)
GROUP BY venue, minute ORDER BY minute, venue
"""


def database_dsn():
    """Load credentials without displaying them; prefer the deliverable's name.

    An optional app/.env allows setup entirely inside app. The existing root
    .env is read as a fallback only; this function never edits either file.
    Exported environment variables take precedence over values in both files.
    """
    load_dotenv(APP / ".env", override=False)
    load_dotenv(APP.parent / ".env", override=False)
    return os.getenv("TIGER_DSN") or os.getenv("TIGER_DATABASE_URL")


def fetch_snapshot(dsn):
    """Fetch consistent summary/history data in one bounded read-only transaction.

    Use the database clock for freshness so laptop clock drift cannot falsely
    mark a feed healthy. A fresh connection per poll also recovers after outages.
    Context managers close both the cursor and connection even when SQL fails.
    """
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5s'")
            cursor.execute("SET LOCAL TIME ZONE 'UTC'")
            cursor.execute("SELECT CURRENT_TIMESTAMP")
            now = cursor.fetchone()[0]
            cursor.execute(SUMMARY_SQL, {"now": now})
            summary = cursor.fetchall()
            cursor.execute(HISTORY_SQL, {"now": now})
            history = cursor.fetchall()
    return now, summary, history


def venue_health(latest, now):
    """Classify a tick; at exactly sixty seconds it is already stale."""
    if latest is None:
        return "No data", "No rows received", False
    age = (now - latest).total_seconds()
    if age < 0:
        return "Clock issue", "Latest timestamp is in the future", False
    return ("Healthy" if age < 60 else "Stale", f"Last row {int(age)} seconds ago", age < 60)


def history_frame(history, venues, now):
    """Fill missing completed minutes with zero so quiet feeds remain visible."""
    end = pd.Timestamp(now).floor("min")
    minutes = pd.date_range(end=end - pd.Timedelta(minutes=1), periods=60, freq="min")
    index = pd.MultiIndex.from_product([venues, minutes], names=["venue", "minute"])
    frame = pd.DataFrame(history, columns=["venue", "minute", "rows"])
    if frame.empty:
        return pd.DataFrame({"rows": 0}, index=index).reset_index()
    frame["minute"] = pd.to_datetime(frame.minute, utc=True)
    return frame.set_index(["venue", "minute"]).reindex(index, fill_value=0).reset_index()


def activity_chart(frame):
    """Draw one readable line per venue with explicit Eastern-time labels."""
    fig = go.Figure()
    colors = {"cme": "#2563eb", "kalshi": "#ea580c", "polymarket": "#64748b"}
    for venue, rows in frame.groupby("venue", sort=True):
        fig.add_trace(go.Scatter(
            x=rows.minute.dt.tz_convert("America/New_York"), y=rows.rows,
            name=venue.upper() if venue == "cme" else venue.title(),
            mode="lines", line=dict(color=colors.get(venue), width=2, shape="hv"),
            hovertemplate="%{x|%H:%M} ET<br>%{y:,} rows/min<extra>%{fullData.name}</extra>",
        ))
    fig.update_layout(
        template="plotly_white", height=450, paper_bgcolor="white", plot_bgcolor="white",
        font=dict(size=16, color="#172033"), margin=dict(l=65, r=25, t=35, b=90),
        xaxis=dict(title="Time (ET)", tickformat="%H:%M", nticks=6, showgrid=False),
        yaxis=dict(title="Rows per minute", rangemode="tozero", gridcolor="#e2e8f0"),
        legend=dict(orientation="h", y=-.25), uirevision="health",
    )
    return fig


def main():
    """Refresh cards and history together, never showing failed polls as healthy."""
    st.set_page_config(page_title="StaleLine recorder health", layout="wide")
    st.html(f"<style>{(APP / 'replay.css').read_text(encoding='utf-8')}</style>")
    st.title("Recorder health")
    st.caption("Updates every 10 seconds. Green: last tick under 60 seconds old. Red: stale or missing data.")
    dsn = database_dsn()
    if not dsn:
        st.info("Database is not configured. Set TIGER_DSN in app/.env to the team's read-only Tiger Data connection string, then rerun this page.")
        return

    @st.fragment(run_every=10)
    def refresh():
        """Replace the snapshot only after both queries succeed."""
        try:
            now, summary, history = fetch_snapshot(dsn)
        except (psycopg.Error, OSError):
            # Database exceptions can contain connection details. Never render
            # their raw text or keep displaying old green cards after failure.
            st.error("Database unavailable. Health is unknown. Check the connection, read permissions, and ticks table. Retrying in 10 seconds.")
            return
        st.caption(f"Database snapshot: {now.astimezone(timezone.utc):%Y-%m-%d %H:%M:%S} UTC")
        records = {venue: (latest, count) for venue, latest, count in summary}
        venues = sorted(set(DEFAULT_VENUES) | set(records))
        # Limit each card row to three columns, even if extra venues are recorded.
        for offset in range(0, len(venues), 3):
            for column, venue in zip(st.columns(3), venues[offset:offset + 3]):
                latest, count = records.get(venue, (None, 0))
                status, freshness, healthy = venue_health(latest, now)
                with column.container(border=True):
                    st.subheader(venue.upper() if venue == "cme" else venue.title())
                    (st.success if healthy else st.error)(status)
                    st.write(freshness)
                    # This is the requested rate: all rows in ten minutes / ten.
                    st.metric("Rows/min (last 10 minutes)", f"{count / 10:,.1f}")
        st.subheader("Activity over the last hour")
        st.caption("60 completed one-minute intervals; missing minutes show zero. Counts include bids, asks, and trades.")
        st.plotly_chart(activity_chart(history_frame(history, venues, now)),
                        width="stretch", theme=None, key="health_history")

    refresh()


if __name__ == "__main__":
    main()
