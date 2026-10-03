# Recorder health (deliverable 2)

Run from the repository root:

```powershell
app/.venv/Scripts/python -m streamlit run app/health.py
```

Use the team's **read-only** Tiger Data credentials. Set `TIGER_DSN` in
`app/.env` to the supplied PostgreSQL connection string. The page also accepts
the existing `TIGER_DATABASE_URL` setting and can read the root `.env` without
modifying it. Never commit credentials. Dependencies are already listed in the
repository requirements and installed in the local `app/.venv`.

The page checks the `ticks` table every ten seconds. Each venue card shows:

- Green when its newest tick is less than 60 seconds old.
- Red when that timestamp is 60 seconds old or older, missing, or in the future.
- The number of rows in the preceding ten minutes divided by ten.

CME, Kalshi, and Polymarket always have cards, even if absent. Additional venues
found in the table get cards too. An absent optional venue will show “No data.”
These are venue-wide counts across all games, including trades, bids and asks.
They measure data freshness, not whether the recorder process itself is alive.

The chart shows 60 completed one-minute intervals and fills missing minutes
with zero. Its times are Eastern; the snapshot timestamp is UTC. The newest
partial minute is excluded from the chart but included in the card's rate.

`fetch_snapshot` reads summary and history in one read-only transaction using
the database clock. Queries have a five-second statement timeout, and opening
a connection has a five-second timeout. An unavailable database clears cards
and reports unknown health; the next refresh retries automatically. No raw
database exception or connection string is shown on the page.

`venue_health` applies the freshness rule. `history_frame` inserts zero-count
minutes. `activity_chart` draws the graph. `main` assembles the page, and its
`refresh` fragment reloads the data every ten seconds.

Run offline checks:

```powershell
app/.venv/Scripts/python -B -m pytest app/test_health.py app/test_replay.py -q -o cache_dir=app/.pytest_cache
```

Live acceptance remains to be verified against the team's database: during an
agreed recorder test, observe that the card turns red on the first poll when
the latest tick is at least 60 seconds old. Normal polling adds up to ten
seconds of detection delay, plus query time. This page never stops the recorder.
