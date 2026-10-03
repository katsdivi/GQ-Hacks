# StaleLine app

Launch both pages together, with sidebar navigation:

```powershell
app/.venv/Scripts/python -m streamlit run app/main.py
```

Select **Replay** or **Recorder Health** in the sidebar. Leaving Replay pauses
it at the last displayed time; return and press Play to continue. Only the
selected page refreshes. Health connection setup is documented in `HEALTH.md`.

## Standalone replay

Deliverable 3 uses recorded outputs by default. When signals or the latency
report are missing, the page shows labeled SVG placeholder images from
`app/assets/`; unavailable metrics are not shown as zero. Enable **Use sample
demo fixtures** in the sidebar to see the earlier synthetic example.

Eligible real recordings are read from `data/ticks/<game_id>.parquet` and must
have a matching catalog entry. Signal outputs are read from
`out/signals/<game_id>.parquet`, and the latency report from
`out/latency_curve.csv`. **Reload replay files** clears cached inputs after the
team supplies new files. The app never creates those upstream outputs.

Real-game acceptance is pending: this checkout currently has only sample ticks
and no signal or latency outputs. Once available, inspect five real trade
markers against the price moves. Preserve original timestamps and report any
mismatch rather than shifting markers. Sealed test games remain excluded.

From the repository root, with the project's requirements installed:

```powershell
streamlit run app/replay.py
```

The local environment created for this task can also launch it:

```powershell
app/.venv/Scripts/python -m streamlit run app/replay.py
```

Choose a game, press Play, and select 1x, 5x, or 20x. The display refreshes every 250 ms; the cursor advances by actual elapsed time
multiplied by 1, 5, or 20. Rendering delays do not change the selected game pace.
Pause freezes the cursor. Play restarts a completed replay. Times use New York
time with daylight savings. Real games on or after August 1, 2026 remain sealed.

The app reads existing ticks, signals and latency reports without running any
pipeline or writing outputs. Quote midpoints use only previously observed bids
and asks; venues without quotes use trades. Trade markers retain their exact
file timestamps and prices, even when a fill differs from a plotted midpoint.
Profit is the latest supplied `pnl_cum` in dollars; the count is entry actions.
When outputs contain multiple strategy directions or bounds, select one series.
The latency chart shows the latest report, which can represent multiple games.

Missing sample signals and latency reports fall back to `app/fixtures/`.
These tiny fixtures contain **fictional actions, profit and latency estimates**,
clearly labeled on screen. They are UI examples, not evidence of an edge. Marker
prices are copied from the sample Kalshi midpoints. No fixtures are substituted
for real games. To rebuild only the sample markers:

```powershell
python app/fixtures/build_fixtures.py
```

Validation (all test files and pytest cache stay under `app`):

```powershell
app/.venv/Scripts/python -B -m pytest app/test_replay.py -q -o cache_dir=app/.pytest_cache
```
