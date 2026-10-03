"""Amendment 2 runner on synthetic books only: two fake machine roots, fake GAPS tables, fake maps.
Kickoffs are in 2025 so the seal guard is not involved; one test checks the guard itself."""
import json

import numpy as np
import pandas as pd
import pytest

import holdout_mid as H
from tests.test_activity_bias import hidden_path, quotes

NS = 1_000_000_000
N_GAMES = 44
KO0 = pd.Timestamp("2025-10-04 15:00", tz="UTC")
OUTAGE_GAME, BOTH_GAME, ONESIDED_GAME, PINNED_GAME = 5, 7, 9, 11
# The two outage games sit far from the rest so a gap inside their window touches no other window.
ISOLATED = {OUTAGE_GAME: pd.Timedelta(hours=16), BOTH_GAME: pd.Timedelta(hours=24)}


def kickoff(i):
    return KO0 + ISOLATED.get(i, pd.Timedelta(minutes=10 * i))


def et(ns):
    return pd.Timestamp(ns, tz="UTC").tz_convert("America/New_York").strftime("%a %b %d %H:%M:%S")


@pytest.fixture(scope="module")
def world(tmp_path_factory):
    rng = np.random.default_rng(21)
    base = tmp_path_factory.mktemp("w")
    cands, pc_map, pu_map = [], {}, {}
    frames = {"kalshi": [], "polymarket": [], "polymarket_us": []}
    for i in range(N_GAMES):
        ko = kickoff(i)
        ev, gid = f"KXNCAAFGAME-25OCT04A{i:02d}H{i:02d}", f"cfb_20251004_a{i:02d}_h{i:02d}"
        lo = ko.value - H.PRE_S * NS
        cands.append({"game_id": gid, "league": "CFB", "kickoff_utc": ko.strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "kalshi_ticker": ev, "polymarket_com_mapped": "y", "polymarket_us_mapped": "y",
                      "window_start_utc": ""})
        pc_map[ev] = {"collector_home_token": f"tok{i}"}
        pu_map[f"aec-cfb-a{i}-h{i}"] = {"kalshi_event": ev}
        p = hidden_path(rng)
        if i == PINNED_GAME:
            p[2 * 3600:] = 0.984                               # pinned (mid 0.98) from 1.5 h after kickoff
        for venue, mid, kw in (("kalshi", f"{ev}-H{i:02d}", dict(lag_s=0.0, flicker_per_min=6)),
                               ("polymarket", f"tok{i}", dict(lag_s=5.0, flicker_per_min=2)),
                               ("polymarket_us", f"aec-cfb-a{i}-h{i}", dict(lag_s=5.0, flicker_per_min=1, poll_s=1, recv_delay_s=0.3))):
            q = quotes(rng, p, venue=venue, **kw).assign(market_id=mid)
            q = q[q["price"].between(0.001, 0.999)]
            if i == ONESIDED_GAME and venue != "kalshi":
                q = q[q["kind"] == "bid"]                      # other venue's ask side empty all game
            q["ts"] = q["ts"] + lo
            frames[venue].append(q)
    machines = []
    for name in ("vultr", "mac"):
        root = base / name
        for venue, fs in frames.items():
            d = root / "data" / "live" / venue / "20251004"
            d.mkdir(parents=True)
            for j, f in enumerate(fs):
                f.to_parquet(d / f"{int(f['ts'].min() // NS)}_{j}.parquet", index=False)
        lines = ["| Start (ET) | End (ET) | Venue | Cause | Fixed by |", "|---|---|---|---|---|"]
        def gap(i, venue, secs):
            a = (kickoff(i) + pd.Timedelta(minutes=30)).value
            lines.append(f"| {et(a)} | {et(a + secs * NS)} | {venue} | test gap | test |")
        if name == "vultr":
            gap(OUTAGE_GAME, "polymarket", 90)
            gap(OUTAGE_GAME, "polymarket_us", 90)
        gap(BOTH_GAME, "all", 120)
        md = root / "GAPS.md"
        md.write_text("\n".join(lines) + "\n")
        machines.append(H.Machine(name, root, md, year=2025))
    maps = {"polymarket_com": pc_map, "polymarket_us": pu_map}
    return pd.DataFrame(cands), maps, machines


@pytest.mark.parametrize("test", ["polymarket.com", "Polymarket US"])
def test_runner_end_to_end(world, test):
    cands, maps, machines = world
    per, pl, dec = H.run_test(cands, maps, machines, test)
    by = per.set_index("game_id")
    g = lambda i: by.loc[f"cfb_20251004_a{i:02d}_h{i:02d}"]
    assert g(OUTAGE_GAME)["machine"] == "mac"                         # Vultr outage 90 s -> whole game from the Mac
    assert g(0)["machine"] == "vultr"
    assert g(BOTH_GAME)["machine"] == "" and g(BOTH_GAME)["reason"].startswith("excluded")
    assert "vultr" in g(BOTH_GAME)["reason"] and "mac" in g(BOTH_GAME)["reason"]
    assert g(ONESIDED_GAME)["qualifying"] is False and "mid changes" in g(ONESIDED_GAME)["reason"]
    assert g(ONESIDED_GAME)["n_changes_other"] == 0
    ko = pd.Timestamp(g(PINNED_GAME)["kickoff_utc"]).value
    assert g(PINNED_GAME)["window_end_ns"] <= ko + int(1.5 * 3600 + 60) * NS + 2 * NS
    ko0 = pd.Timestamp(g(0)["kickoff_utc"]).value
    assert g(0)["window_end_ns"] <= ko0 + H.POST_S * NS
    q = per[per["qualifying"].fillna(False).astype(bool)]
    assert len(q) >= 40 and (q["lag_s"] == 5).mean() > 0.9
    mach = by["machine"].to_dict()
    assert all(mach[a] == mach[b] == m for a, b, m in pl[["game_a", "game_b", "machine"]].itertuples(index=False))
    # Decision = xcorr_lead.decide on exactly these lags. Its verdict is not asserted: with placebo lags spread
    # over +-15 s, Mann-Whitney power for a 5 s lead at ~40 games is only ~60-70% (docs/results/activity_bias.md).
    import xcorr_lead as X
    other, min_lead = H.TESTS[test]
    assert dec == X.decide(q["lag_s"].to_numpy(float), pl["lag_s"].to_numpy(float), 0.0, "kalshi", other, min_lead_s=min_lead)
    assert dec["n_qualifying"] == len(q) and dec["median_corrected_lag_s"] == 5 and dec["share_positive"] > 0.9


def test_seal_guard_and_rest_cover(world, tmp_path):
    cands, maps, machines = world
    late = cands.head(1).assign(kickoff_utc="2026-10-03T19:30:00Z")
    with pytest.raises(ValueError):
        H.run_test(late, maps, machines, "polymarket.com")
    md = tmp_path / "GAPS.md"
    md.write_text("| Sat Oct 03 10:00:00 | Sat Oct 03 10:05:00 | kalshi_ws | drop | auto |\n")
    a = pd.Timestamp("2026-10-03 14:00:00", tz="UTC").value
    full = H.parse_gaps(md, [(a, a + 300 * NS)])
    assert full.empty                                                 # REST delivered the whole gap: no outage
    part = H.parse_gaps(md, [(a, a + 200 * NS)])
    assert len(part) == 1 and (part.end_ns - part.start_ns).item() == 100 * NS
