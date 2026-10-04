"""Synthetic tests for Post-hoc Idea 6 (post-hoc, exploratory; designed and selected on training only)."""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import posthoc_idea6 as P  # noqa: E402
import strategy_a as A  # noqa: E402

NS = P.NS
KO = pd.Timestamp("2025-10-01 23:00", tz="UTC")
E = pd.Timestamp("2025-10-02 02:30", tz="UTC")


def W(ts: pd.Timestamp) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def team(ha: str, abbr: str, name: str, score: int) -> dict:
    return {"homeAway": ha, "score": str(score),
            "team": {"abbreviation": abbr, "displayName": name, "location": name, "shortDisplayName": name, "name": name}}


def summary(plays: list[dict], final=(24, 17), completed=True, scoring=None) -> dict:
    comp = {"status": {"type": {"completed": completed}},
            "competitors": [team("home", "HOM", "Homeville", final[0]), team("away", "AWY", "Awaytown", final[1])]}
    return {"header": {"competitions": [comp]}, "drives": {"previous": [{"plays": plays}]},
            "scoringPlays": scoring or []}


def play(pid, text, hs, as_, wc, scoring=False) -> dict:
    return {"id": pid, "text": text, "homeScore": hs, "awayScore": as_, "wallclock": W(wc), "scoringPlay": scoring}


def clean_plays(hs=24, as_=17) -> list[dict]:
    return [play("1", "Kickoff", 0, 0, KO),
            play("2", "Touchdown", hs, as_, E - pd.Timedelta(minutes=5), scoring=True),
            play("3", "J. Smith takes a knee", hs, as_, E - pd.Timedelta(seconds=30)),
            play("4", "End of 4th Quarter", hs, as_, E)]


def game(result=1.0) -> A.Game:
    return A.Game("cfb_20251001_awy_hom", "CFB", "HOM", "AWY", "EV", KO, "espn", result)


def trades(rows: list[tuple[pd.Timestamp, str, float]]) -> pd.DataFrame:
    """rows: (ts, team, own YES price) -> tick contract (price = P(home))."""
    return pd.DataFrame([{"ts": t.value, "venue": "kalshi", "market_id": f"EV-{tm}", "kind": "trade",
                          "price": p if tm == "HOM" else 1 - p, "size": 5.0, "side": "buy"} for t, tm, p in rows])


def test_clean_end_marker():
    end = P.game_end(summary(clean_plays(), scoring=[{"id": "2", "homeScore": 24, "awayScore": 17}]))
    assert end["E_ns"] == E.value and end["leader"] == "home"


def test_play_after_end_of_4th_marker_is_skipped():
    pl = clean_plays() + [play("5", "A. Manning takes a knee", 24, 17, E + pd.Timedelta(seconds=5))]
    assert P.game_end(summary(pl))["skip"] == "play or score after marker"


def test_tied_marker_and_ot_scoring_end_skipped():
    pl = [play("1", "Kickoff", 0, 0, KO), play("2", "End of 4th Quarter", 13, 13, E),
          play("3", "Shipley 45 Yd Field Goal", 13, 16, E + pd.Timedelta(minutes=7), scoring=True)]
    assert P.game_end(summary(pl, final=(13, 16)))["skip"] == "no untied end marker"


def test_scoring_after_marker_and_not_final_skipped():
    s = summary(clean_plays(), final=(24, 24))
    assert P.game_end(s)["skip"] == "play or score after marker"
    assert P.game_end(summary(clean_plays(), completed=False))["skip"] == "ESPN status not final"


def test_marker_text_variants():
    for t in ("END GAME", "End of Game.", "end of 4th quarter"):
        assert P.is_marker(t)
    assert not P.is_marker("End Quarter 4") and not P.is_marker("End of 3rd Quarter")


def test_fill_never_before_t_plus_1s():
    g = game()
    t = E.value + 60 * NS
    tr = trades([(E + pd.Timedelta(seconds=60), "HOM", 0.50),
                 (E + pd.Timedelta(seconds=60.999), "HOM", 0.60),
                 (E + pd.Timedelta(seconds=61), "HOM", 0.90),
                 (E + pd.Timedelta(seconds=70), "HOM", 0.95)])
    r = P.leg(tr, g, "HOM", t)
    assert r["fill_ts"] >= t + NS and r["fill_ts"] == (E + pd.Timedelta(seconds=61)).value
    assert r["fill"] == pytest.approx(0.91)
    r2 = P.leg(trades([(E + pd.Timedelta(seconds=61), "HOM", 0.98)]), g, "HOM", t)
    assert not r2["entered"] and r2["skip"] == "fill at 0.99"
    r3 = P.leg(trades([(E + pd.Timedelta(seconds=60.5), "HOM", 0.50)]), g, "HOM", t)
    assert r3["skip"] == "no post-decision trade"


def test_winner_uses_no_data_after_E():
    """Score at the marker decides; ESPN plays and the final score after E can only cause a skip, never a different
    winner. Here the away team leads at the marker: winner = away even though Kalshi settles home."""
    end = P.game_end(summary(clean_plays(10, 20), final=(10, 20)))
    g = game(result=1.0)
    assert P.winner_code(end, "same", g) == "AWY"
    assert P.winner_code(end, "swapped", g) == "HOM"
    tr = trades([(E + pd.Timedelta(seconds=61), "AWY", 0.50), (E + pd.Timedelta(seconds=61), "HOM", 0.50)])
    rows, desc = P.evaluate_game(tr, g, end, "same")
    w = [r for r in rows if r["leg"] == "winner" and r["D"] == 60][0]
    assert w["team"] == "AWY" and w["t_ns"] == E.value + 60 * NS


def test_payout_is_kalshi_settlement_not_espn():
    """ESPN says home leads at E; Kalshi settled home 0 (wrong or early settlement): the winner leg loses."""
    end = P.game_end(summary(clean_plays()))
    g = game(result=0.0)
    tr = trades([(E + pd.Timedelta(seconds=65), "HOM", 0.90), (E + pd.Timedelta(seconds=65), "AWY", 0.10)])
    rows, _ = P.evaluate_game(tr, g, end, "same")
    w = [r for r in rows if r["leg"] == "winner" and r["D"] == 60][0]
    pl = [r for r in rows if r["leg"] == "placebo" and r["D"] == 60][0]
    assert w["payout"] == 0.0 and w["pnl_direct"] < 0
    assert pl["payout"] == 1.0
    g2 = game(result=float("nan"))
    w2 = [r for r in P.evaluate_game(tr, g2, end, "same")[0] if r["leg"] == "winner"][0]
    assert w2["skip"] == "unsettled"


def test_fee_function():
    # 0.07 x 10 x P x (1 - P), rounded up to the cent
    assert P.fee_direct(Decimal("0.95")) == Decimal("0.04")   # 0.03325
    assert P.fee_direct(Decimal("0.98")) == Decimal("0.02")   # 0.01372
    assert P.fee_direct(Decimal("0.99")) == Decimal("0.01")   # 0.00693
    assert P.fee_webull(Decimal("0.95")) == Decimal("0.20")


def test_sealed_game_refused():
    g = A.Game("cfb_20260905_x_y", "CFB", "HOM", "AWY", "EV", pd.Timestamp("2026-09-05", tz="UTC"), "espn", 1.0)
    with pytest.raises(ValueError):
        P.evaluate_game(trades([]), g, {"skip": "x"}, None)
