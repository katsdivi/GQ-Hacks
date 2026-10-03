"""Deliverable 1: read-only replay. Run: streamlit run app/replay.py.

Only presentation transforms (midpoints, one-second steps and gap shading) live
here. Signals, cumulative profit and latency estimates always come from files.
"""
from pathlib import Path
import math
import time

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SECOND = 1_000_000_000
COLORS = {"cme": "#2563eb", "kalshi": "#f97316", "polymarket": "#888888"}
SIGNAL_COLUMNS = ["ts", "action", "price", "qty", "fee", "pnl_cum"]


def style_chart(fig, height):
    """Give both charts consistent spacing and sparse, legible axis labels."""
    fig.update_layout(
        template="plotly_white", height=height,
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        font=dict(family="Arial, sans-serif", size=16, color="#172033"),
        margin=dict(l=70, r=30, t=65, b=115),
        legend=dict(orientation="h", yanchor="top", y=-0.24, x=0,
                    font=dict(size=14), bgcolor="rgba(0,0,0,0)"),
        hovermode="closest", hoverlabel=dict(bgcolor="white", font_size=15, font_color="#172033"),
        transition_duration=0,
        dragmode="zoom",
    )
    fig.update_xaxes(nticks=6, tickangle=0, showgrid=False, zeroline=False,
                     automargin=True, title_standoff=16, tickfont_size=14)
    fig.update_yaxes(nticks=6, gridcolor="#e2e8f0", zeroline=False,
                     automargin=True, title_standoff=18, tickfont_size=14)
    return fig


def require_columns(frame, columns, source):
    """Report an input contract problem without repairing upstream numbers."""
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{source}: missing columns {', '.join(sorted(missing))}")


@st.cache_data(show_spinner=False)
def load_games():
    """Read the picker once; sealed real games are excluded before tick loading."""
    games = pd.read_csv(ROOT / "data/games.csv", dtype=str)
    require_columns(games, ["game_id", "home", "away", "kickoff_utc"], "games.csv")
    kickoff = pd.to_datetime(games.kickoff_utc, utc=True, errors="coerce")
    return games[(games.game_id == "sample") | (kickoff < pd.Timestamp("2026-08-01", tz="UTC"))]


def price_steps(ticks):
    """Build causal price events, using the latest known bid and ask per venue.

    Quote sides are forward-filled only; a midpoint requires both sides. A
    venue with any quotes never silently substitutes trades for missing quotes.
    The one-second grid samples at each timestamp, never from its future bucket.
    """
    start, end = int(ticks.ts.min()), int(ticks.ts.max())
    grid = pd.Index(range(start, end + SECOND, SECOND), name="ts")
    result = pd.DataFrame(index=grid[grid <= end])
    for venue in COLORS:
        rows = ticks[ticks.venue == venue].sort_values("ts", kind="stable")
        quotes = rows[rows.kind.isin(["bid", "ask"])]
        if not quotes.empty:
            book = quotes.pivot_table(index="ts", columns="kind", values="price", aggfunc="last")
            book = book.reindex(columns=["bid", "ask"]).ffill()
            events = (book.bid + book.ask) / 2
        else:
            events = rows[rows.kind == "trade"].drop_duplicates("ts", keep="last").set_index("ts").price
        if not events.empty:
            # Reindex on the union before forward fill to preserve subsecond events.
            result[venue] = events.reindex(events.index.union(result.index)).sort_index().ffill().reindex(result.index)
    return result


@st.cache_data(show_spinner=False)
def load_game(game_id, use_fixtures=True):
    """Load one game's immutable files once, with sample-only fallback fixtures."""
    if game_id not in set(load_games().game_id):
        raise ValueError("Game is unavailable or belongs to the sealed test set.")
    ticks = pd.read_parquet(ROOT / "data/ticks" / f"{game_id}.parquet")
    require_columns(ticks, ["ts", "venue", "kind", "price"], "ticks")
    if ticks.empty:
        raise ValueError("This game has no ticks to replay.")
    ticks = ticks.sort_values("ts", kind="stable")
    signal_path = ROOT / "out/signals" / f"{game_id}.parquet"
    curve_path = ROOT / "out/latency_curve.csv"
    notes = []
    if signal_path.exists():
        signals = pd.read_parquet(signal_path)
    elif game_id == "sample" and use_fixtures:
        signals = pd.read_parquet(FIXTURES / "sample_signals.parquet")
        notes.append("Trade markers and profit are synthetic UI fixtures, not backtest results.")
    else:
        signals = pd.DataFrame(columns=SIGNAL_COLUMNS)
        notes.append("No signal output exists for this game.")
    if curve_path.exists():
        curve = pd.read_csv(curve_path)
        notes.append("Latency curve: latest report output; it may cover a different game set.")
    elif game_id == "sample" and use_fixtures:
        curve = pd.read_csv(FIXTURES / "latency_curve.csv")
        notes.append("Latency curve is a synthetic UI fixture.")
    else:
        curve = pd.DataFrame(columns=["latency_s", "edge_cents_mean", "edge_ci_low", "edge_ci_high", "n_trades"])
    require_columns(signals, SIGNAL_COLUMNS, "signals")
    require_columns(curve, ["latency_s", "edge_cents_mean", "edge_ci_low", "edge_ci_high", "n_trades"], "latency curve")
    # Missing results are unknown, not zero-profit or zero-trade results.
    signals.attrs["available"] = signal_path.exists() or (game_id == "sample" and use_fixtures)
    return price_steps(ticks), signals.sort_values("ts", kind="stable"), curve, notes, int(ticks.ts.max())


def eastern(timestamps):
    """Use explicit nanoseconds and New York time, including daylight savings."""
    return pd.to_datetime(timestamps, unit="ns", utc=True).tz_convert("America/New_York")


def price_range(visible, signals):
    """Expand the display range in five-point steps using only revealed prices.

    Padding makes small venue differences readable. Since the full revealed
    history is retained, limits only expand instead of bouncing every frame.
    Signal fill prices are included so markers cannot be clipped by the scale.
    """
    values = pd.concat([visible[column] for column in visible.columns] + [signals.price]).dropna()
    if values.empty:
        return [0, 1]
    low = max(0, math.floor((float(values.min()) - 0.02) / 0.05) * 0.05)
    high = min(1, math.ceil((float(values.max()) + 0.02) / 0.05) * 0.05)
    return [low, high]


def price_chart(prices, signals, cursor):
    """Draw only visible price steps and original, unshifted signal coordinates."""
    visible = prices.loc[prices.index <= cursor]
    fig = go.Figure()
    if {"cme", "kalshi"}.issubset(visible.columns):
        # Fill each qualifying interval as its own rectangle. This avoids joining
        # disconnected gaps or shading across a later, non-qualifying interval.
        xs, ys = [], []
        gaps = visible[(visible.cme - visible.kalshi).abs() > 0.02 + 1e-12]
        # Convert timestamps once per frame, not once per polygon.
        left_times = eastern(gaps.index)
        right_times = eastern((gaps.index + SECOND).to_numpy().clip(max=cursor))
        for row, a, b in zip(gaps.itertuples(), left_times, right_times):
            left = int(row.Index)
            right = min(left + SECOND, cursor)
            if right > left:
                xs.extend([a, b, b, a, a, None])
                ys.extend([row.cme, row.cme, row.kalshi, row.kalshi, row.cme, None])
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line_width=0,
                                 fill="toself", fillcolor="rgba(239,68,68,0.30)",
                                 name="Gap > 2 cents", hoverinfo="skip"))
    for venue in visible.columns:
        fig.add_trace(go.Scatter(x=eastern(visible.index), y=visible[venue], name=venue.upper() if venue == "cme" else venue.title(),
                                 mode="lines", line={"color": COLORS[venue], "shape": "hv", "width": 2}, connectgaps=False,
                                 hovertemplate="%{x|%H:%M:%S} ET<br>%{y:.1%}<extra>%{fullData.name}</extra>"))
    shown = signals[signals.ts <= cursor]
    for action, symbol, color in [("enter_long", "triangle-up", "green"), ("enter_short", "triangle-down", "red"), ("exit", "x", "black")]:
        group = shown[shown.action == action]
        fig.add_trace(go.Scatter(x=eastern(group.ts.to_numpy()), y=group.price, mode="markers", name=action.replace("_", " ").title(),
                                 showlegend=True,
                                 marker={"symbol": symbol, "color": color, "size": 10, "line": {"color": "white", "width": 1}},
                                 customdata=group[["action", "qty", "fee"]].to_numpy(),
                                 hovertemplate="%{customdata[0]}<br>Price: %{y:.2%}<br>Qty: %{customdata[1]}<br>Fee: $%{customdata[2]:.2f}<extra></extra>"))
    fig.update_layout(title=dict(text="Home team win chance", font_size=20),
                      xaxis_title="Time (ET)", yaxis_title="Win chance",
                      yaxis={"range": price_range(visible, shown), "tickformat": ".0%"},
                      uirevision=f"replay-{prices.index.min()}")
    style_chart(fig, 680)
    # Short time labels prevent Plotly's automatic date labels from crowding
    # the axis. Full seconds remain available in the hover tooltip.
    elapsed_seconds = (cursor - int(prices.index.min())) / SECOND
    fig.update_xaxes(tickformat="%H:%M:%S" if elapsed_seconds < 120 else "%H:%M",
                     hoverformat="%H:%M:%S", minallowed=eastern([int(prices.index.min())])[0])
    return fig


def latency_chart(curve):
    """Plot supplied means and confidence bounds separately for each report series."""
    fig = go.Figure()
    # Bounds and directions must never be combined into one misleading line.
    keys = [key for key in ["direction", "bound"] if key in curve.columns]
    groups = curve.groupby(keys, dropna=False, sort=False) if keys else [("Reported edge", curve)]
    for label, group in groups:
        group = group.sort_values("latency_s")
        name = " / ".join(map(str, label)) if isinstance(label, tuple) else str(label)
        fig.add_trace(go.Scatter(x=group.latency_s, y=group.edge_ci_low, mode="lines", line_width=0, showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=group.latency_s, y=group.edge_ci_high, mode="lines", line_width=0, fill="tonexty", fillcolor="rgba(37,99,235,0.15)", showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=group.latency_s, y=group.edge_cents_mean, mode="lines+markers", name=name,
                                 customdata=group[["n_trades"]].to_numpy(), hovertemplate="%{x}s: %{y:.2f} cents<br>Trades: %{customdata[0]}<extra>%{fullData.name}</extra>"))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(title=dict(text="Net edge per trade vs reaction time.", font_size=18),
                      xaxis_title="Reaction time (seconds)", yaxis_title="Net edge (cents)")
    return style_chart(fig, 340)


def advance_cursor(cursor, end, speed, elapsed_seconds=1.0):
    """Advance by actual elapsed time, independent of render frequency or delays."""
    return min(cursor + round(SECOND * speed * max(0.0, elapsed_seconds)), end)


def sync_clock(end):
    """Settle elapsed playback at the old speed before controls change it."""
    now = time.monotonic()
    if st.session_state.playing:
        elapsed = now - st.session_state.get("clock_at", now)
        st.session_state.cursor = advance_cursor(
            st.session_state.cursor, end, st.session_state.get("clock_speed", 1), elapsed)
    st.session_state.clock_at = now


def replay_metrics(signals, cursor):
    """Read one consistent snapshot; count entries, never exits or contracts."""
    seen = signals.loc[signals.ts <= cursor].sort_values("ts", kind="stable")
    return {
        "profit": float(seen.iloc[-1].pnl_cum) if len(seen) else 0.0,
        "entries": int(seen.action.isin(["enter_long", "enter_short"]).sum()),
        "time": eastern([cursor])[0].strftime("%H:%M:%S"),
        "last": last_trade_sentence(seen.iloc[-1]) if len(seen) else "No trades yet.",
    }


def last_trade_sentence(row):
    """Describe only supplied row fields; never invent a reason for the trade."""
    action = {"enter_long": "Entered long", "enter_short": "Entered short", "exit": "Exited"}.get(row.action, row.action)
    venue = f" on {row['venue']}" if "venue" in row.index else ""
    return f"{action}{venue}, {row.qty:g} contract(s) at {row.price:.0%}; fee ${row.fee:.2f}."


def main():
    """Assemble controls and refresh placeholders without a blocking play loop."""
    st.set_page_config(page_title="StaleLine replay", layout="wide")
    # App-local styling avoids changing any repository-wide Streamlit settings.
    # Keep the last frame opaque during reruns instead of flashing a dim overlay.
    css = Path(__file__).with_name("replay.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")
    st.title("StaleLine | Replay")
    st.caption("Paper trading only. Prices show P(home team wins).")
    use_fixtures = st.sidebar.checkbox("Use sample demo fixtures", value=False,
                                       help="Synthetic results for the sample only. Off uses recorded outputs or placeholders.")
    if st.sidebar.button("Reload replay files"):
        # New upstream outputs must replace cached missing-file results on demand.
        load_games.clear()
        load_game.clear()
        st.session_state.playing = False
    try:
        games = load_games()
        # The catalog describes planned games too. Only offer recordings that
        # actually exist locally; do not download data or fabricate real games.
        available = games.game_id.map(lambda game: (ROOT / "data/ticks" / f"{game}.parquet").is_file())
        unavailable_count = int((~available).sum())
        games = games[available]
        if games.empty:
            st.info("No local game recordings are available for replay.")
            return
        if unavailable_count:
            st.caption(f"Showing locally recorded games. {unavailable_count} catalog games have no local recording yet.")
        picker, button, speed_control = st.columns([6, 1, 1])
        labels = {r.game_id: f"{r.home} vs {r.away} ({r.game_id})" for r in games.itertuples()}
        game_id = picker.selectbox("Game", list(labels), format_func=labels.get)
        prices, signals, curve, notes, end = load_game(game_id, use_fixtures)
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"Cannot load replay: {exc}")
        return
    if prices.empty or not len(prices.columns):
        st.info("No supported venue prices are available.")
        return
    signals_available = signals.attrs.get("available", True)
    if game_id == "sample":
        st.info("Sample price data only. No eligible real recording is currently selected.")
    st.caption(f"Price source: data/ticks/{game_id}.parquet. Timestamps and signal prices are shown without manual shifts.")
    if not signals_available:
        st.image(str(Path(__file__).with_name("assets") / "signals_pending.svg"),
                 caption="Trade signals unavailable. Markers, profit, and entry count await the real signal file.", width="stretch")
    start = int(prices.index.min())
    if st.session_state.get("game_id") != game_id:
        st.session_state.update(game_id=game_id, cursor=start, playing=False,
                                clock_at=time.monotonic(), clock_speed=1)
    def toggle_playback():
        """Change state before drawing the button so its label stays in sync."""
        sync_clock(end)
        if st.session_state.cursor >= end:
            st.session_state.cursor = start
        st.session_state.playing = not st.session_state.playing

    button.button("Pause" if st.session_state.playing else "Play", key="play_pause", on_click=toggle_playback)
    speed = speed_control.selectbox("Speed", [1, 5, 20], format_func=lambda value: f"{value}x")
    # Charge time since the last frame to the previous speed, then switch.
    sync_clock(end)
    st.session_state.clock_speed = speed
    for note in notes:
        st.caption(note)
    # Select an upstream strategy/bound before reading its cumulative P&L.
    # Cumulative series cannot be summed or interleaved by the presentation app.
    for column in ["leader", "venue", "bound"]:
        if column in signals and signals[column].nunique() > 1:
            choice = st.selectbox(f"Signal {column}", signals[column].dropna().unique())
            signals = signals[signals[column] == choice]
    # Keep all changing elements inside their fragment. Replacing an external
    # placeholder container every frame remounts its children and causes flicker.
    @st.fragment(run_every=0.25 if st.session_state.playing else None)
    def render_frame():
        """Refresh the replay region every 250 ms; pause keeps the cursor fixed."""
        sync_clock(end)
        cursor = st.session_state.cursor
        # Disable Streamlit's chart theme override so white surfaces and dark
        # labels remain consistent even when the user selected a dark app theme.
        st.plotly_chart(price_chart(prices, signals, cursor), width="stretch", key="prices", theme=None)
        metrics = replay_metrics(signals, cursor)
        # Fixed element positions keep Streamlit's DOM stable across frames.
        profit, count, replay_clock = st.columns(3)
        profit.metric("Running profit", f"${metrics['profit']:.2f}" if signals_available else "Unavailable")
        count.metric("Trades entered", metrics["entries"] if signals_available else "Unavailable")
        replay_clock.metric("Replay time (ET)", metrics["time"])
        st.caption("Last trade")
        st.write(metrics["last"] if signals_available else "Waiting for recorded signals.")
        st.caption("Replay complete. Press Play to restart." if cursor >= end else "Replay in progress" if st.session_state.playing else "Replay paused")
        if cursor >= end and st.session_state.playing:
            st.session_state.playing = False
            st.rerun()

    render_frame()
    if curve.empty:
        st.image(str(Path(__file__).with_name("assets") / "latency_pending.svg"),
                 caption="Latency results unavailable. This is a placeholder, not a measured curve.", width="stretch")
    else:
        st.plotly_chart(latency_chart(curve), width="stretch", key="latency", theme=None)


if __name__ == "__main__":
    main()
