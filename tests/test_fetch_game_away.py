"""download_all.fetch_game (the clean-clone path) takes the away market from the Kalshi event's own market list,
never from team codes. The 10 Miami (OH) Strategy B games: event market lists recorded from Kalshi
(GET /historical/markets?event_ticker=..., ids only, 2026-10-03) and the away tickers the bulk download used
(data/raw/t8_game_plan.csv). The resolved away ticker must equal the bulk one exactly."""
import json
from pathlib import Path

import pandas as pd
import pytest

import ingest.download_all as D

GAMES = json.loads((Path(__file__).parent / "data_moh_events.json").read_text())


def test_ten_miami_oh_games_resolve_to_bulk_tickers():
    assert len(GAMES) == 10
    b = pd.read_csv(Path(__file__).parents[1] / "data" / "games.csv").set_index("game_id")
    for g in GAMES:
        assert b.loc[g["game_id"], "kalshi_ticker"] == g["home"]          # the committed B game set's home ticker
        assert D.pick_away_ticker(g["home"], g["event_markets"]) == g["bulk_away"]
        old = g["home"].rsplit("-", 1)[0] + "-" + b.loc[g["game_id"], "away"]
        assert old != g["bulk_away"]                                      # the old rebuild was wrong for all 10


def test_event_away_ticker_uses_the_listing(monkeypatch):
    g = GAMES[0]
    calls = []

    def fake_get(url, params=None, throttle=True):
        calls.append((url, params))
        return {"markets": [{"ticker": t} for t in g["event_markets"]]} if "historical" in url else {"markets": []}
    monkeypatch.setattr(D, "get", fake_get)
    assert D.event_away_ticker(g["home"], g["event"]) == g["bulk_away"]
    assert calls[0][1] == {"event_ticker": g["event"], "limit": 100}


def test_bad_listing_raises_instead_of_guessing():
    with pytest.raises(ValueError):
        D.pick_away_ticker("EV-H", ["EV-H"])                               # only the home market
    with pytest.raises(ValueError):
        D.pick_away_ticker("EV-H", ["EV-A", "EV-B"])                       # home missing
    with pytest.raises(ValueError):
        D.pick_away_ticker("EV-H", ["EV-H", "EV-A", "EV-B"])               # more than two markets
